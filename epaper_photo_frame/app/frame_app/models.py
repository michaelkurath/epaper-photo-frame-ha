from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourcePhoto:
    id: str
    url: str
    width: int | None = None
    height: int | None = None
    created_at: int | None = None


@dataclass(frozen=True, slots=True)
class AlbumSnapshot:
    id: str
    title: str
    photos: tuple[SourcePhoto, ...]


@dataclass(frozen=True, slots=True)
class StoredPhoto:
    id: str
    source_url: str
    width: int | None
    height: int | None
    created_at: int | None
    shown_count: int
    last_shown_at: int | None

