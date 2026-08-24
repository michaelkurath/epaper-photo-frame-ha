from __future__ import annotations

import asyncio
import html
import json
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from frame_app.models import AlbumSnapshot, SourcePhoto


class GooglePhotosError(RuntimeError):
    """A public Google Photos album could not be read safely."""


class _CanonicalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.url: str | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() != "link":
            return
        values = {key.lower(): value for key, value in attrs}
        rel = (values.get("rel") or "").lower().split()
        if "canonical" in rel and values.get("href"):
            self.url = html.unescape(values["href"] or "")


class GooglePhotosPublicAlbum:
    """Read a public share using Google's unauthenticated Photos web RPC."""

    _album_rpc = "snAcKc"
    _rpc_url = "https://photos.google.com/_/PhotosUi/data/batchexecute"
    _allowed_input_hosts = {"photos.google.com", "photos.app.goo.gl"}

    def __init__(
        self,
        album_url: str,
        *,
        max_pages: int = 100,
    ) -> None:
        self.album_url = album_url
        self.max_pages = max_pages
        self._validate_input_url(album_url)

    @classmethod
    def _validate_input_url(cls, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in cls._allowed_input_hosts:
            raise GooglePhotosError("Only HTTPS Google Photos share links are allowed")

    @staticmethod
    def _canonical_from_html(page: str) -> str:
        parser = _CanonicalParser()
        parser.feed(page)
        if not parser.url:
            raise GooglePhotosError("The album page has no canonical share link")
        return parser.url

    @staticmethod
    def _album_identity(canonical_url: str, input_url: str) -> tuple[str, str]:
        canonical = urlparse(canonical_url)
        if canonical.scheme != "https" or canonical.hostname != "photos.google.com":
            raise GooglePhotosError("The canonical album link is not Google Photos")
        parts = [part for part in canonical.path.split("/") if part]
        album_id = parts[-1] if parts else ""
        key = parse_qs(canonical.query).get("key", [""])[0]
        if not key:
            key = parse_qs(urlparse(input_url).query).get("key", [""])[0]
        if not album_id or not key:
            raise GooglePhotosError("Album id or share key is missing")
        return album_id, key

    @staticmethod
    def _decode_rpc(text: str, rpc_id: str) -> list[object]:
        clean = text.lstrip()
        if clean.startswith(")]}'"):
            clean = clean[4:].lstrip()
        try:
            envelope = json.loads(clean)
        except json.JSONDecodeError as exc:
            raise GooglePhotosError("Google Photos returned invalid RPC data") from exc

        for row in envelope:
            if isinstance(row, list) and len(row) > 2 and row[1] == rpc_id:
                try:
                    payload = json.loads(row[2])
                except (TypeError, json.JSONDecodeError) as exc:
                    raise GooglePhotosError("Google Photos RPC payload is invalid") from exc
                if isinstance(payload, list):
                    return payload
        raise GooglePhotosError("Google Photos RPC response is missing album data")

    def _rpc_page(
        self, album_id: str, key: str, token: object | None
    ) -> list[object]:
        argument = json.dumps(
            [album_id, token, None, key], separators=(",", ":")
        )
        request = [[[self._album_rpc, argument]]]
        body = urlencode(
            {"f.req": json.dumps(request, separators=(",", ":"))}
        ).encode("utf-8")
        network_request = Request(
            self._rpc_url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "User-Agent": "ePaperPhotoFrame/0.1",
            },
        )
        with urlopen(network_request, timeout=30) as response:
            text = response.read().decode("utf-8", "replace")
        return self._decode_rpc(text, self._album_rpc)

    @staticmethod
    def _photos_from_payload(payload: list[object]) -> list[SourcePhoto]:
        raw_items = payload[1] if len(payload) > 1 else []
        if not isinstance(raw_items, list):
            return []
        photos: list[SourcePhoto] = []
        for item in raw_items:
            if not isinstance(item, list) or len(item) < 2:
                continue
            photo_id, image_data = item[0], item[1]
            if not isinstance(photo_id, str) or not isinstance(image_data, list):
                continue
            if not image_data or not isinstance(image_data[0], str):
                continue
            url = image_data[0]
            parsed = urlparse(url)
            if parsed.scheme != "https" or not (
                parsed.hostname == "googleusercontent.com"
                or (parsed.hostname or "").endswith(".googleusercontent.com")
            ):
                continue
            width = image_data[1] if len(image_data) > 1 else None
            height = image_data[2] if len(image_data) > 2 else None
            created_at = item[2] if len(item) > 2 else None
            photos.append(
                SourcePhoto(
                    id=photo_id,
                    url=url,
                    width=width if isinstance(width, int) else None,
                    height=height if isinstance(height, int) else None,
                    created_at=created_at if isinstance(created_at, int) else None,
                )
            )
        return photos

    def _fetch_sync(self) -> AlbumSnapshot:
        try:
            request = Request(
                self.album_url, headers={"User-Agent": "ePaperPhotoFrame/0.1"}
            )
            with urlopen(request, timeout=30) as response:
                page = response.read().decode("utf-8", "replace")
            canonical = self._canonical_from_html(page)
            album_id, key = self._album_identity(canonical, self.album_url)

            title = "Google Photos"
            token: object | None = None
            photos: list[SourcePhoto] = []
            seen: set[str] = set()
            for _ in range(self.max_pages):
                payload = self._rpc_page(album_id, key, token)
                details = payload[3] if len(payload) > 3 else []
                if isinstance(details, list) and len(details) > 1:
                    if isinstance(details[1], str) and details[1].strip():
                        title = details[1].strip()
                for photo in self._photos_from_payload(payload):
                    if photo.id not in seen:
                        photos.append(photo)
                        seen.add(photo.id)
                token = payload[2] if len(payload) > 2 else None
                if not token:
                    break
            else:
                raise GooglePhotosError("Album pagination exceeded the safety limit")

            if not photos:
                raise GooglePhotosError("The public album contains no readable photos")
            return AlbumSnapshot(id=album_id, title=title, photos=tuple(photos))
        except GooglePhotosError:
            raise
        except (OSError, TimeoutError) as exc:
            raise GooglePhotosError("Google Photos could not be reached") from exc

    async def fetch(self) -> AlbumSnapshot:
        return await asyncio.to_thread(self._fetch_sync)
