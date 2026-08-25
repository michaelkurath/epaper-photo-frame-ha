from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frame_app.config import DISPLAY_MODEL_7_3, Settings
from frame_app.device_protocol import device_config_payload


class DeviceProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.settings = Settings(
            album_url="https://photos.google.com/share/example?key=test",
            api_token="0123456789abcdef",
            orientation="landscape",
            frame_interval_hours=4,
            night_start="23:00",
            night_end="07:00",
            data_dir=Path(self.temporary.name),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_config_describes_exact_raw_protocol(self) -> None:
        config = device_config_payload(self.settings, server_time=123)
        self.assertEqual(config["protocol_version"], 1)
        self.assertEqual(config["display_model"], "spectra_13_3_ee02")
        self.assertEqual(config["server_time"], 123)
        self.assertEqual((config["width"], config["height"]), (1600, 1200))
        self.assertEqual(config["raw_size_bytes"], 1600 * 1200 // 2)
        self.assertEqual(len(config["palette_rgb"]), 6)
        self.assertEqual(config["frame_interval_seconds"], 4 * 3600)

    def test_portrait_dimensions_and_night_window_are_reported(self) -> None:
        portrait = Settings(
            album_url=self.settings.album_url,
            api_token=self.settings.api_token,
            orientation="portrait",
            night_start="22:30",
            night_end="06:15",
            data_dir=Path(self.temporary.name),
        )
        config = device_config_payload(portrait, server_time=456)
        self.assertEqual((config["width"], config["height"]), (1200, 1600))
        self.assertEqual(config["raw_size_bytes"], 960_000)
        self.assertEqual(config["night_start"], "22:30")
        self.assertEqual(config["night_end"], "06:15")
        self.assertEqual(config["report_endpoint"], "/api/device/report")

    def test_palette_order_matches_raw_protocol(self) -> None:
        config = device_config_payload(self.settings, server_time=123)
        self.assertEqual(
            config["palette"], ["white", "black", "red", "yellow", "blue", "green"]
        )
        self.assertIn("high nibble first", config["raw_packing"])

    def test_7_3_inch_profile_reports_both_orientations(self) -> None:
        portrait = Settings(
            album_url=self.settings.album_url,
            api_token=self.settings.api_token,
            display_model=DISPLAY_MODEL_7_3,
            orientation="portrait",
            data_dir=Path(self.temporary.name),
        )
        portrait_config = device_config_payload(portrait, server_time=789)
        self.assertEqual((portrait_config["width"], portrait_config["height"]), (480, 800))
        self.assertEqual(portrait_config["raw_size_bytes"], 192_000)

        landscape_config = device_config_payload(
            Settings(
                album_url=portrait.album_url,
                api_token=portrait.api_token,
                display_model=DISPLAY_MODEL_7_3,
                orientation="landscape",
                data_dir=portrait.data_dir,
            ),
            server_time=790,
        )
        self.assertEqual(
            (landscape_config["width"], landscape_config["height"]), (800, 480)
        )
        self.assertEqual(landscape_config["raw_size_bytes"], 192_000)


if __name__ == "__main__":
    unittest.main()
