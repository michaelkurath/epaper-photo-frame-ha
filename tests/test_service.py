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
                f"{RENDER_CACHE_VERSION}:photo-a:portrait:smart:15:1:50:auto".encode("utf-8")
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


if __name__ == "__main__":
    unittest.main()
