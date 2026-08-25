# Changelog

## 0.3.1 - 2026-08-25

- Bundle the OpenCV Haar cascade because Alpine's `py3-opencv` package does not
  include the `cv2.data` cascade directory.
- Fall back to detail-aware Smart Crop if face detection is unavailable.
- Return and display useful JSON errors instead of a browser JSON parse error.

## 0.3.0 - 2026-08-25

- Add local OpenCV face detection and detail-aware Smart Crop.
- Keep groups of detected faces visible or fall back to the full image.
- Add persistent per-photo manual focus points through the dashboard.
- Apply gentle contrast and colour optimisation before six-colour conversion.

## 0.2.1 - 2026-08-25

- Add an in-dashboard controller simulator for the token-protected device API.
- Show controller configuration, frame identity, format, and download size.

## 0.2.0 - 2026-08-25

- Add previous, next, and random-photo controls to the dashboard.
- Show the active portrait/landscape and cover/contain settings in the dashboard.

## 0.1.2 - 2026-08-25

- Avoid the AppArmor-blocked Nginx ownership change during startup.
- Send early Nginx startup diagnostics directly to standard error.

## 0.1.1 - 2026-08-24

- Run Nginx with its PID, logs and temporary files in writable locations so
  the App starts correctly under the Home Assistant container permissions.

## 0.1.0 - 2026-08-24

- Initial Home Assistant App scaffold.
- Public Google Photos adapter with paginated RPC extraction.
- SQLite catalogue, new-photo-first selection, and no immediate repeats.
- Six-colour PNG and packed 4-bit RAW output.
- Ingress dashboard plus isolated token-protected device API.
