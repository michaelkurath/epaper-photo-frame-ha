# Changelog

## 0.6.0 - 2026-08-25

- Add selectable `spectra_7_3_ee04` and `spectra_13_3_ee02` hardware profiles.
- Render the 7.3-inch panel at 800 x 480 or 480 x 800 with an exact 192,000-byte
  packed RAW frame while preserving the 13.3-inch 960,000-byte format.
- Keep existing installations on the 13.3-inch profile by default.
- Add an EE04/P073_SP6 firmware variant and validate the server profile before
  any physical display refresh.
- Separate rendered-frame caches by display profile and show the active panel
  and resolution in the dashboard and controller simulator.
- Keep pixel iteration compatible with both the pinned Pillow 11.3 release and
  newer Pillow versions.

## 0.5.0 - 2026-08-25

- Add selectable 0%, 25%, 50%, 75%, and 100% dithering strengths.
- Use a softened Floyd-Steinberg source at partial strengths to reduce visible
  grain while retaining smoother photographic colour transitions.
- Apply the existing gentle contrast and colour enhancement consistently to
  Smart Crop, Cover, and Contain modes.
- Persist the dashboard selection and isolate every quality level in the
  rendered-frame cache.

## 0.4.2 - 2026-08-25

- Add a persistent 0–40% setting for unused display area in Smart Crop mode.
- Expose convenient percentage choices directly in the dashboard.
- Include the selected percentage in render cache keys so each setting is
  rendered independently.
- Keep 15% as the recommended default and allow 0% for a borderless crop.

## 0.4.1 - 2026-08-25

- Keep the complete photo when Contain already uses at least 85% of the screen.
- When more space would be unused, crop only enough to reach 85% coverage
  instead of zooming all the way to a borderless frame.
- Preserve face-aware and manual focus positioning within the gentler crop.
- Invalidate old rendered-frame cache keys so upgraded installations immediately
  use the new crop behaviour.

## 0.4.0 - 2026-08-25

- Replace the PNG API demo with a stateful, accelerated controller simulator.
- Validate the exact packed RAW data path used by the future ESP32 firmware.
- Simulate wake-up, configured night pauses, display refresh, and deep sleep.
- Add authenticated device telemetry and persist the latest controller state.
- Expose protocol version, RGB palette, expected RAW size, ETag, and frame size
  metadata through the device API.

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
