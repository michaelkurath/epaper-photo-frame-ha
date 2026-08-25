#include "driver.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <esp_sleep.h>
#include <sys/time.h>
#include <time.h>

#include "firmware_core.h"

#ifndef EPAPER_ENABLE
#error "BOARD_SCREEN_COMBO in driver.h must select an ePaper setup"
#endif

#if !defined(PHOTO_FRAME_DISPLAY_MODEL) || !defined(PHOTO_FRAME_DEVICE_PREFIX) || \
    !defined(PHOTO_FRAME_HARDWARE_NAME) || !defined(PHOTO_FRAME_PORTRAIT_WIDTH) || \
    !defined(PHOTO_FRAME_PORTRAIT_HEIGHT)
#error "driver.h must define the complete photo-frame hardware profile"
#endif

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy secrets.example.h to secrets.h and enter Wi-Fi, URL and API token"
#endif

namespace {

constexpr char kFirmwareVersion[] = "0.2.0";
constexpr std::uint32_t kWifiTimeoutMs = 30000;
constexpr std::uint32_t kHttpTimeoutMs = 45000;
constexpr std::uint32_t kErrorRetrySeconds = 15 * 60;
constexpr std::uint32_t kMinimumSleepSeconds = 60;
constexpr std::uint32_t kMaximumSleepSeconds = 7 * 24 * 60 * 60;

RTC_DATA_ATTR bool gHasDisplayedFrame = false;

EPaper epaper;

struct DeviceConfig {
  String displayModel;
  std::uint16_t width = 0;
  std::uint16_t height = 0;
  std::size_t rawSize = 0;
  std::uint32_t frameIntervalSeconds = 0;
  std::int64_t serverTime = 0;
  String nightStart;
  String nightEnd;
};

struct FrameResult {
  bool ok = false;
  String frameId;
  String detail;
};

String baseUrl() {
  String value(HOME_ASSISTANT_URL);
  while (value.endsWith("/")) {
    value.remove(value.length() - 1);
  }
  return value;
}

String deviceId() {
  String value = WiFi.macAddress();
  value.replace(":", "");
  value.toLowerCase();
  return String(PHOTO_FRAME_DEVICE_PREFIX) + value;
}

void addAuthorization(HTTPClient& http) {
  http.addHeader("Authorization", String("Bearer ") + DEVICE_API_TOKEN);
}

bool connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  const std::uint32_t started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < kWifiTimeoutMs) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi connection timed out");
    return false;
  }
  Serial.printf("Wi-Fi connected, IP %s, RSSI %d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  return true;
}

bool validatePalette(JsonArray palette) {
  static const char* expected[] = {"white", "black", "red",
                                   "yellow", "blue", "green"};
  if (palette.size() != photo_frame::kPaletteSize) {
    return false;
  }
  for (std::size_t index = 0; index < photo_frame::kPaletteSize; ++index) {
    const char* actual = palette[index] | "";
    if (strcmp(actual, expected[index]) != 0) {
      return false;
    }
  }
  return true;
}

bool fetchConfig(DeviceConfig& config, String& detail) {
  HTTPClient http;
  http.setConnectTimeout(kHttpTimeoutMs);
  http.setTimeout(kHttpTimeoutMs);
  if (!http.begin(baseUrl() + "/api/device/config")) {
    detail = "invalid Home Assistant URL";
    return false;
  }
  addAuthorization(http);
  const int status = http.GET();
  if (status != HTTP_CODE_OK) {
    detail = "config HTTP " + String(status);
    http.end();
    return false;
  }

  JsonDocument document;
  const DeserializationError jsonError = deserializeJson(document, http.getStream());
  if (jsonError) {
    detail = "config JSON: " + String(jsonError.c_str());
    http.end();
    return false;
  }

  const int protocol = document["protocol_version"] | 0;
  config.displayModel = document["display_model"] | "";
  config.width = document["width"] | 0;
  config.height = document["height"] | 0;
  config.rawSize = document["raw_size_bytes"] | 0;
  config.frameIntervalSeconds = document["frame_interval_seconds"] | 0;
  config.serverTime = document["server_time"] | 0;
  config.nightStart = document["night_start"] | "";
  config.nightEnd = document["night_end"] | "";
  const JsonArray palette = document["palette"].as<JsonArray>();
  http.end();

  int unusedMinutes = 0;
  if (protocol != 1) {
    detail = "unsupported device protocol " + String(protocol);
  } else if (config.displayModel != PHOTO_FRAME_DISPLAY_MODEL) {
    detail = "server display profile does not match firmware";
  } else if (!photo_frame::validGeometry(
                 config.width, config.height, PHOTO_FRAME_PORTRAIT_WIDTH,
                 PHOTO_FRAME_PORTRAIT_HEIGHT)) {
    detail = "unexpected display geometry";
  } else if (config.rawSize != photo_frame::rawSize(config.width, config.height)) {
    detail = "unexpected RAW size";
  } else if (config.frameIntervalSeconds < kMinimumSleepSeconds ||
             config.frameIntervalSeconds > kMaximumSleepSeconds) {
    detail = "invalid frame interval";
  } else if (config.serverTime <= 0) {
    detail = "invalid server time";
  } else if (!photo_frame::parseClock(config.nightStart.c_str(), unusedMinutes) ||
             !photo_frame::parseClock(config.nightEnd.c_str(), unusedMinutes)) {
    detail = "invalid night window";
  } else if (!validatePalette(palette)) {
    detail = "unexpected colour palette";
  } else {
    return true;
  }
  return false;
}

