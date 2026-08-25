#pragma once

#include <cstddef>
#include <cstdint>

namespace photo_frame {

constexpr std::uint16_t kP133PortraitWidth = 1200;
constexpr std::uint16_t kP133PortraitHeight = 1600;
constexpr std::uint16_t kP073PortraitWidth = 480;
constexpr std::uint16_t kP073PortraitHeight = 800;
constexpr std::uint8_t kPaletteSize = 6;

constexpr bool validGeometry(std::uint16_t width, std::uint16_t height,
                             std::uint16_t portraitWidth,
                             std::uint16_t portraitHeight) {
  return (width == portraitWidth && height == portraitHeight) ||
         (width == portraitHeight && height == portraitWidth);
}

constexpr bool knownGeometry(std::uint16_t width, std::uint16_t height) {
  return validGeometry(width, height, kP133PortraitWidth, kP133PortraitHeight) ||
         validGeometry(width, height, kP073PortraitWidth, kP073PortraitHeight);
}

constexpr std::size_t rawSize(std::uint16_t width, std::uint16_t height) {
  return static_cast<std::size_t>(width) * height / 2;
}

constexpr std::uint8_t highPixel(std::uint8_t packed) { return packed >> 4; }
constexpr std::uint8_t lowPixel(std::uint8_t packed) { return packed & 0x0F; }

constexpr bool validPackedByte(std::uint8_t packed) {
  return highPixel(packed) < kPaletteSize && lowPixel(packed) < kPaletteSize;
}

inline bool parseClock(const char* value, int& minutes) {
  if (value == nullptr || value[0] < '0' || value[0] > '2' ||
      value[1] < '0' || value[1] > '9' || value[2] != ':' ||
      value[3] < '0' || value[3] > '5' || value[4] < '0' ||
      value[4] > '9' || value[5] != '\0') {
    return false;
  }
  const int hours = (value[0] - '0') * 10 + value[1] - '0';
  if (hours > 23) {
    return false;
  }
  minutes = hours * 60 + (value[3] - '0') * 10 + value[4] - '0';
  return true;
}

constexpr bool inNightWindow(int now, int start, int end) {
  if (start == end) {
    return false;
  }
  return start < end ? now >= start && now < end : now >= start || now < end;
}

constexpr std::uint32_t secondsUntilNightEnd(int now, int end) {
  int delta = end - now;
  if (delta <= 0) {
    delta += 24 * 60;
  }
  return static_cast<std::uint32_t>(delta) * 60U;
}

}  // namespace photo_frame
