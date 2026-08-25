import asyncio
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frame_app.config import Settings
from frame_app.image_pipeline import ImagePipeline, RENDER_CACHE_VERSION
from frame_app.service import FrameService
from frame_app.storage import Catalogue


class ServiceTests(unittest.TestCase):
    def test_render_cache_key_contains_pipeline_version(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(
                album_url="https://photos.google.com/share/example?key=test",
                api_token="0123456789abcdef",
                fit_mode="smart",
                orientation="portrait",
                dither=True,
                data_dir=root,
            )
            service = FrameService(
                settings,
                source=None,  # type: ignore[arg-type]
                catalogue=Catalogue(root / "catalogue.sqlite3"),
                pipeline=ImagePipeline(settings.dimensions, fit_mode="smart"),
            )
            _, png, raw = service._paths("photo-a")
            expected = hashlib.sha256(
                f"{RENDER_CACHE_VERSION}:photo-a:spectra_13_3_ee02:portrait:smart:15:1:50:auto".encode("utf-8")
            ).hexdigest()
            self.assertEqual(png.name, f"{expected}.png")
            self.assertEqual(raw.name, f"{expected}.raw")

            asyncio.run(service.set_display_options("landscape", "smart", 25, 75))
            self.assertEqual(service.settings.smart_unused_percent, 25)
            self.assertEqual(service.settings.dither_strength, 75)
            self.assertEqual(
                service.catalogue.get_state("display_smart_unused_percent"), "25"
            )
            self.assertEqual(
                service.catalogue.get_state("display_dither_strength"), "75"
            )

    def test_download_url_accepts_only_googleusercontent_https(self) -> None:
        self.assertEqual(
            FrameService._download_url("https://lh3.googleusercontent.com/photo"),
            "https://lh3.googleusercontent.com/photo=w2400-h2400",
        )
        self.assertEqual(
            FrameService._download_url(
                "https://lh3.googleusercontent.com/photo=w1200-h800"
            ),
            "https://lh3.googleusercontent.com/photo=w1200-h800",
        )
        for url in (
            "http://lh3.googleusercontent.com/photo",
            "https://googleusercontent.com.example.net/photo",
            "https://example.com/photo",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                FrameService._download_url(url)

    def test_render_cache_separates_focus_and_quality_options(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(
                album_url="https://photos.google.com/share/example?key=test",
                api_token="0123456789abcdef",
                fit_mode="smart",
                orientation="portrait",
                dither=True,
                data_dir=root,
            )
            catalogue = Catalogue(root / "catalogue.sqlite3")
            service = FrameService(
                settings,
                source=None,  # type: ignore[arg-type]
                catalogue=catalogue,
                pipeline=ImagePipeline(settings.dimensions, fit_mode="smart"),
            )
            default_png = service._paths("photo-a")[1]
            catalogue.set_focus("photo-a", 0.2, 0.8)
            focused_png = service._paths("photo-a")[1]
            asyncio.run(service.set_display_options("portrait", "smart", 25, 75))
            quality_png = service._paths("photo-a")[1]
            self.assertEqual(len({default_png.name, focused_png.name, quality_png.name}), 3)

    def test_display_options_reject_invalid_values_without_mutation(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(
                album_url="https://photos.google.com/share/example?key=test",
                api_token="0123456789abcdef",
                data_dir=root,
            )
            service = FrameService(
                settings,
                source=None,  # type: ignore[arg-type]
                catalogue=Catalogue(root / "catalogue.sqlite3"),
                pipeline=ImagePipeline(settings.dimensions),
            )
            invalid = (
                ("diagonal", "smart", 15, 50),
                ("portrait", "stretch", 15, 50),
                ("portrait", "smart", 41, 50),
                ("portrait", "smart", 15, -1),
            )
            for values in invalid:
                with self.subTest(values=values), self.assertRaises(ValueError):
                    asyncio.run(service.set_display_options(*values))
            self.assertEqual(service.settings, settings)

    def test_status_exposes_active_render_settings(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = Settings(
                album_url="https://photos.google.com/share/example?key=test",
                api_token="0123456789abcdef",
                orientation="landscape",
                fit_mode="contain",
                smart_unused_percent=20,
                dither=True,
                dither_strength=25,
                data_dir=root,
            )
            service = FrameService(
                settings,
                source=None,  # type: ignore[arg-type]
                catalogue=Catalogue(root / "catalogue.sqlite3"),
                pipeline=ImagePipeline(settings.dimensions),
            )
            status = service.status()
            self.assertEqual(status["display_model"], "spectra_13_3_ee02")
            self.assertEqual((status["width"], status["height"]), (1600, 1200))
            self.assertEqual(status["fit_mode"], "contain")
            self.assertEqual(status["smart_unused_percent"], 20)
            self.assertEqual(status["dither_strength"], 25)


if __name__ == "__main__":
    unittest.main()