void setLocalClock(std::int64_t epochSeconds) {
  timeval value{};
  value.tv_sec = static_cast<time_t>(epochSeconds);
  settimeofday(&value, nullptr);
  setenv("TZ", TIME_ZONE_RULE, 1);
  tzset();
}

bool isNightNow(const DeviceConfig& config, std::uint32_t& sleepSeconds) {
  int start = 0;
  int end = 0;
  if (!photo_frame::parseClock(config.nightStart.c_str(), start) ||
      !photo_frame::parseClock(config.nightEnd.c_str(), end)) {
    return false;
  }
  time_t nowEpoch = time(nullptr);
  tm local{};
  localtime_r(&nowEpoch, &local);
  const int now = local.tm_hour * 60 + local.tm_min;
  if (!photo_frame::inNightWindow(now, start, end)) {
    return false;
  }
  sleepSeconds = photo_frame::secondsUntilNightEnd(now, end) + 60;
  return true;
}

bool configureDisplay(std::uint16_t width, std::uint16_t height) {
  if (!psramFound()) {
    Serial.println("OPI PSRAM not available; check Arduino Tools settings");
    return false;
  }
  epaper.begin();
  for (std::uint8_t rotation = 0; rotation < 4; ++rotation) {
    epaper.setRotation(rotation);
    if (epaper.width() == width && epaper.height() == height) {
      Serial.printf("Display ready: %u x %u, rotation %u\n", width, height,
                    rotation);
      epaper.fillScreen(TFT_WHITE);
      return true;
    }
  }
  Serial.printf("No rotation matches %u x %u\n", width, height);
  return false;
}

std::uint16_t paletteColour(std::uint8_t index) {
  static const std::uint16_t colours[] = {
      TFT_WHITE, TFT_BLACK, TFT_RED, TFT_YELLOW, TFT_BLUE, TFT_GREEN};
  return colours[index];
}

FrameResult downloadFrame(const DeviceConfig& config, bool advance) {
  FrameResult result;
  HTTPClient http;
  http.setConnectTimeout(kHttpTimeoutMs);
  http.setTimeout(kHttpTimeoutMs);
  http.useHTTP10(true);
  const String endpoint =
      advance ? "/api/device/next.raw" : "/api/device/current.raw";
  if (!http.begin(baseUrl() + endpoint)) {
    result.detail = "invalid frame URL";
    return result;
  }
  const char* headerKeys[] = {"X-Frame-Id", "X-Frame-Width", "X-Frame-Height",
                              "X-Frame-Bytes"};
  http.collectHeaders(headerKeys, 4);
  addAuthorization(http);
  const int status = advance ? http.sendRequest("POST") : http.GET();
  if (status != HTTP_CODE_OK) {
    result.detail = "frame HTTP " + String(status);
    http.end();
    return result;
  }

  result.frameId = http.header("X-Frame-Id");
  const long headerWidth = http.header("X-Frame-Width").toInt();
  const long headerHeight = http.header("X-Frame-Height").toInt();
  const long headerBytes = http.header("X-Frame-Bytes").toInt();
  const int contentLength = http.getSize();
  if (result.frameId.isEmpty() || headerWidth != config.width ||
      headerHeight != config.height || headerBytes != config.rawSize ||
      contentLength != static_cast<int>(config.rawSize)) {
    result.detail = "frame headers do not match config";
    http.end();
    return result;
  }

  WiFiClient* stream = http.getStreamPtr();
  stream->setTimeout(kHttpTimeoutMs);
  std::uint8_t buffer[1024];
  std::size_t received = 0;
  std::size_t pixel = 0;
  while (received < config.rawSize) {
    const int available = stream->available();
    if (available <= 0) {
      if (!http.connected()) {
        break;
      }
      delay(1);
      continue;
    }
    std::size_t wanted = sizeof(buffer);
    if (static_cast<std::size_t>(available) < wanted) {
      wanted = static_cast<std::size_t>(available);
    }
    if (config.rawSize - received < wanted) {
      wanted = config.rawSize - received;
    }
    const std::size_t count = stream->readBytes(buffer, wanted);
    if (count == 0) {
      break;
    }
    for (std::size_t offset = 0; offset < count; ++offset) {
      const std::uint8_t packed = buffer[offset];
      if (!photo_frame::validPackedByte(packed)) {
        result.detail = "invalid palette index in RAW frame";
        http.end();
        return result;
      }
      const std::uint8_t first = photo_frame::highPixel(packed);
      const std::uint8_t second = photo_frame::lowPixel(packed);
      epaper.drawPixel(pixel % config.width, pixel / config.width,
                       paletteColour(first));
      ++pixel;
      epaper.drawPixel(pixel % config.width, pixel / config.width,
                       paletteColour(second));
      ++pixel;
    }
    received += count;
  }
  http.end();

  if (received != config.rawSize ||
      pixel != static_cast<std::size_t>(config.width) * config.height) {
    result.detail = "incomplete RAW frame";
    return result;
  }

  Serial.printf("Validated %u bytes; refreshing display\n",
                static_cast<unsigned>(received));
  epaper.update();
  epaper.sleep();
  result.ok = true;
  return result;
}

