# ePaper Photo Frame for Home Assistant

A Home Assistant App repository for a battery-powered, 13.3-inch
Spectra 6 photo frame. The App reads a public shared Google Photos album,
caches metadata and images, converts photos to the six-colour display palette,
and serves the next frame to an ESP32-based display controller.

The Google Photos album URL and device API token are runtime options. They are
not committed to this repository.

## Repository layout

- `epaper_photo_frame/`: installable Home Assistant App
- `firmware/ee02_photo_frame/`: first EE02/XIAO ESP32-S3 Plus controller firmware
- `firmware/tests/`: hardware-independent controller logic tests
- `tests/`: parser, selection and image-pipeline tests
- `.github/workflows/`: GitHub Actions checks

See [epaper_photo_frame/DOCS.md](epaper_photo_frame/DOCS.md) for installation
and configuration. See
[firmware/ee02_photo_frame/README.md](firmware/ee02_photo_frame/README.md) for
the exact controller hardware, Arduino setup, first flash, and safety notes.

Add the public repository
`https://github.com/michaelkurath/epaper-photo-frame-ha` directly to the Home
Assistant App store. For local development, deployment through Samba's
`local_apps` share remains available as an alternative.
