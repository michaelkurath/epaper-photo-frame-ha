from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from frame_app.config import Settings
from frame_app.image_pipeline import ImagePipeline, RENDER_CACHE_VERSION
from frame_app.models import StoredPhoto
from frame_app.sources.base import PhotoSource
from frame_app.storage import Catalogue


class FrameService:
    def __init__(
        self,
        settings: Settings,
        source: PhotoSource,
        catalogue: Catalogue,
        pipeline: ImagePipeline,
    ) -> None:
        self.settings = settings
        self.source = source
        self.catalogue = catalogue
        self.pipeline = pipeline
        self.original_dir = settings.data_dir / "cache" / "original"
        self.render_dir = settings.data_dir / "cache" / "rendered"
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._sync_lock = asyncio.Lock()
        self._frame_lock = asyncio.Lock()

    @staticmethod
    def _cache_key(photo_id: str) -> str:
        return hashlib.sha256(photo_id.encode("utf-8")).hexdigest()

    def _paths(self, photo_id: str) -> tuple[Path, Path, Path]:
        key = self._cache_key(photo_id)
        focus = self.catalogue.get_focus(photo_id)
        focus_key = "auto" if focus is None else f"{focus[0]:.6f},{focus[1]:.6f}"
        render_key = self._cache_key(
            f"{RENDER_CACHE_VERSION}:{photo_id}:{self.settings.display_model}:"
            f"{self.settings.orientation}:"
            f"{self.settings.fit_mode}:"
            f"{self.settings.smart_unused_percent}:{int(self.settings.dither)}:"
            f"{self.settings.dither_strength}:{focus_key}"
        )
        return (
            self.original_dir / f"{key}.image",
            self.render_dir / f"{render_key}.png",
            self.render_dir / f"{render_key}.raw",
        )

    async def set_display_options(
        self,
        orientation: str,
        fit_mode: str,
        smart_unused_percent: int,
        dither_strength: int,
    ) -> None:
        if orientation not in {"portrait", "landscape"}:
            raise ValueError("orientation must be portrait or landscape")
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")
        async with self._frame_lock:
            self.settings = replace(
                self.settings,
                orientation=orientation,
                fit_mode=fit_mode,
                smart_unused_percent=smart_unused_percent,
                dither=dither_strength > 0,
                dither_strength=dither_strength,
            )
            self.pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
            )
            self.catalogue.set_state("display_orientation", orientation)
            self.catalogue.set_state("display_fit_mode", fit_mode)
            self.catalogue.set_state(
                "display_smart_unused_percent", str(smart_unused_percent)
            )
            self.catalogue.set_state("display_dither", str(dither_strength > 0).lower())
            self.catalogue.set_state("display_dither_strength", str(dither_strength))

    async def set_focus(self, x: float, y: float) -> tuple[float, float]:
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("focus coordinates must be between 0 and 1")
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.set_focus(photo.id, x, y)
            return (x, y)

    async def clear_focus(self) -> None:
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.clear_focus(photo.id)

    async def _current_photo(self) -> StoredPhoto:
        photo_id = self.catalogue.get_state("current_photo_id")
        photo = self.catalogue.get_photo(photo_id) if photo_id else None
        if photo is None:
            photo = self.catalogue.preview_photo()
        if photo is None:
            raise LookupError("No cached photo is available")
        return photo

    @staticmethod
    def _download_url(source_url: str) -> str:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or not (
            hostname == "googleusercontent.com"
            or hostname.endswith(".googleusercontent.com")
        ):
            raise ValueError("Image host is not allowed")
        return source_url if "=" in parsed.path.rsplit("/", 1)[-1] else f"{source_url}=w2400-h2400"

    def _download_sync(self, photo: StoredPhoto, destination: Path) -> None:
        request = Request(
            self._download_url(photo.source_url),
            headers={"User-Agent": "ePaperPhotoFrame/0.1"},
        )
        temporary = destination.with_suffix(".tmp")
        try:
            with urlopen(request, timeout=45) as response:
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    raise ValueError("Photo download did not return an image")
                total = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(64 * 1024):
                        total += len(chunk)
                        if total > 30 * 1024 * 1024:
                            raise ValueError("Photo exceeds the 30 MiB safety limit")
                        output.write(chunk)
            if total == 0:
                raise ValueError("Photo download was empty")
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    async def _download(self, photo: StoredPhoto, destination: Path) -> None:
        await asyncio.to_thread(self._download_sync, photo, destination)

    async def _ensure_render(self, photo: StoredPhoto) -> tuple[Path, Path]:
        original, png, raw = self._paths(photo.id)
        if not original.exists():
            await self._download(photo, original)
        if not png.exists():
            pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
                focus_point=self.catalogue.get_focus(photo.id),
            )
            await asyncio.to_thread(pipeline.render_png, original.read_bytes(), png)
        if not raw.exists():
            await asyncio.to_thread(self.pipeline.png_to_raw, png, raw)
        return png, raw

    async def sync(self) -> dict[str, object]:
        async with self._sync_lock:
            try:
                snapshot = await self.source.fetch()
                self.catalogue.sync(snapshot)
                preview = self.catalogue.preview_photo()
                if preview:
                    await self._ensure_render(preview)
            except Exception as exc:
                safe_error = f"{type(exc).__name__}: synchronization failed"
                self.catalogue.set_state("last_error", safe_error)
                raise
            return self.status()

    async def next_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_next()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def random_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_random()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def previous_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_previous()
            if photo is None:
                raise LookupError("No previous photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def current_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = await self._current_photo()
            png, raw = await self._ensure_render(photo)
            return photo, png, raw

    def status(self) -> dict[str, object]:
        status = self.catalogue.status()
        status.update(
            {
                "display_model": self.settings.display_model,
                "orientation": self.settings.orientation,
                "width": self.settings.dimensions[0],
                "height": self.settings.dimensions[1],
                "fit_mode": self.settings.fit_mode,
                "smart_unused_percent": self.settings.smart_unused_percent,
                "dither": self.settings.dither,
                "dither_strength": self.settings.dither_strength,
                "focus_point": (
                    self.catalogue.get_focus(photo_id)
                    if (photo_id := self.catalogue.get_state("current_photo_id"))
                    else None
                ),
            }
        )
        return status

    def record_device_report(self, report: dict[str, object]) -> dict[str, object]:
        return self.catalogue.record_device_report(
            device_id=str(report["device_id"]),
            firmware_version=(
                str(report["firmware_version"])
                if report.get("firmware_version") is not None
                else None
            ),
            status=str(report["status"]),
            frame_id=(
                str(report["frame_id"]) if report.get("frame_id") is not None else None
            ),
            battery_percent=(
                int(report["battery_percent"])
                if report.get("battery_percent") is not None
                else None
            ),
            wifi_rssi=(
                int(report["wifi_rssi"])
                if report.get("wifi_rssi") is not None
                else None
            ),
            cycle_ms=(
                int(report["cycle_ms"]) if report.get("cycle_ms") is not None else None
            ),
            detail=str(report["detail"]) if report.get("detail") is not None else None,
        )

    async def background_sync(self) -> None:
        while True:
            try:
                await self.sync()
            except Exception:
                pass
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from frame_app.config import Settings
from frame_app.image_pipeline import ImagePipeline, RENDER_CACHE_VERSION
from frame_app.models import StoredPhoto
from frame_app.sources.base import PhotoSource
from frame_app.storage import Catalogue


class FrameService:
    def __init__(
        self,
        settings: Settings,
        source: PhotoSource,
        catalogue: Catalogue,
        pipeline: ImagePipeline,
    ) -> None:
        self.settings = settings
        self.source = source
        self.catalogue = catalogue
        self.pipeline = pipeline
        self.original_dir = settings.data_dir / "cache" / "original"
        self.render_dir = settings.data_dir / "cache" / "rendered"
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._sync_lock = asyncio.Lock()
        self._frame_lock = asyncio.Lock()

    @staticmethod
    def _cache_key(photo_id: str) -> str:
        return hashlib.sha256(photo_id.encode("utf-8")).hexdigest()

    def _paths(self, photo_id: str) -> tuple[Path, Path, Path]:
        key = self._cache_key(photo_id)
        focus = self.catalogue.get_focus(photo_id)
        focus_key = "auto" if focus is None else f"{focus[0]:.6f},{focus[1]:.6f}"
        render_key = self._cache_key(
            f"{RENDER_CACHE_VERSION}:{photo_id}:{self.settings.display_model}:"
            f"{self.settings.orientation}:"
            f"{self.settings.fit_mode}:"
            f"{self.settings.smart_unused_percent}:{int(self.settings.dither)}:"
            f"{self.settings.dither_strength}:{focus_key}"
        )
        return (
            self.original_dir / f"{key}.image",
            self.render_dir / f"{render_key}.png",
            self.render_dir / f"{render_key}.raw",
        )

    async def set_display_options(
        self,
        orientation: str,
        fit_mode: str,
        smart_unused_percent: int,
        dither_strength: int,
    ) -> None:
        if orientation not in {"portrait", "landscape"}:
            raise ValueError("orientation must be portrait or landscape")
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")
        async with self._frame_lock:
            self.settings = replace(
                self.settings,
                orientation=orientation,
                fit_mode=fit_mode,
                smart_unused_percent=smart_unused_percent,
                dither=dither_strength > 0,
                dither_strength=dither_strength,
            )
            self.pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
            )
            self.catalogue.set_state("display_orientation", orientation)
            self.catalogue.set_state("display_fit_mode", fit_mode)
            self.catalogue.set_state(
                "display_smart_unused_percent", str(smart_unused_percent)
            )
            self.catalogue.set_state("display_dither", str(dither_strength > 0).lower())
            self.catalogue.set_state("display_dither_strength", str(dither_strength))

    async def set_focus(self, x: float, y: float) -> tuple[float, float]:
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("focus coordinates must be between 0 and 1")
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.set_focus(photo.id, x, y)
            return (x, y)

    async def clear_focus(self) -> None:
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.clear_focus(photo.id)

    async def _current_photo(self) -> StoredPhoto:
        photo_id = self.catalogue.get_state("current_photo_id")
        photo = self.catalogue.get_photo(photo_id) if photo_id else None
        if photo is None:
            photo = self.catalogue.preview_photo()
        if photo is None:
            raise LookupError("No cached photo is available")
        return photo

    @staticmethod
    def _download_url(source_url: str) -> str:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or not (
            hostname == "googleusercontent.com"
            or hostname.endswith(".googleusercontent.com")
        ):
            raise ValueError("Image host is not allowed")
        return source_url if "=" in parsed.path.rsplit("/", 1)[-1] else f"{source_url}=w2400-h2400"

    def _download_sync(self, photo: StoredPhoto, destination: Path) -> None:
        request = Request(
            self._download_url(photo.source_url),
            headers={"User-Agent": "ePaperPhotoFrame/0.1"},
        )
        temporary = destination.with_suffix(".tmp")
        try:
            with urlopen(request, timeout=45) as response:
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    raise ValueError("Photo download did not return an image")
                total = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(64 * 1024):
                        total += len(chunk)
                        if total > 30 * 1024 * 1024:
                            raise ValueError("Photo exceeds the 30 MiB safety limit")
                        output.write(chunk)
            if total == 0:
                raise ValueError("Photo download was empty")
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    async def _download(self, photo: StoredPhoto, destination: Path) -> None:
        await asyncio.to_thread(self._download_sync, photo, destination)

    async def _ensure_render(self, photo: StoredPhoto) -> tuple[Path, Path]:
        original, png, raw = self._paths(photo.id)
        if not original.exists():
            await self._download(photo, original)
        if not png.exists():
            pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
                focus_point=self.catalogue.get_focus(photo.id),
            )
            await asyncio.to_thread(pipeline.render_png, original.read_bytes(), png)
        if not raw.exists():
            await asyncio.to_thread(self.pipeline.png_to_raw, png, raw)
        return png, raw

    async def sync(self) -> dict[str, object]:
        async with self._sync_lock:
            try:
                snapshot = await self.source.fetch()
                self.catalogue.sync(snapshot)
                preview = self.catalogue.preview_photo()
                if preview:
                    await self._ensure_render(preview)
            except Exception as exc:
                safe_error = f"{type(exc).__name__}: synchronization failed"
                self.catalogue.set_state("last_error", safe_error)
                raise
            return self.status()

    async def next_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_next()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def random_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_random()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def previous_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_previous()
            if photo is None:
                raise LookupError("No previous photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def current_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = await self._current_photo()
            png, raw = await self._ensure_render(photo)
            return photo, png, raw

    def status(self) -> dict[str, object]:
        status = self.catalogue.status()
        status.update(
            {
                "display_model": self.settings.display_model,
                "orientation": self.settings.orientation,
                "width": self.settings.dimensions[0],
                "height": self.settings.dimensions[1],
                "fit_mode": self.settings.fit_mode,
                "smart_unused_percent": self.settings.smart_unused_percent,
                "dither": self.settings.dither,
                "dither_strength": self.settings.dither_strength,
                "focus_point": (
                    self.catalogue.get_focus(photo_id)
                    if (photo_id := self.catalogue.get_state("current_photo_id"))
                    else None
                ),
            }
        )
        return status

    def record_device_report(self, report: dict[str, object]) -> dict[str, object]:
        return self.catalogue.record_device_report(
            device_id=str(report["device_id"]),
            firmware_version=(
                str(report["firmware_version"])
                if report.get("firmware_version") is not None
                else None
            ),
            status=str(report["status"]),
            frame_id=(
                str(report["frame_id"]) if report.get("frame_id") is not None else None
            ),
            battery_percent=(
                int(report["battery_percent"])
                if report.get("battery_percent") is not None
                else None
            ),
            wifi_rssi=(
                int(report["wifi_rssi"])
                if report.get("wifi_rssi") is not None
                else None
            ),
            cycle_ms=(
                int(report["cycle_ms"]) if report.get("cycle_ms") is not None else None
            ),
            detail=str(report["detail"]) if report.get("detail") is not None else None,
        )

    async def background_sync(self) -> None:
        while True:
            try:
                await self.sync()
            except Exception:
                pass
            await asyncio.sleep(self.settings.album_poll_hours * 3600)
            await asyncio.sleep(self.settings.album_poll_hours * 3600)
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from frame_app.config import Settings
from frame_app.image_pipeline import ImagePipeline, RENDER_CACHE_VERSION
from frame_app.models import StoredPhoto
from frame_app.sources.base import PhotoSource
from frame_app.storage import Catalogue


class FrameService:
    def __init__(
        self,
        settings: Settings,
        source: PhotoSource,
        catalogue: Catalogue,
        pipeline: ImagePipeline,
    ) -> None:
        self.settings = settings
        self.source = source
        self.catalogue = catalogue
        self.pipeline = pipeline
        self.original_dir = settings.data_dir / "cache" / "original"
        self.render_dir = settings.data_dir / "cache" / "rendered"
        self.original_dir.mkdir(parents=True, exist_ok=True)
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._sync_lock = asyncio.Lock()
        self._frame_lock = asyncio.Lock()

    @staticmethod
    def _cache_key(photo_id: str) -> str:
        return hashlib.sha256(photo_id.encode("utf-8")).hexdigest()

    def _paths(self, photo_id: str) -> tuple[Path, Path, Path]:
        key = self._cache_key(photo_id)
        focus = self.catalogue.get_focus(photo_id)
        focus_key = "auto" if focus is None else f"{focus[0]:.6f},{focus[1]:.6f}"
        render_key = self._cache_key(
            f"{RENDER_CACHE_VERSION}:{photo_id}:{self.settings.orientation}:"
            f"{self.settings.fit_mode}:"
            f"{self.settings.smart_unused_percent}:{int(self.settings.dither)}:"
            f"{self.settings.dither_strength}:{focus_key}"
        )
        return (
            self.original_dir / f"{key}.image",
            self.render_dir / f"{render_key}.png",
            self.render_dir / f"{render_key}.raw",
        )

    async def set_display_options(
        self,
        orientation: str,
        fit_mode: str,
        smart_unused_percent: int,
        dither_strength: int,
    ) -> None:
        if orientation not in {"portrait", "landscape"}:
            raise ValueError("orientation must be portrait or landscape")
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")
        async with self._frame_lock:
            self.settings = replace(
                self.settings,
                orientation=orientation,
                fit_mode=fit_mode,
                smart_unused_percent=smart_unused_percent,
                dither=dither_strength > 0,
                dither_strength=dither_strength,
            )
            self.pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
            )
            self.catalogue.set_state("display_orientation", orientation)
            self.catalogue.set_state("display_fit_mode", fit_mode)
            self.catalogue.set_state(
                "display_smart_unused_percent", str(smart_unused_percent)
            )
            self.catalogue.set_state("display_dither", str(dither_strength > 0).lower())
            self.catalogue.set_state("display_dither_strength", str(dither_strength))

    async def set_focus(self, x: float, y: float) -> tuple[float, float]:
        if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
            raise ValueError("focus coordinates must be between 0 and 1")
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.set_focus(photo.id, x, y)
            return (x, y)

    async def clear_focus(self) -> None:
        async with self._frame_lock:
            photo = await self._current_photo()
            self.catalogue.clear_focus(photo.id)

    async def _current_photo(self) -> StoredPhoto:
        photo_id = self.catalogue.get_state("current_photo_id")
        photo = self.catalogue.get_photo(photo_id) if photo_id else None
        if photo is None:
            photo = self.catalogue.preview_photo()
        if photo is None:
            raise LookupError("No cached photo is available")
        return photo

    @staticmethod
    def _download_url(source_url: str) -> str:
        parsed = urlparse(source_url)
        hostname = parsed.hostname or ""
        if parsed.scheme != "https" or not (
            hostname == "googleusercontent.com"
            or hostname.endswith(".googleusercontent.com")
        ):
            raise ValueError("Image host is not allowed")
        return source_url if "=" in parsed.path.rsplit("/", 1)[-1] else f"{source_url}=w2400-h2400"

    def _download_sync(self, photo: StoredPhoto, destination: Path) -> None:
        request = Request(
            self._download_url(photo.source_url),
            headers={"User-Agent": "ePaperPhotoFrame/0.1"},
        )
        temporary = destination.with_suffix(".tmp")
        try:
            with urlopen(request, timeout=45) as response:
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    raise ValueError("Photo download did not return an image")
                total = 0
                with temporary.open("wb") as output:
                    while chunk := response.read(64 * 1024):
                        total += len(chunk)
                        if total > 30 * 1024 * 1024:
                            raise ValueError("Photo exceeds the 30 MiB safety limit")
                        output.write(chunk)
            if total == 0:
                raise ValueError("Photo download was empty")
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    async def _download(self, photo: StoredPhoto, destination: Path) -> None:
        await asyncio.to_thread(self._download_sync, photo, destination)

    async def _ensure_render(self, photo: StoredPhoto) -> tuple[Path, Path]:
        original, png, raw = self._paths(photo.id)
        if not original.exists():
            await self._download(photo, original)
        if not png.exists():
            pipeline = ImagePipeline(
                self.settings.dimensions,
                fit_mode=self.settings.fit_mode,
                dither=self.settings.dither,
                dither_strength=self.settings.dither_strength,
                smart_unused_percent=self.settings.smart_unused_percent,
                focus_point=self.catalogue.get_focus(photo.id),
            )
            await asyncio.to_thread(pipeline.render_png, original.read_bytes(), png)
        if not raw.exists():
            await asyncio.to_thread(self.pipeline.png_to_raw, png, raw)
        return png, raw

    async def sync(self) -> dict[str, object]:
        async with self._sync_lock:
            try:
                snapshot = await self.source.fetch()
                self.catalogue.sync(snapshot)
                preview = self.catalogue.preview_photo()
                if preview:
                    await self._ensure_render(preview)
            except Exception as exc:
                safe_error = f"{type(exc).__name__}: synchronization failed"
                self.catalogue.set_state("last_error", safe_error)
                raise
            return self.status()

    async def next_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_next()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def random_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_random()
            if photo is None:
                raise LookupError("No cached photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def previous_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = self.catalogue.choose_previous()
            if photo is None:
                raise LookupError("No previous photo is available")
            png, raw = await self._ensure_render(photo)
            self.catalogue.mark_shown(photo.id)
            return photo, png, raw

    async def current_frame(self) -> tuple[StoredPhoto, Path, Path]:
        async with self._frame_lock:
            photo = await self._current_photo()
            png, raw = await self._ensure_render(photo)
            return photo, png, raw

    def status(self) -> dict[str, object]:
        status = self.catalogue.status()
        status.update(
            {
                "orientation": self.settings.orientation,
                "width": self.settings.dimensions[0],
                "height": self.settings.dimensions[1],
                "fit_mode": self.settings.fit_mode,
                "smart_unused_percent": self.settings.smart_unused_percent,
                "dither": self.settings.dither,
                "dither_strength": self.settings.dither_strength,
                "focus_point": (
                    self.catalogue.get_focus(photo_id)
                    if (photo_id := self.catalogue.get_state("current_photo_id"))
                    else None
                ),
            }
        )
        return status

    def record_device_report(self, report: dict[str, object]) -> dict[str, object]:
        return self.catalogue.record_device_report(
            device_id=str(report["device_id"]),
            firmware_version=(
                str(report["firmware_version"])
                if report.get("firmware_version") is not None
                else None
            ),
            status=str(report["status"]),
            frame_id=(
                str(report["frame_id"]) if report.get("frame_id") is not None else None
            ),
            battery_percent=(
                int(report["battery_percent"])
                if report.get("battery_percent") is not None
                else None
            ),
            wifi_rssi=(
                int(report["wifi_rssi"])
                if report.get("wifi_rssi") is not None
                else None
            ),
            cycle_ms=(
                int(report["cycle_ms"]) if report.get("cycle_ms") is not None else None
            ),
            detail=str(report["detail"]) if report.get("detail") is not None else None,
        )

    async def background_sync(self) -> None:
        while True:
            try:
                await self.sync()
            except Exception:
                pass
            await asyncio.sleep(self.settings.album_poll_hours * 3600)
