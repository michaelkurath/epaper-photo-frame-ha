from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = ROOT / "firmware" / "ee02_photo_frame"


class FirmwareSourceTests(unittest.TestCase):
    def test_driver_targets_exact_ee02_panel_combination(self) -> None:
        source = (FIRMWARE / "driver.h").read_text(encoding="utf-8")
        self.assertIn("#define BOARD_SCREEN_COMBO 510", source)
        self.assertIn("#define USE_XIAO_EPAPER_DISPLAY_BOARD_EE02", source)

    def test_all_device_api_routes_are_present(self) -> None:
        source = (FIRMWARE / "ee02_photo_frame.ino").read_text(encoding="utf-8")
        for route in (
            "/api/device/config",
            "/api/device/current.raw",
            "/api/device/next.raw",
            "/api/device/report",
        ):
            self.assertIn(route, source)

    def test_display_refresh_happens_only_after_complete_frame_check(self) -> None:
        source = (FIRMWARE / "ee02_photo_frame.ino").read_text(encoding="utf-8")
        size_check = source.index("received != config.rawSize")
        update = source.index("epaper.update()")
        self.assertLess(size_check, update)

    def test_palette_order_matches_server_protocol(self) -> None:
        source = (FIRMWARE / "ee02_photo_frame.ino").read_text(encoding="utf-8")
        expected = "TFT_WHITE, TFT_BLACK, TFT_RED, TFT_YELLOW, TFT_BLUE, TFT_GREEN"
        self.assertIn(expected, source)

    def test_real_secrets_file_is_ignored(self) -> None:
        ignores = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("firmware/ee02_photo_frame/secrets.h", ignores.splitlines())
        self.assertFalse((FIRMWARE / "secrets.h").exists())


if __name__ == "__main__":
    unittest.main()
