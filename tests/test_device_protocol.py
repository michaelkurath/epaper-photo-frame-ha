from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frame_app.config import Settings
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
        self.assertEqual(config["server_time"], 123)
        self.assertEqual((config["width"], config["height"]), (1600, 1200))
        self.assertEqual(config["raw_size_bytes"], 1600 * 1200 // 2)
        self.assertEqual(len(config["palette_rgb"]), 6)
        self.assertEqual(config["frame_interval_seconds"], 4 * 3600)


if __name__ == "__main__":
    unittest.main()
