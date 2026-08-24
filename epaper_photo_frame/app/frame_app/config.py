from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    album_url: str
    api_token: str
    album_poll_hours: int = 6
    frame_interval_hours: int = 4
    fit_mode: str = "cover"
    orientation: str = "portrait"
    dither: bool = True
    night_start: str = "23:00"
    night_end: str = "07:00"
    data_dir: Path = Path("/data")

    @property
    def dimensions(self) -> tuple[int, int]:
        return (1200, 1600) if self.orientation == "portrait" else (1600, 1200)

    @classmethod
    def load(cls) -> "Settings":
        options_file = Path(os.getenv("EPAPER_OPTIONS_FILE", "/data/options.json"))
        options: dict[str, object] = {}
        if options_file.exists():
            options = json.loads(options_file.read_text(encoding="utf-8"))

        def option(name: str, default: object | None = None) -> object | None:
            env_name = f"EPAPER_{name.upper()}"
            return os.getenv(env_name, options.get(name, default))

        album_url = str(option("album_url", "") or "").strip()
        api_token = str(option("api_token", "") or "").strip()
        if not album_url:
            raise ValueError("album_url is required")
        if len(api_token) < 16:
            raise ValueError("api_token must contain at least 16 characters")

        fit_mode = str(option("fit_mode", "cover"))
        orientation = str(option("orientation", "portrait"))
        if fit_mode not in {"cover", "contain"}:
            raise ValueError("fit_mode must be cover or contain")
        if orientation not in {"portrait", "landscape"}:
            raise ValueError("orientation must be portrait or landscape")

        raw_dither = option("dither", True)
        if isinstance(raw_dither, str):
            dither = raw_dither.lower() in {"1", "true", "yes", "on"}
        else:
            dither = bool(raw_dither)

        return cls(
            album_url=album_url,
            api_token=api_token,
            album_poll_hours=int(option("album_poll_hours", 6) or 6),
            frame_interval_hours=int(option("frame_interval_hours", 4) or 4),
            fit_mode=fit_mode,
            orientation=orientation,
            dither=dither,
            night_start=str(option("night_start", "23:00")),
            night_end=str(option("night_end", "07:00")),
            data_dir=Path(os.getenv("EPAPER_DATA_DIR", "/data")),
        )

