# ePaper Photo Frame for Home Assistant

A Home Assistant App repository for a battery-powered Spectra 6 photo frame.
It supports the 7.3-inch 800 x 480 panel with EE04 and the 13.3-inch
1200 x 1600 panel with EE02. The App reads a public shared Google Photos album,
caches metadata and images, converts photos to the six-colour display palette,
and serves the next frame to an ESP32-based display controller.

The Google Photos album URL and device API token are runtime options. They are
not committed to this repository.

## Repository layout

- `epaper_photo_frame/`: installable Home Assistant App
- `firmware/ee02_photo_frame/`: EE02 firmware for the 13.3-inch panel
- `firmware/ee04_photo_frame/`: EE04 firmware for the 7.3-inch panel
- `firmware/tests/`: hardware-independent controller logic tests
- `tests/`: parser, selection and image-pipeline tests
- `.github/workflows/`: GitHub Actions checks

See [epaper_photo_frame/DOCS.md](epaper_photo_frame/DOCS.md) for installation
and configuration. The controller folders contain the exact hardware profile,
Arduino setup, first-flash instructions, and safety notes for each panel.

Add the public repository
`https://github.com/michaelkurath/epaper-photo-frame-ha` directly to the Home
Assistant App store. For local development, deployment through Samba's
`local_apps` share remains available as an alternative.

## Security

The controller API on port `8080` currently uses HTTP with a bearer token and
is intended only for a trusted local network. Do not forward this port through
a router or expose it to the internet. See [SECURITY.md](SECURITY.md) for the
supported-version policy and private vulnerability-reporting instructions.

## License and third-party software

Original project code is licensed under the [MIT License](LICENSE), copyright
2026 Michael Kurath. Direct dependencies, build-time firmware libraries, and
the bundled OpenCV face-detector data retain their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Home Assistant, Google Photos, Seeed Studio, Spectra, Arduino, ESP32, and other
names are used only to identify compatible products and services. This
independent project is not endorsed by or affiliated with their respective
owners.
