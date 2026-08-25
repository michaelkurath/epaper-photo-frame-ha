from __future__ import annotations

import random
import sqlite3
import time
from pathlib import Path

from frame_app.models import AlbumSnapshot, StoredPhoto


class Catalogue:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS photos (
                    id TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    created_at INTEGER,
                    discovered_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    shown_count INTEGER NOT NULL DEFAULT 0,
                    last_shown_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def sync(self, snapshot: AlbumSnapshot, now: int | None = None) -> None:
        timestamp = now or int(time.time())
        with self._connect() as db:
            db.execute("UPDATE photos SET active = 0")
            for photo in snapshot.photos:
                db.execute(
                    """
                    INSERT INTO photos (
                        id, source_url, width, height, created_at,
                        discovered_at, last_seen_at, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(id) DO UPDATE SET
                        source_url = excluded.source_url,
                        width = excluded.width,
                        height = excluded.height,
                        created_at = excluded.created_at,
                        last_seen_at = excluded.last_seen_at,
                        active = 1
                    """,
                    (
                        photo.id,
                        photo.url,
                        photo.width,
                        photo.height,
                        photo.created_at,
                        timestamp,
                        timestamp,
                    ),
                )
            self._set_state_in(db, "album_id", snapshot.id)
            self._set_state_in(db, "album_title", snapshot.title)
            self._set_state_in(db, "last_sync", str(timestamp))
            self._set_state_in(db, "last_error", "")

    @staticmethod
    def _set_state_in(db: sqlite3.Connection, key: str, value: str) -> None:
        db.execute(
            """
            INSERT INTO state(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as db:
            self._set_state_in(db, key, value)

    def get_state(self, key: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_focus(self, photo_id: str, x: float, y: float) -> None:
        self.set_state(f"focus:{photo_id}", f"{x:.6f},{y:.6f}")

    def clear_focus(self, photo_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM state WHERE key = ?", (f"focus:{photo_id}",))

    def get_focus(self, photo_id: str) -> tuple[float, float] | None:
        value = self.get_state(f"focus:{photo_id}")
        if not value:
            return None
        try:
            x, y = (float(part) for part in value.split(",", 1))
        except (TypeError, ValueError):
            return None
        return (x, y) if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 else None

    @staticmethod
    def _stored(row: sqlite3.Row) -> StoredPhoto:
        return StoredPhoto(
            id=row["id"],
            source_url=row["source_url"],
            width=row["width"],
            height=row["height"],
            created_at=row["created_at"],
            shown_count=row["shown_count"],
            last_shown_at=row["last_shown_at"],
        )

    def get_photo(self, photo_id: str) -> StoredPhoto | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
        return self._stored(row) if row else None

    def preview_photo(self) -> StoredPhoto | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT * FROM photos WHERE active = 1
                ORDER BY shown_count ASC, COALESCE(created_at, discovered_at) DESC
                LIMIT 1
                """
            ).fetchone()
        return self._stored(row) if row else None

    def choose_next(self) -> StoredPhoto | None:
        current_id = self.get_state("current_photo_id")
        with self._connect() as db:
            unseen = db.execute(
                """
                SELECT * FROM photos
                WHERE active = 1 AND shown_count = 0 AND id != COALESCE(?, '')
                ORDER BY COALESCE(created_at, discovered_at) DESC
                """,
                (current_id,),
            ).fetchall()
            if unseen:
                return self._stored(unseen[0])
            rows = db.execute(
                """
                SELECT * FROM photos
                WHERE active = 1 AND id != COALESCE(?, '')
                """,
                (current_id,),
            ).fetchall()
            if not rows and current_id:
                row = db.execute(
                    "SELECT * FROM photos WHERE active = 1 AND id = ?", (current_id,)
                ).fetchone()
                return self._stored(row) if row else None
        return self._stored(random.SystemRandom().choice(rows)) if rows else None

    def choose_random(self) -> StoredPhoto | None:
        current_id = self.get_state("current_photo_id")
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM photos
                WHERE active = 1 AND id != COALESCE(?, '')
                """,
                (current_id,),
            ).fetchall()
            if not rows and current_id:
                row = db.execute(
                    "SELECT * FROM photos WHERE active = 1 AND id = ?", (current_id,)
                ).fetchone()
                return self._stored(row) if row else None
        return self._stored(random.SystemRandom().choice(rows)) if rows else None

    def choose_previous(self) -> StoredPhoto | None:
        current_id = self.get_state("current_photo_id")
        with self._connect() as db:
            row = db.execute(
                """
                SELECT * FROM photos
                WHERE active = 1
                  AND id != COALESCE(?, '')
                  AND last_shown_at IS NOT NULL
                ORDER BY last_shown_at DESC
                LIMIT 1
                """,
                (current_id,),
            ).fetchone()
        return self._stored(row) if row else None

    def mark_shown(self, photo_id: str, now: int | None = None) -> None:
        timestamp = now or int(time.time())
        with self._connect() as db:
            db.execute(
                """
                UPDATE photos
                SET shown_count = shown_count + 1, last_shown_at = ?
                WHERE id = ?
                """,
                (timestamp, photo_id),
            )
            self._set_state_in(db, "current_photo_id", photo_id)
            self._set_state_in(db, "last_frame_at", str(timestamp))

    def status(self) -> dict[str, object]:
        with self._connect() as db:
            counts = db.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN shown_count = 0 THEN 1 ELSE 0 END) AS new_count
                FROM photos WHERE active = 1
                """
            ).fetchone()
            state_rows = db.execute("SELECT key, value FROM state").fetchall()
        state = {row["key"]: row["value"] for row in state_rows}
        return {
            "album_title": state.get("album_title"),
            "photo_count": int(counts["total"] or 0),
            "new_photo_count": int(counts["new_count"] or 0),
            "last_sync": int(state["last_sync"]) if state.get("last_sync") else None,
            "last_frame_at": (
                int(state["last_frame_at"]) if state.get("last_frame_at") else None
            ),
            "last_error": state.get("last_error") or None,
            "has_current_frame": bool(state.get("current_photo_id")),
        }
