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


if __name__ == "__main__":
    unittest.main()
