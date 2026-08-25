# ePaper Photo Frame

## Installation from the public GitHub repository

1. In Home Assistant open **Settings → Apps → App store**.
2. Open the repository management menu and add
   `https://github.com/michaelkurath/epaper-photo-frame-ha`.
3. Refresh the App store if necessary, select **ePaper Photo Frame**, and
   install it.
4. Configure the required options below, save them, and start the App.

For local development, the complete `epaper_photo_frame` directory can instead
be copied to Samba's `local_apps` share. The resulting path must be
`local_apps\\epaper_photo_frame\\config.yaml`; avoid an accidental second
nested `epaper_photo_frame` folder. The included `scripts/deploy-local.sh` can
perform this copy when `local_apps` is mounted as a normal directory.

## Required options

- `album_url`: the public Google Photos share link.
- `api_token`: a random secret with at least 16 characters. The same token will
  later be entered in the ESP32 firmware configuration.

The link and token live in `/data/options.json` inside the App data volume and
are intentionally absent from Git.

## First test

1. Start the App and open its Web UI.
2. Press **Album jetzt synchronisieren**.
3. Confirm that the photo count is non-zero and a six-colour preview appears.
4. From the local network, check `http://HOME_ASSISTANT_IP:8080/health`.

## Device API

All `/api/device/*` calls require this header:

```text
Authorization: Bearer YOUR_API_TOKEN
```

Endpoints:

- `GET /api/device/config`: protocol version, display geometry, palette, exact
  RAW size, sleep interval, and night pause.
- `GET /api/device/current.png`: current rendered frame, without advancing.
- `GET /api/device/current.raw`: current packed frame, without advancing.
- `POST /api/device/next.png`: select and return the next rendered frame.
- `POST /api/device/next.raw`: the same frame as packed 4-bit palette indices.
- `POST /api/device/report`: record controller state, displayed frame, battery,
  Wi-Fi signal, and cycle duration.

RAW data contains two pixels per byte: the first pixel in the high nibble and
the second in the low nibble. Palette indices are `0 white`, `1 black`, `2 red`,
`3 yellow`, `4 blue`, `5 green`. The final mapping to the EE02 driver remains a
firmware concern so it can be changed without touching the album or rendering
modules.

## Controller simulator

The Web UI contains a browser-based controller simulator that follows the
planned ESP32 cycle instead of merely previewing a PNG:

1. wake and fetch `/api/device/config`;
2. skip the display refresh during the configured night window;
3. download the packed RAW frame and validate dimensions, byte count, and all
   palette indices;
4. reconstruct the display image directly from the RAW data;
5. report the displayed frame and simulated device telemetry;
6. enter simulated deep sleep until the next cycle.

Automatic mode advances a virtual clock by the real frame interval while only
waiting 5, 10, or 30 seconds in the browser. It therefore tests multi-cycle and
night-window behaviour without waiting several hours.

## EE02 firmware 0.1.0

The repository now contains a first physical controller implementation under
`firmware/ee02_photo_frame`. It targets the XIAO ePaper Display Board EE02,
XIAO ESP32-S3 Plus, and the 13.3-inch 1200 x 1600 Spectra 6 T133A01 panel.

The controller uses the same API as the simulator. It validates protocol
version, dimensions, palette, frame headers, RAW length, and every packed
palette index before calling the physical display update. It automatically
selects portrait or landscape rotation from the dimensions supplied by the
App. Server time and the configured night window control timer deep sleep.

The first USB test should be performed with deep sleep disabled. The full
Arduino preparation, wiring precautions, secrets file and commissioning steps
are documented in `firmware/ee02_photo_frame/README.md`.

## Operational behaviour

- Album metadata refreshes at startup and then at the configured interval.
- Newly discovered photos are shown before already-used photos.
- Afterwards selection is random, excluding the immediately previous image.
- Originals and rendered files are cached in the persistent App data volume.
- A failed album refresh preserves the cache and the last rendered frame.
- The controller, not Home Assistant, owns deep sleep. The App exposes the
  configured frame and night intervals through `/api/device/config`.
- Smart Crop accepts a configurable 0–40% of unused display area. At the 15%
  default it keeps the full photo when that already fills at least 85% of the
  display; otherwise it crops only enough to reach 85% coverage. A value of 0%
  forces a borderless crop, while larger values preserve more of the photo.
- Dithering strength is configurable from 0–100%. A value of 0% produces calm,
  hard colour areas; 100% uses full Floyd-Steinberg error diffusion. The 50%
  default first moves colours closer to the Spectra 6 palette and then applies
  error diffusion, which usually gives photos and faces a less grainy result.

## Privacy and limitations

Anyone with the Google Photos share link can view that album. Google does not
offer a supported API for reading arbitrary shared albums, so the source adapter
uses Google's public web endpoint. It is isolated behind `PhotoSource`; if
Google changes the endpoint, only that adapter should need an update.
