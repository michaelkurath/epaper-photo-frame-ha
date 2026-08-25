from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from frame_app.image_pipeline import ImagePipeline, SPECTRA6_PALETTE


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
                self.assertTrue(set(rgb.getdata()).issubset(set(SPECTRA6_PALETTE)))

    def test_raw_output_packs_two_pixels_per_byte(self) -> None:
        with TemporaryDirectory() as temporary:
            pipeline = ImagePipeline((120, 160), fit_mode="cover", dither=False)
            png = Path(temporary) / "frame.png"
            raw = Path(temporary) / "frame.raw"
            pipeline.render_png(source_image(), png)
            pipeline.png_to_raw(png, raw)
            self.assertEqual(raw.stat().st_size, 120 * 160 // 2)

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


if __name__ == "__main__":
    unittest.main()
