from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


SPECTRA6_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 255, 255),
    (0, 0, 0),
    (220, 30, 30),
    (250, 210, 20),
    (25, 80, 190),
    (35, 145, 70),
)


class ImagePipeline:
    def __init__(
        self,
        dimensions: tuple[int, int],
        *,
        fit_mode: str = "cover",
        dither: bool = True,
    ) -> None:
        self.dimensions = dimensions
        self.fit_mode = fit_mode
        self.dither = dither
        if fit_mode not in {"cover", "contain"}:
            raise ValueError("fit_mode must be cover or contain")

    @staticmethod
    def _palette_image() -> Image.Image:
        palette = Image.new("P", (1, 1))
        flat = [channel for colour in SPECTRA6_PALETTE for channel in colour]
        palette.putpalette(flat + [0] * (768 - len(flat)))
        return palette

    def _fit(self, image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if self.fit_mode == "cover":
            return ImageOps.fit(
                image,
                self.dimensions,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        contained = ImageOps.contain(
            image, self.dimensions, method=Image.Resampling.LANCZOS
        )
        canvas = Image.new("RGB", self.dimensions, SPECTRA6_PALETTE[0])
        position = (
            (self.dimensions[0] - contained.width) // 2,
            (self.dimensions[1] - contained.height) // 2,
        )
        canvas.paste(contained, position)
        return canvas

    def quantize(self, source: bytes) -> Image.Image:
        with Image.open(BytesIO(source)) as opened:
            fitted = self._fit(opened)
        dither = Image.Dither.FLOYDSTEINBERG if self.dither else Image.Dither.NONE
        return fitted.quantize(palette=self._palette_image(), dither=dither)

    def render_png(self, source: bytes, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        image = self.quantize(source)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        image.save(temporary, format="PNG", optimize=True)
        temporary.replace(destination)

    @staticmethod
    def png_to_raw(png_path: Path, destination: Path) -> None:
        with Image.open(png_path) as opened:
            image = opened.convert("P")
            pixels = image.tobytes()
        packed = bytearray((len(pixels) + 1) // 2)
        for index in range(0, len(pixels), 2):
            high = pixels[index] & 0x0F
            low = pixels[index + 1] & 0x0F if index + 1 < len(pixels) else 0
            packed[index // 2] = (high << 4) | low
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(packed)
        temporary.replace(destination)

