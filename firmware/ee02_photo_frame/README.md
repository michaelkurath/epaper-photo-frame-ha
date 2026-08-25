# EE02 / 13.3-inch controller firmware 0.2.0

First controller firmware for this exact hardware combination:

- Seeed Studio XIAO ePaper Display Board EE02;
- XIAO ESP32-S3 Plus;
- 13.3-inch Spectra 6 panel, 1200 x 1600 pixels, P133_SP6;
- the Home Assistant ePaper Photo Frame App in this repository.

The Home Assistant App performs photo selection, cropping, colour conversion
and dithering. The controller is deliberately thin: it validates and displays
the already prepared six-colour RAW frame, reports its state, and sleeps.

## What version 0.2.0 does

1. Connect to 2.4 GHz Wi-Fi.
2. Read and validate the exact `spectra_13_3_ee02` display profile, geometry,
   frame interval, server time and night window from `/api/device/config`.
3. Select portrait or landscape rotation from the server geometry.
4. Download `current.raw` on the first boot and `next.raw` after later wakes.
5. Validate HTTP metadata, exactly 960,000 bytes, 1,920,000 pixels and every
   4-bit palette index before refreshing the panel.
6. Report `awake`, `displayed`, `sleeping`, or `error` to Home Assistant.
7. Use timer deep sleep between frames and sleep through the configured night
   window.

No incomplete download is sent to the physical display. The RAW stream is
written directly into the Seeed_GFX framebuffer; a second 960 kB frame buffer
is not allocated.

## Arduino preparation

Use the current setup described by Seeed for the EE02 and its
`XIAO_EPaper_Hello` example. In Arduino IDE install:

- Espressif ESP32 board support with the XIAO ESP32-S3 Plus target;
- Seeed_GFX from Seeed's repository/library package;
- ArduinoJson 7.x.

Select **OPI PSRAM: Enabled**. For useful first-start logs also select
**USB CDC On Boot: Enabled**. The display framebuffer is too large to run
without PSRAM.

The project sets Seeed_GFX's official P133_SP6 target and the matching server
profile in `driver.h`:

```cpp
#define BOARD_SCREEN_COMBO 510
#define USE_XIAO_EPAPER_DISPLAY_BOARD_EE02
#define PHOTO_FRAME_DISPLAY_MODEL "spectra_13_3_ee02"
```

In the Home Assistant App configuration select
`spectra_13_3_ee02`. The firmware refuses the 7.3-inch profile before
initialising or refreshing this panel.

## Configure and flash

1. Copy `secrets.example.h` to `secrets.h` in this folder.
2. Enter the 2.4 GHz Wi-Fi name and password.
3. Set `HOME_ASSISTANT_URL` to the Home Assistant machine's LAN address and
   fixed App port, for example `http://192.168.1.10:8080`. Do not use the
   Home Assistant Ingress/browser URL.
4. Enter the same device API token that is configured in the App.
5. Leave `ENABLE_DEEP_SLEEP` set to `false` for the first test.
6. With all power disconnected, seat and lock the display FPC cable in the
   EE02 connector. Then connect the XIAO by USB-C.
7. Open `ee02_photo_frame.ino`, compile, upload, and monitor Serial at
   115200 baud.

A successful first cycle prints Wi-Fi details, the selected rotation, a
validated byte count, and the display refresh. It also appears under the
controller telemetry in the App's Web UI. Only then change
`ENABLE_DEEP_SLEEP` to `true` and upload again.

## Safety and network scope

- Disconnect USB and battery power before inserting or removing the panel
  cable.
- Keep the panel flat and avoid pressure or twisting.
- Firmware 0.2.0 uses HTTP on the trusted local network. The bearer token is
  therefore not protected against someone already able to sniff that LAN.
  Do not expose port 8080 to the internet. Local TLS can be added later.
- A failed cycle waits 15 minutes before retrying so a network outage cannot
  drain the battery with a tight reboot loop.

## Deferred until the first hardware test

- physical button assignments;
- battery-voltage calibration and charging telemetry;
- optional orientation sensor;
- captive-portal provisioning and OTA updates;
- throughput optimisations based on measured EE02 refresh and transfer times.

These features do not change the server protocol and can be added later.

For the smaller 7.3-inch 800 x 480 panel, use the physically different EE04
board and the sibling `firmware/ee04_photo_frame` sketch instead.
