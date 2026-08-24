# ePaper Photo Frame for Home Assistant

A private Home Assistant App repository for a battery-powered, 13.3-inch
Spectra 6 photo frame. The App reads a public shared Google Photos album,
caches metadata and images, converts photos to the six-colour display palette,
and serves the next frame to an ESP32-based display controller.

The Google Photos album URL and device API token are runtime options. They are
not committed to this repository.

## Repository layout

- `epaper_photo_frame/`: installable Home Assistant App
- `tests/`: parser, selection and image-pipeline tests
- `.github/workflows/`: GitHub Actions checks

See [epaper_photo_frame/DOCS.md](epaper_photo_frame/DOCS.md) for installation
and configuration.

The intended private repository is
`https://github.com/michaelkurath/epaper-photo-frame-ha`. Keep it private as
source control and deploy the App through Samba's `local_apps` share. Direct
App-store repository URLs are best suited to repositories that Home Assistant
can fetch without an interactive GitHub login.
