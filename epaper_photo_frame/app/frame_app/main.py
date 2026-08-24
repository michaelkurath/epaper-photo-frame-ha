from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from frame_app.config import Settings
from frame_app.image_pipeline import ImagePipeline
from frame_app.service import FrameService
from frame_app.sources.google_photos import GooglePhotosPublicAlbum
from frame_app.storage import Catalogue


service: FrameService | None = None


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
    source = GooglePhotosPublicAlbum(settings.album_url)
    pipeline = ImagePipeline(
        settings.dimensions, fit_mode=settings.fit_mode, dither=settings.dither
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
    version="0.1.1",
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
    return FileResponse(png, media_type="image/png", headers={"X-Frame-Id": photo.id})


@app.get("/api/device/config")
async def device_config(current: FrameService = Depends(_device_auth)) -> dict[str, object]:
    return {
        "width": current.settings.dimensions[0],
        "height": current.settings.dimensions[1],
        "palette": ["white", "black", "red", "yellow", "blue", "green"],
        "raw_packing": "two 4-bit palette indices per byte, high nibble first",
        "frame_interval_seconds": current.settings.frame_interval_hours * 3600,
        "night_start": current.settings.night_start,
        "night_end": current.settings.night_end,
    }


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