bool reportStatus(const char* status, const String& frameId, const String& detail,
                  std::uint32_t cycleMs) {
  HTTPClient http;
  http.setConnectTimeout(kHttpTimeoutMs);
  http.setTimeout(kHttpTimeoutMs);
  if (!http.begin(baseUrl() + "/api/device/report")) {
    return false;
  }
  addAuthorization(http);
  http.addHeader("Content-Type", "application/json");
  JsonDocument document;
  document["device_id"] = deviceId();
  document["firmware_version"] = kFirmwareVersion;
  document["status"] = status;
  if (!frameId.isEmpty()) {
    document["frame_id"] = frameId;
  }
  document["wifi_rssi"] = WiFi.RSSI();
  document["cycle_ms"] = cycleMs;
  if (!detail.isEmpty()) {
    document["detail"] = detail.substring(0, 256);
  }
  String body;
  serializeJson(document, body);
  const int response = http.POST(body);
  http.end();
  return response == HTTP_CODE_OK;
}

void sleepFor(std::uint32_t seconds) {
  if (seconds < kMinimumSleepSeconds) {
    seconds = kMinimumSleepSeconds;
  }
  if (seconds > kMaximumSleepSeconds) {
    seconds = kMaximumSleepSeconds;
  }
  Serial.printf("Sleep for %u seconds\n", seconds);
  Serial.flush();
#if ENABLE_DEEP_SLEEP
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  esp_sleep_enable_timer_wakeup(static_cast<std::uint64_t>(seconds) * 1000000ULL);
  esp_deep_sleep_start();
#else
  Serial.println("Deep sleep disabled for bench test; reset to run again");
#endif
}

void failCycle(const String& detail, std::uint32_t started) {
  Serial.println("ERROR: " + detail);
  if (WiFi.status() == WL_CONNECTED) {
    reportStatus("error", "", detail, millis() - started);
  }
  sleepFor(kErrorRetrySeconds);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);
  const std::uint32_t started = millis();
  Serial.printf("ePaper Photo Frame %s firmware %s\n", PHOTO_FRAME_HARDWARE_NAME,
                kFirmwareVersion);

  if (!connectWifi()) {
    failCycle("Wi-Fi unavailable", started);
    return;
  }

  DeviceConfig config;
  String detail;
  if (!fetchConfig(config, detail)) {
    failCycle(detail, started);
    return;
  }
  setLocalClock(config.serverTime);
  reportStatus("awake", "", "", millis() - started);

  std::uint32_t sleepSeconds = config.frameIntervalSeconds;
  if (isNightNow(config, sleepSeconds)) {
    reportStatus("sleeping", "", "night window", millis() - started);
    sleepFor(sleepSeconds);
    return;
  }

  if (!configureDisplay(config.width, config.height)) {
    failCycle("display initialization failed", started);
    return;
  }

  const FrameResult frame = downloadFrame(config, gHasDisplayedFrame);
  if (!frame.ok) {
    epaper.sleep();
    failCycle(frame.detail, started);
    return;
  }
  gHasDisplayedFrame = true;
  reportStatus("displayed", frame.frameId, "", millis() - started);
  reportStatus("sleeping", frame.frameId, "timer", millis() - started);
  sleepFor(config.frameIntervalSeconds);
}

void loop() { delay(1000); }
