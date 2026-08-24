# ePaper Photo Frame

## Installation from a private GitHub repository

1. Create the private repository
   `https://github.com/michaelkurath/epaper-photo-frame-ha` and push the complete
   contents of this package to it.
2. In Home Assistant install the official **Samba share** App under
   **Settings → Apps → Install app**.
3. In the Samba configuration set a separate username and password and ensure
   the `local_apps` share is enabled. Save and start Samba.
4. In Windows Explorer open `\\homeassistant.local` or `\\HOME_ASSISTANT_IP`,
   sign in with the Samba credentials, and open `local_apps`.
5. Copy the complete `epaper_photo_frame` directory into `local_apps`. The
   result in Windows must be
   `local_apps\\epaper_photo_frame\\config.yaml`—avoid an accidental second
   nested `epaper_photo_frame` folder.
6. In **Settings → Apps → App store**, refresh/check for updates under the local
   Apps section, then install **ePaper Photo Frame**.

The included `scripts/deploy-local.sh` can perform step 5 when `local_apps` is
mounted as a normal directory on a development computer.

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

- `GET /api/device/config`: display geometry, sleep interval, and night pause.
- `GET /api/device/current.png`: current rendered frame, without advancing.
- `POST /api/device/next.png`: select and return the next rendered frame.
- `POST /api/device/next.raw`: the same frame as packed 4-bit palette indices.

RAW data contains two pixels per byte: the first pixel in the high nibble and
the second in the low nibble. Palette indices are `0 white`, `1 black`, `2 red`,
`3 yellow`, `4 blue`, `5 green`. The final mapping to the EE02 driver remains a
firmware concern so it can be changed without touching the album or rendering
modules.

## Operational behaviour

- Album metadata refreshes at startup and then at the configured interval.
- Newly discovered photos are shown before already-used photos.
- Afterwards selection is random, excluding the immediately previous image.
- Originals and rendered files are cached in the persistent App data volume.
- A failed album refresh preserves the cache and the last rendered frame.
- The controller, not Home Assistant, owns deep sleep. The App exposes the
  configured frame and night intervals through `/api/device/config`.

## Privacy and limitations

Anyone with the Google Photos share link can view that album. Google does not
offer a supported API for reading arbitrary shared albums, so the source adapter
uses Google's public web endpoint. It is isolated behind `PhotoSource`; if
Google changes the endpoint, only that adapter should need an update.
