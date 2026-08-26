from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager, suppress
from dataclasses import replace
from pathlib import Path
from typing import Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from frame_app.config import Settings
from frame_app.device_protocol import device_config_payload
from frame_app.image_pipeline import ImagePipeline
from frame_app.service import FrameService
from frame_app.sources.google_photos import GooglePhotosPublicAlbum
from frame_app.storage import Catalogue


service: FrameService | None = None


class DisplayOptions(BaseModel):
    orientation: str
    fit_mode: str
    smart_unused_percent: int = Field(default=15, ge=0, le=40)
    dither_strength: int = Field(default=50, ge=0, le=100)


class FocusOptions(BaseModel):
    x: float
    y: float


class DeviceReport(BaseModel):
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    firmware_version: str | None = Field(default=None, max_length=64)
    status: Literal["awake", "displayed", "sleeping", "error"]
    frame_id: str | None = Field(default=None, max_length=256)
    battery_percent: int | None = Field(default=None, ge=0, le=100)
    wifi_rssi: int | None = Field(default=None, ge=-120, le=0)
    cycle_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    detail: str | None = Field(default=None, max_length=256)


def _service() -> FrameService:
    if service is None:
        raise HTTPException(status_code=503, detail="Service is starting")
    return service


def _device_auth(
    authorization: str | None = Header(default=None),
    current: FrameService = Depends(_service),
) -> FrameService:
    prefix = "Bearer "
    supplied = authorization[len(prefix) :] if authorization and authorization.startswith(prefix) else ""
    if not supplied or not hmac.compare_digest(supplied, current.settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current


@asynccontextmanager
async def lifespan(app: FastAPI):
    global service
    settings = Settings.load()
    catalogue = Catalogue(settings.data_dir / "catalogue.sqlite3")
    orientation = catalogue.get_state("display_orientation") or settings.orientation
    fit_mode = catalogue.get_state("display_fit_mode") or settings.fit_mode
    stored_unused = catalogue.get_state("display_smart_unused_percent")
    try:
        smart_unused_percent = int(stored_unused) if stored_unused is not None else settings.smart_unused_percent
    except ValueError:
        smart_unused_percent = settings.smart_unused_percent
    if not 0 <= smart_unused_percent <= 40:
        smart_unused_percent = settings.smart_unused_percent
    stored_dither = catalogue.get_state("display_dither")
    dither = (
        stored_dither.lower() in {"1", "true", "yes", "on"}
        if stored_dither is not None
        else settings.dither
    )
    stored_strength = catalogue.get_state("display_dither_strength")
    try:
        dither_strength = (
            int(stored_strength) if stored_strength is not None else settings.dither_strength
        )
    except ValueError:
        dither_strength = settings.dither_strength
    if not 0 <= dither_strength <= 100:
        dither_strength = settings.dither_strength
    if not dither:
        dither_strength = 0
    settings = replace(
        settings,
        orientation=orientation,
        fit_mode=fit_mode,
        smart_unused_percent=smart_unused_percent,
        dither=dither,
        dither_strength=dither_strength,
    )
    source = GooglePhotosPublicAlbum(settings.album_url)
    pipeline = ImagePipeline(
        settings.dimensions,
        fit_mode=settings.fit_mode,
        dither=settings.dither,
        dither_strength=settings.dither_strength,
        smart_unused_percent=settings.smart_unused_percent,
    )
    service = FrameService(settings, source, catalogue, pipeline)
    task = asyncio.create_task(service.background_sync())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        service = None


app = FastAPI(
    title="ePaper Photo Frame",
    version="0.6.1",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    template = Path(__file__).parent / "static" / "index.html"
    return template.read_text(encoding="utf-8")


@app.get("/api/status")
async def app_status(current: FrameService = Depends(_service)) -> dict[str, object]:
    return current.status()


@app.post("/api/sync")
async def sync_now(current: FrameService = Depends(_service)) -> JSONResponse:
    try:
        result = await current.sync()
        return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: sync failed") from exc


@app.get("/api/preview.png", response_class=FileResponse)
async def preview(current: FrameService = Depends(_service)) -> FileResponse:
    try:
        photo, png, _ = await current.current_frame()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: frame processing failed"
        ) from exc
    return FileResponse(png, media_type="image/png", headers={"X-Frame-Id": photo.id})


async def _select_preview(mode: str, current: FrameService) -> dict[str, str]:
    try:
        if mode == "previous":
            photo, _, _ = await current.previous_frame()
        elif mode == "random":
            photo, _, _ = await current.random_frame()
        else:
            photo, _, _ = await current.next_frame()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"{type(exc).__name__}: frame processing failed"
        ) from exc
    return {"photo_id": photo.id}


