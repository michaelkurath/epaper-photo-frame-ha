from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EE02 = ROOT / "firmware" / "ee02_photo_frame"
EE04 = ROOT / "firmware" / "ee04_photo_frame"


class FirmwareSourceTests(unittest.TestCase):
    def test_drivers_target_exact_supported_panel_combinations(self) -> None:
        profiles = (
            (EE02, "510", "EE02", "spectra_13_3_ee02", "1200", "1600"),
            (EE04, "509", "EE04", "spectra_7_3_ee04", "480", "800"),
        )
        for folder, combo, board, model, width, height in profiles:
            with self.subTest(board=board):
                source = (folder / "driver.h").read_text(encoding="utf-8")
                self.assertIn(f"#define BOARD_SCREEN_COMBO {combo}", source)
                self.assertIn(f"#define USE_XIAO_EPAPER_DISPLAY_BOARD_{board}", source)
                self.assertIn(f'#define PHOTO_FRAME_DISPLAY_MODEL "{model}"', source)
                self.assertIn(f"#define PHOTO_FRAME_PORTRAIT_WIDTH {width}", source)
                self.assertIn(f"#define PHOTO_FRAME_PORTRAIT_HEIGHT {height}", source)

    def test_all_device_api_routes_are_present(self) -> None:
        for folder in (EE02, EE04):
            source = (folder / f"{folder.name}.ino").read_text(encoding="utf-8")
            for route in (
                "/api/device/config",
                "/api/device/current.raw",
                "/api/device/next.raw",
                "/api/device/report",
            ):
                self.assertIn(route, source)

    def test_display_refresh_happens_only_after_complete_frame_check(self) -> None:
        for folder in (EE02, EE04):
            source = (folder / f"{folder.name}.ino").read_text(encoding="utf-8")
            size_check = source.index("received != config.rawSize")
            update = source.index("epaper.update()")
            self.assertLess(size_check, update)

    def test_palette_order_matches_server_protocol(self) -> None:
        source = (EE02 / "ee02_photo_frame.ino").read_text(encoding="utf-8")
        expected = "TFT_WHITE, TFT_BLACK, TFT_RED, TFT_YELLOW, TFT_BLUE, TFT_GREEN"
        self.assertIn(expected, source)

    def test_firmware_rejects_a_server_profile_for_the_other_panel(self) -> None:
        source = (EE04 / "ee04_photo_frame.ino").read_text(encoding="utf-8")
        self.assertIn('document["display_model"]', source)
        self.assertIn("config.displayModel != PHOTO_FRAME_DISPLAY_MODEL", source)
        self.assertIn("PHOTO_FRAME_PORTRAIT_WIDTH", source)

    def test_controller_sources_stay_in_sync(self) -> None:
        self.assertEqual(
            (EE02 / "ee02_photo_frame.ino").read_bytes(),
            (EE04 / "ee04_photo_frame.ino").read_bytes(),
        )
        self.assertEqual(
            (EE02 / "firmware_core.h").read_bytes(),
            (EE04 / "firmware_core.h").read_bytes(),
        )

    def test_real_secrets_file_is_ignored(self) -> None:
        ignores = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for folder in (EE02, EE04):
            relative = f"firmware/{folder.name}/secrets.h"
            self.assertIn(relative, ignores.splitlines())
            self.assertFalse((folder / "secrets.h").exists())


if __name__ == "__main__":
    unittest.main()
