from __future__ import annotations

from typing import Protocol

from frame_app.models import AlbumSnapshot


class PhotoSource(Protocol):
    async def fetch(self) -> AlbumSnapshot:
        """Return the source's current album metadata."""

