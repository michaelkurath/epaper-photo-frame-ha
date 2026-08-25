from __future__ import annotations


from io import BytesIO
from pathlib import Path
from typing import Callable


from PIL import Image, ImageEnhance, ImageFilter, ImageOps




FaceBox = tuple[float, float, float, float]
FaceDetector = Callable[[Image.Image], list[FaceBox]]




SPECTRA6_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 255, 255),
    (0, 0, 0),
    (220, 30, 30),
    (250, 210, 20),
    (25, 80, 190),
    (35, 145, 70),
)


# Smart Crop may leave slim borders instead of discarding more of the photo.
# Cropping starts only when a contained image would use less than this share of
# the target display, and then removes only enough material to reach it.
SMART_DEFAULT_UNUSED_PERCENT = 15
DITHER_DEFAULT_STRENGTH = 50
RENDER_CACHE_VERSION = "quality-v1"




class ImagePipeline:
    def __init__(
        self,
        dimensions: tuple[int, int],
        *,
        fit_mode: str = "cover",
        dither: bool = True,
        dither_strength: int = DITHER_DEFAULT_STRENGTH,
        smart_unused_percent: int = SMART_DEFAULT_UNUSED_PERCENT,
        focus_point: tuple[float, float] | None = None,
        face_detector: FaceDetector | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.fit_mode = fit_mode
        self.dither = dither
        self.dither_strength = dither_strength
        self.smart_unused_percent = smart_unused_percent
        self.smart_target_coverage = 1.0 - smart_unused_percent / 100
        self.focus_point = focus_point
        self.face_detector = face_detector or self._detect_faces_opencv
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")
        if focus_point and not all(0.0 <= value <= 1.0 for value in focus_point):
            raise ValueError("focus_point coordinates must be between 0 and 1")


    @staticmethod
    def _palette_image() -> Image.Image:
        palette = Image.new("P", (1, 1))
        flat = [channel for colour in SPECTRA6_PALETTE for channel in colour]
        palette.putpalette(flat + [0] * (768 - len(flat)))
        return palette


    @staticmethod
    def _detect_faces_opencv(image: Image.Image) -> list[FaceBox]:
        try:
            import cv2
            import numpy as np
        except (ImportError, RuntimeError):
            return []


        bundled = Path(__file__).parent / "data" / "haarcascade_frontalface_default.xml"
        cv2_data = getattr(cv2, "data", None)
        candidates = [bundled]
        if cv2_data is not None:
            haarcascades = getattr(cv2_data, "haarcascades", "")
            if haarcascades:
                candidates.append(Path(haarcascades) / bundled.name)
        cascade_path = next((path for path in candidates if path.is_file()), None)
        if cascade_path is None:
            return []


        try:
            classifier = cv2.CascadeClassifier(str(cascade_path))
            if classifier.empty():
                return []
            scale = min(1.0, 900 / max(image.size))
            sample = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
            gray = cv2.cvtColor(np.asarray(sample), cv2.COLOR_RGB2GRAY)
            detected = classifier.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(28, 28)
            )
            return [
                (
                    x / sample.width,
                    y / sample.height,
                    (x + w) / sample.width,
                    (y + h) / sample.height,
                )
                for x, y, w, h in detected
            ]
        except Exception:
            # Face detection is an enhancement. Smart Crop must still fall back
            # to detail analysis if a platform OpenCV build cannot run it.
            return []


    @staticmethod
    def _detail_focus(image: Image.Image) -> tuple[float, float]:
        sample = ImageOps.grayscale(image).resize((64, 64), Image.Resampling.LANCZOS)
        edges = sample.filter(ImageFilter.FIND_EDGES)
        values = list(_pixel_values(edges))
        total = sum(values)
        if total <= 0:
            return (0.5, 0.5)
        x = sum((index % 64 + 0.5) * value for index, value in enumerate(values)) / total
        y = sum((index // 64 + 0.5) * value for index, value in enumerate(values)) / total
        return (x / 64, y / 64)


    def _smart_crop(self, image: Image.Image) -> Image.Image:
        target_ratio = self.dimensions[0] / self.dimensions[1]
        source_ratio = image.width / image.height
        contained_coverage = min(source_ratio, target_ratio) / max(
            source_ratio, target_ratio
        )
        if contained_coverage >= self.smart_target_coverage:
            return self._contain(self._enhance(image))


        if source_ratio > target_ratio:
            crop_height = image.height
            crop_width = crop_height * target_ratio / self.smart_target_coverage
        else:
            crop_width = image.width
            crop_height = crop_width / (target_ratio * self.smart_target_coverage)


        faces = self.face_detector(image)
        use_contain = False
        if self.focus_point:
            focus_x, focus_y = self.focus_point
        elif faces:
            left = max(0.0, min(box[0] for box in faces) - 0.08)
            top = max(0.0, min(box[1] for box in faces) - 0.12)
            right = min(1.0, max(box[2] for box in faces) + 0.08)
            bottom = min(1.0, max(box[3] for box in faces) + 0.16)
            focus_x, focus_y = ((left + right) / 2, (top + bottom) / 2)
            required_width = (right - left) * image.width
            required_height = (bottom - top) * image.height
            use_contain = required_width > crop_width or required_height > crop_height
        else:
            focus_x, focus_y = self._detail_focus(image)


        if use_contain:
            return self._contain(self._enhance(image))
        left_px = min(max(focus_x * image.width - crop_width / 2, 0), image.width - crop_width)
        top_px = min(max(focus_y * image.height - crop_height / 2, 0), image.height - crop_height)
        cropped = image.crop(
            (round(left_px), round(top_px), round(left_px + crop_width), round(top_px + crop_height))
        )
        return self._contain(self._enhance(cropped))


    @staticmethod
    def _enhance(image: Image.Image) -> Image.Image:
        enhanced = ImageOps.autocontrast(image, cutoff=1)
        enhanced = ImageEnhance.Contrast(enhanced).enhance(1.06)
        return ImageEnhance.Color(enhanced).enhance(1.04)


    def _contain(self, image: Image.Image) -> Image.Image:
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


    def _fit(self, image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if self.fit_mode == "smart":
            return self._smart_crop(image)
        if self.fit_mode == "cover":
            return self._enhance(
                ImageOps.fit(
                    image,
                    self.dimensions,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
            )
        return self._contain(self._enhance(image))


    def quantize(self, source: bytes) -> Image.Image:
        with Image.open(BytesIO(source)) as opened:
            fitted = self._fit(opened)
        if not self.dither or self.dither_strength == 0:
            return fitted.quantize(
                palette=self._palette_image(), dither=Image.Dither.NONE
            )
        if self.dither_strength < 100:
            nearest = fitted.quantize(
                palette=self._palette_image(), dither=Image.Dither.NONE
            ).convert("RGB")
            fitted = Image.blend(nearest, fitted, self.dither_strength / 100)
        return fitted.quantize(
            palette=self._palette_image(), dither=Image.Dither.FLOYDSTEINBERG
        )


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
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Callable

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


FaceBox = tuple[float, float, float, float]
FaceDetector = Callable[[Image.Image], list[FaceBox]]


SPECTRA6_PALETTE: tuple[tuple[int, int, int], ...] = (
    (255, 255, 255),
    (0, 0, 0),
    (220, 30, 30),
    (250, 210, 20),
    (25, 80, 190),
    (35, 145, 70),
)

# Smart Crop may leave slim borders instead of discarding more of the photo.
# Cropping starts only when a contained image would use less than this share of
# the target display, and then removes only enough material to reach it.
SMART_DEFAULT_UNUSED_PERCENT = 15
DITHER_DEFAULT_STRENGTH = 50
RENDER_CACHE_VERSION = "quality-v1"


class ImagePipeline:
    def __init__(
        self,
        dimensions: tuple[int, int],
        *,
        fit_mode: str = "cover",
        dither: bool = True,
        dither_strength: int = DITHER_DEFAULT_STRENGTH,
        smart_unused_percent: int = SMART_DEFAULT_UNUSED_PERCENT,
        focus_point: tuple[float, float] | None = None,
        face_detector: FaceDetector | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.fit_mode = fit_mode
        self.dither = dither
        self.dither_strength = dither_strength
        self.smart_unused_percent = smart_unused_percent
        self.smart_target_coverage = 1.0 - smart_unused_percent / 100
        self.focus_point = focus_point
        self.face_detector = face_detector or self._detect_faces_opencv
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")
        if focus_point and not all(0.0 <= value <= 1.0 for value in focus_point):
            raise ValueError("focus_point coordinates must be between 0 and 1")

    @staticmethod
    def _palette_image() -> Image.Image:
        palette = Image.new("P", (1, 1))
        flat = [channel for colour in SPECTRA6_PALETTE for channel in colour]
        palette.putpalette(flat + [0] * (768 - len(flat)))
        return palette

    @staticmethod
    def _detect_faces_opencv(image: Image.Image) -> list[FaceBox]:
        try:
            import cv2
            import numpy as np
        except (ImportError, RuntimeError):
            return []

        bundled = Path(__file__).parent / "data" / "haarcascade_frontalface_default.xml"
        cv2_data = getattr(cv2, "data", None)
        candidates = [bundled]
        if cv2_data is not None:
            haarcascades = getattr(cv2_data, "haarcascades", "")
            if haarcascades:
                candidates.append(Path(haarcascades) / bundled.name)
        cascade_path = next((path for path in candidates if path.is_file()), None)
        if cascade_path is None:
            return []

        try:
            classifier = cv2.CascadeClassifier(str(cascade_path))
            if classifier.empty():
                return []
            scale = min(1.0, 900 / max(image.size))
            sample = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
            gray = cv2.cvtColor(np.asarray(sample), cv2.COLOR_RGB2GRAY)
            detected = classifier.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(28, 28)
            )
            return [
                (
                    x / sample.width,
                    y / sample.height,
                    (x + w) / sample.width,
                    (y + h) / sample.height,
                )
                for x, y, w, h in detected
            ]
        except Exception:
            # Face detection is an enhancement. Smart Crop must still fall back
            # to detail analysis if a platform OpenCV build cannot run it.
            return []

    @staticmethod
    def _detail_focus(image: Image.Image) -> tuple[float, float]:
        sample = ImageOps.grayscale(image).resize((64, 64), Image.Resampling.LANCZOS)
        edges = sample.filter(ImageFilter.FIND_EDGES)
        values = list(edges.get_flattened_data())
        total = sum(values)
        if total <= 0:
            return (0.5, 0.5)
        x = sum((index % 64 + 0.5) * value for index, value in enumerate(values)) / total
        y = sum((index // 64 + 0.5) * value for index, value in enumerate(values)) / total
        return (x / 64, y / 64)

    def _smart_crop(self, image: Image.Image) -> Image.Image:
        target_ratio = self.dimensions[0] / self.dimensions[1]
        source_ratio = image.width / image.height
        contained_coverage = min(source_ratio, target_ratio) / max(
            source_ratio, target_ratio
        )
        if contained_coverage >= self.smart_target_coverage:
            return self._contain(self._enhance(image))

        if source_ratio > target_ratio:
            crop_height = image.height
            crop_width = crop_height * target_ratio / self.smart_target_coverage
        else:
            crop_width = image.width
            crop_height = crop_width / (target_ratio * self.smart_target_coverage)

        faces = self.face_detector(image)
        use_contain = False
        if self.focus_point:
            focus_x, focus_y = self.focus_point
        elif faces:
            left = max(0.0, min(box[0] for box in faces) - 0.08)
            top = max(0.0, min(box[1] for box in faces) - 0.12)
            right = min(1.0, max(box[2] for box in faces) + 0.08)
            bottom = min(1.0, max(box[3] for box in faces) + 0.16)
            focus_x, focus_y = ((left + right) / 2, (top + bottom) / 2)
            required_width = (right - left) * image.width
            required_height = (bottom - top) * image.height
            use_contain = required_width > crop_width or required_height > crop_height
        else:
            focus_x, focus_y = self._detail_focus(image)

        if use_contain:
            return self._contain(self._enhance(image))
        left_px = min(max(focus_x * image.width - crop_width / 2, 0), image.width - crop_width)
        top_px = min(max(focus_y * image.height - crop_height / 2, 0), image.height - crop_height)
        cropped = image.crop(
            (round(left_px), round(top_px), round(left_px + crop_width), round(top_px + crop_height))
        )
        return self._contain(self._enhance(cropped))

    @staticmethod
    def _enhance(image: Image.Image) -> Image.Image:
        enhanced = ImageOps.autocontrast(image, cutoff=1)
        enhanced = ImageEnhance.Contrast(enhanced).enhance(1.06)
        return ImageEnhance.Color(enhanced).enhance(1.04)

    def _contain(self, image: Image.Image) -> Image.Image:
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

    def _fit(self, image: Image.Image) -> Image.Image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if self.fit_mode == "smart":
            return self._smart_crop(image)
        if self.fit_mode == "cover":
            return self._enhance(
                ImageOps.fit(
                    image,
                    self.dimensions,
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
            )
        return self._contain(self._enhance(image))

    def quantize(self, source: bytes) -> Image.Image:
        with Image.open(BytesIO(source)) as opened:
            fitted = self._fit(opened)
        if not self.dither or self.dither_strength == 0:
            return fitted.quantize(
                palette=self._palette_image(), dither=Image.Dither.NONE
            )
        if self.dither_strength < 100:
            nearest = fitted.quantize(
                palette=self._palette_image(), dither=Image.Dither.NONE
            ).convert("RGB")
            fitted = Image.blend(nearest, fitted, self.dither_strength / 100)
        return fitted.quantize(
            palette=self._palette_image(), dither=Image.Dither.FLOYDSTEINBERG
        )

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
