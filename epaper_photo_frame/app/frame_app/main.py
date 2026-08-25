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



