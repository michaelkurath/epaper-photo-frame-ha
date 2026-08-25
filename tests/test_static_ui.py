from pathlib import Path
import unittest


HTML = (
    Path(__file__).parents[1]
    / "epaper_photo_frame"
    / "app"
    / "frame_app"
    / "static"
    / "index.html"
).read_text(encoding="utf-8")


class StaticUiTests(unittest.TestCase):
    def test_image_quality_controls_are_present(self) -> None:
        for control_id in ("fitMode", "unusedArea", "ditherStrength", "clearFocus"):
            with self.subTest(control_id=control_id):
                self.assertIn(f'id="{control_id}"', HTML)
        for strength in ("0", "25", "50", "75", "100"):
            self.assertIn(f'<option value="{strength}"', HTML)

    def test_controller_simulator_uses_real_device_endpoints(self) -> None:
        for endpoint in (
            "api/device/config",
            "api/device/report",
            "api/device/${useNext ? 'next' : 'current'}.raw",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, HTML)
        self.assertIn("Authorization: 'Bearer '", HTML)
        self.assertIn('id="displayProfile"', HTML)
        self.assertIn("spectra_7_3_ee04", HTML)

    def test_simulator_checks_raw_size_and_reports_lifecycle(self) -> None:
        self.assertIn("bytes.length !== config.raw_size_bytes", HTML)
        for status in ("awake", "displayed", "sleeping", "error"):
            self.assertIn(f"reportDevice('{status}'", HTML)
        self.assertIn("isNightTime(simulator.virtualTime, config)", HTML)


if __name__ == "__main__":
    unittest.main()
