import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from frame_app.config import DISPLAY_MODEL_13_3, DISPLAY_MODEL_7_3, Settings


class ConfigTests(unittest.TestCase):
    def test_loads_home_assistant_options(self) -> None:
        with TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            options = tmp_path / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "0123456789abcdef",
                        "display_model": DISPLAY_MODEL_7_3,
                        "orientation": "landscape",
                        "smart_unused_percent": 25,
                        "dither_strength": 75,
                        "dither": False,
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                "EPAPER_OPTIONS_FILE": str(options),
                "EPAPER_DATA_DIR": str(tmp_path),
            }
            with patch.dict(os.environ, environment, clear=False):
                settings = Settings.load()
            self.assertEqual(settings.display_model, DISPLAY_MODEL_7_3)
            self.assertEqual(settings.dimensions, (800, 480))
            self.assertEqual(settings.smart_unused_percent, 25)
            self.assertEqual(settings.dither_strength, 75)
            self.assertFalse(settings.dither)

    def test_rejects_invalid_unused_percentage(self) -> None:
        with TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "0123456789abcdef",
                        "smart_unused_percent": 41,
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"EPAPER_OPTIONS_FILE": str(options)}, clear=False):
                with self.assertRaises(ValueError):
                    Settings.load()

    def test_rejects_short_device_token(self) -> None:
        with TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "short",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"EPAPER_OPTIONS_FILE": str(options)}, clear=False):
                with self.assertRaises(ValueError):
                    Settings.load()

    def test_rejects_invalid_dither_strength(self) -> None:
        with TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "0123456789abcdef",
                        "dither_strength": 101,
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"EPAPER_OPTIONS_FILE": str(options)}, clear=False):
                with self.assertRaises(ValueError):
                    Settings.load()

    def test_existing_install_defaults_to_13_3_inch_profile(self) -> None:
        with TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "0123456789abcdef",
                        "orientation": "portrait",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"EPAPER_OPTIONS_FILE": str(options)}, clear=False):
                settings = Settings.load()
            self.assertEqual(settings.display_model, DISPLAY_MODEL_13_3)
            self.assertEqual(settings.dimensions, (1200, 1600))

    def test_environment_overrides_home_assistant_options(self) -> None:
        with TemporaryDirectory() as temporary:
            options = Path(temporary) / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "album_url": "https://photos.google.com/share/example?key=test",
                        "api_token": "0123456789abcdef",
                        "orientation": "portrait",
                        "fit_mode": "cover",
                        "dither": True,
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                "EPAPER_OPTIONS_FILE": str(options),
                "EPAPER_ORIENTATION": "landscape",
                "EPAPER_FIT_MODE": "smart",
                "EPAPER_DITHER": "off",
            }
            with patch.dict(os.environ, environment, clear=False):
                settings = Settings.load()
            self.assertEqual(settings.orientation, "landscape")
            self.assertEqual(settings.fit_mode, "smart")
            self.assertFalse(settings.dither)

    def test_rejects_invalid_orientation_and_fit_mode(self) -> None:
        base = {
            "album_url": "https://photos.google.com/share/example?key=test",
            "api_token": "0123456789abcdef",
        }
        for name, value in (
            ("orientation", "diagonal"),
            ("fit_mode", "stretch"),
            ("display_model", "unknown_panel"),
        ):
            with self.subTest(name=name), TemporaryDirectory() as temporary:
                options = Path(temporary) / "options.json"
                options.write_text(json.dumps({**base, name: value}), encoding="utf-8")
                with patch.dict(
                    os.environ, {"EPAPER_OPTIONS_FILE": str(options)}, clear=False
                ):
                    with self.assertRaises(ValueError):
                        Settings.load()


if __name__ == "__main__":
    unittest.main()
