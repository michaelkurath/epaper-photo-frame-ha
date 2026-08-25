from io import BytesIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from frame_app.image_pipeline import (
    ImagePipeline,
    SMART_DEFAULT_UNUSED_PERCENT,
    SPECTRA6_PALETTE,
)


def source_image() -> bytes:
    image = Image.new("RGB", (80, 60))
    for y in range(image.height):
        for x in range(image.width):
            image.putpixel((x, y), (x * 3, y * 4, (x + y) * 2))
    buffer = BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


class ImagePipelineTests(unittest.TestCase):
    def test_renders_exact_dimensions_and_palette(self) -> None:
        with TemporaryDirectory() as temporary:
            pipeline = ImagePipeline((120, 160), fit_mode="contain", dither=True)
            output = Path(temporary) / "frame.png"
            pipeline.render_png(source_image(), output)
            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (120, 160))
                rgb = rendered.convert("RGB")
                self.assertTrue(
                    set(rgb.get_flattened_data()).issubset(set(SPECTRA6_PALETTE))
                )

    def test_raw_output_packs_two_pixels_per_byte(self) -> None:
        with TemporaryDirectory() as temporary:
            pipeline = ImagePipeline((120, 160), fit_mode="cover", dither=False)
            png = Path(temporary) / "frame.png"
            raw = Path(temporary) / "frame.raw"
            pipeline.render_png(source_image(), png)
            pipeline.png_to_raw(png, raw)
            self.assertEqual(raw.stat().st_size, 120 * 160 // 2)

    def test_7_3_inch_landscape_render_has_exact_panel_geometry_and_raw_size(self) -> None:
        with TemporaryDirectory() as temporary:
            pipeline = ImagePipeline((800, 480), fit_mode="smart", dither=True)
            png = Path(temporary) / "p073-frame.png"
            raw = Path(temporary) / "p073-frame.raw"
            pipeline.render_png(source_image(), png)
            pipeline.png_to_raw(png, raw)
            with Image.open(png) as rendered:
                self.assertEqual(rendered.size, (800, 480))
                self.assertTrue(
                    set(rendered.convert("RGB").get_flattened_data()).issubset(
                        set(SPECTRA6_PALETTE)
                    )
                )
            self.assertEqual(raw.stat().st_size, 192_000)

    def test_13_3_inch_portrait_render_keeps_existing_raw_format(self) -> None:
        with TemporaryDirectory() as temporary:
            pipeline = ImagePipeline((1200, 1600), fit_mode="contain", dither=False)
            png = Path(temporary) / "p133-frame.png"
            raw = Path(temporary) / "p133-frame.raw"
            pipeline.render_png(source_image(), png)
            pipeline.png_to_raw(png, raw)
            with Image.open(png) as rendered:
                self.assertEqual(rendered.size, (1200, 1600))
            self.assertEqual(raw.stat().st_size, 960_000)

    def test_dither_strength_produces_distinct_quality_levels(self) -> None:
        outputs = []
        for strength in (0, 50, 100):
            pipeline = ImagePipeline(
                (120, 160),
                fit_mode="contain",
                dither=strength > 0,
                dither_strength=strength,
            )
            outputs.append(pipeline.quantize(source_image()).convert("RGB").tobytes())
        self.assertNotEqual(outputs[0], outputs[1])
        self.assertNotEqual(outputs[1], outputs[2])

    def test_rejects_invalid_dither_strength(self) -> None:
        with self.assertRaises(ValueError):
            ImagePipeline((100, 100), dither_strength=101)

    def test_smart_crop_uses_manual_focus(self) -> None:
        image = Image.new("RGB", (200, 100), "red")
        for x in range(100, 200):
            for y in range(100):
                image.putpixel((x, y), (0, 0, 255))
        pipeline = ImagePipeline(
            (100, 100), fit_mode="smart", dither=False, focus_point=(0.85, 0.5)
        )
        fitted = pipeline._fit(image)
        red, _, blue = fitted.resize((1, 1)).getpixel((0, 0))
        self.assertGreater(blue, red)

    def test_smart_crop_contains_image_when_faces_do_not_fit(self) -> None:
        image = Image.new("RGB", (300, 100), "blue")
        detector = lambda _: [(0.02, 0.1, 0.20, 0.9), (0.80, 0.1, 0.98, 0.9)]
        pipeline = ImagePipeline(
            (100, 160), fit_mode="smart", dither=False, face_detector=detector
        )
        fitted = pipeline._fit(image)
        self.assertEqual(fitted.getpixel((50, 0)), SPECTRA6_PALETTE[0])
        self.assertEqual(fitted.getpixel((50, 159)), SPECTRA6_PALETTE[0])

    def test_smart_crop_keeps_full_image_when_screen_usage_is_high(self) -> None:
        image = Image.new("RGB", (100, 110), "blue")
        pipeline = ImagePipeline((100, 100), fit_mode="smart", dither=False)
        fitted = pipeline._fit(image)
        self.assertEqual(fitted.getpixel((0, 50)), SPECTRA6_PALETTE[0])
        self.assertNotEqual(fitted.getpixel((50, 50)), SPECTRA6_PALETTE[0])

    def test_smart_crop_leaves_small_borders_instead_of_full_zoom(self) -> None:
        image = Image.new("RGB", (200, 100), "blue")
        pipeline = ImagePipeline(
            (100, 100),
            fit_mode="smart",
            dither=False,
            face_detector=lambda _: [],
        )
        fitted = pipeline._fit(image)
        self.assertEqual(SMART_DEFAULT_UNUSED_PERCENT, 15)
        self.assertEqual(pipeline.smart_target_coverage, 0.85)
        self.assertEqual(fitted.getpixel((50, 0)), SPECTRA6_PALETTE[0])
        self.assertNotEqual(fitted.getpixel((50, 50)), SPECTRA6_PALETTE[0])

    def test_allowed_unused_percentage_controls_zoom_amount(self) -> None:
        image = Image.new("RGB", (200, 100), "blue")
        borderless = ImagePipeline(
            (100, 100),
            fit_mode="smart",
            dither=False,
            smart_unused_percent=0,
            face_detector=lambda _: [],
        )._fit(image)
        gentle = ImagePipeline(
            (100, 100),
            fit_mode="smart",
            dither=False,
            smart_unused_percent=30,
            face_detector=lambda _: [],
        )._fit(image)
        self.assertNotEqual(borderless.getpixel((50, 0)), SPECTRA6_PALETTE[0])
        self.assertEqual(gentle.getpixel((50, 0)), SPECTRA6_PALETTE[0])

    def test_rejects_invalid_unused_percentage(self) -> None:
        with self.assertRaises(ValueError):
            ImagePipeline((100, 100), fit_mode="smart", smart_unused_percent=41)

    def test_alpine_opencv_without_data_module_falls_back_safely(self) -> None:
        class EmptyClassifier:
            def __init__(self, _: str) -> None:
                pass

            @staticmethod
            def empty() -> bool:
                return True

        fake_cv2 = SimpleNamespace(CascadeClassifier=EmptyClassifier)
        with patch.dict(sys.modules, {"cv2": fake_cv2}):
            faces = ImagePipeline._detect_faces_opencv(
                Image.new("RGB", (100, 100), "white")
            )
        self.assertEqual(faces, [])


if __name__ == "__main__":
    unittest.main()