@app.post("/api/frame/previous")
async def previous_preview(current: FrameService = Depends(_service)) -> dict[str, str]:
    return await _select_preview("previous", current)


@app.post("/api/frame/next")
async def next_preview(current: FrameService = Depends(_service)) -> dict[str, str]:
    return await _select_preview("next", current)


@app.post("/api/frame/random")
async def random_preview(current: FrameService = Depends(_service)) -> dict[str, str]:
    return await _select_preview("random", current)


@app.post("/api/display")
async def display_options(
    options: DisplayOptions, current: FrameService = Depends(_service)
) -> dict[str, object]:
    try:
        await current.set_display_options(
            options.orientation,
            options.fit_mode,
            options.smart_unused_percent,
            options.dither_strength,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return current.status()


@app.post("/api/frame/focus")
async def set_frame_focus(
    options: FocusOptions, current: FrameService = Depends(_service)
) -> dict[str, object]:
    try:
        focus = await current.set_focus(options.x, options.y)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"focus_point": focus}


@app.delete("/api/frame/focus")
async def clear_frame_focus(
    current: FrameService = Depends(_service),
) -> dict[str, object]:
    try:
        await current.clear_focus()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"focus_point": None}


@app.get("/api/device/config")
async def device_config(current: FrameService = Depends(_device_auth)) -> dict[str, object]:
    return device_config_payload(current.settings)


@app.post("/api/device/report")
async def device_report(
    report: DeviceReport, current: FrameService = Depends(_device_auth)
) -> dict[str, object]:
    return current.record_device_report(report.model_dump())


async def _frame_response(
    current: FrameService, *, advance: bool, raw: bool
) -> FileResponse:
    try:
        photo, png_path, raw_path = (
            await current.next_frame() if advance else await current.current_frame()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    selected = raw_path if raw else png_path
    media_type = "application/octet-stream" if raw else "image/png"
    return FileResponse(
        selected,
        media_type=media_type,
        headers={
            "X-Frame-Id": photo.id,
            "X-Frame-Width": str(current.settings.dimensions[0]),
            "X-Frame-Height": str(current.settings.dimensions[1]),
            "X-Frame-Bytes": str(selected.stat().st_size),
            "ETag": f'"{photo.id}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/device/current.png", response_class=FileResponse)
async def device_current_png(current: FrameService = Depends(_device_auth)) -> FileResponse:
    return await _frame_response(current, advance=False, raw=False)


@app.get("/api/device/current.raw", response_class=FileResponse)
async def device_current_raw(current: FrameService = Depends(_device_auth)) -> FileResponse:
    return await _frame_response(current, advance=False, raw=True)


@app.post("/api/device/next.png", response_class=FileResponse)
async def device_next_png(current: FrameService = Depends(_device_auth)) -> FileResponse:
    return await _frame_response(current, advance=True, raw=False)


@app.post("/api/device/next.raw", response_class=FileResponse)
async def device_next_raw(current: FrameService = Depends(_device_auth)) -> FileResponse:
    return await _frame_response(current, advance=True, raw=True)
