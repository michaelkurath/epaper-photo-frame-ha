from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DISPLAY_MODEL_13_3 = "spectra_13_3_ee02"
DISPLAY_MODEL_7_3 = "spectra_7_3_ee04"
DISPLAY_DIMENSIONS = {
    DISPLAY_MODEL_13_3: (1200, 1600),
    DISPLAY_MODEL_7_3: (480, 800),
}


@dataclass(frozen=True, slots=True)
class Settings:
    album_url: str
    api_token: str
    album_poll_hours: int = 6
    frame_interval_hours: int = 4
    fit_mode: str = "cover"
    display_model: str = DISPLAY_MODEL_13_3
    orientation: str = "portrait"
    smart_unused_percent: int = 15
    dither: bool = True
    dither_strength: int = 50
    night_start: str = "23:00"
    night_end: str = "07:00"
    data_dir: Path = Path("/data")

    @property
    def dimensions(self) -> tuple[int, int]:
        portrait = DISPLAY_DIMENSIONS[self.display_model]
        return portrait if self.orientation == "portrait" else portrait[::-1]

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
        display_model = str(option("display_model", DISPLAY_MODEL_13_3))
        orientation = str(option("orientation", "portrait"))
        if fit_mode not in {"cover", "contain", "smart"}:
            raise ValueError("fit_mode must be cover, contain or smart")
        if display_model not in DISPLAY_DIMENSIONS:
            raise ValueError(
                "display_model must be spectra_13_3_ee02 or spectra_7_3_ee04"
            )
        if orientation not in {"portrait", "landscape"}:
            raise ValueError("orientation must be portrait or landscape")
        smart_unused_percent = int(option("smart_unused_percent", 15) or 0)
        if not 0 <= smart_unused_percent <= 40:
            raise ValueError("smart_unused_percent must be between 0 and 40")

        raw_dither = option("dither", True)
        if isinstance(raw_dither, str):
            dither = raw_dither.lower() in {"1", "true", "yes", "on"}
        else:
            dither = bool(raw_dither)
        dither_strength = int(option("dither_strength", 50) or 0)
        if not 0 <= dither_strength <= 100:
            raise ValueError("dither_strength must be between 0 and 100")

        return cls(
            album_url=album_url,
            api_token=api_token,
            album_poll_hours=int(option("album_poll_hours", 6) or 6),
            frame_interval_hours=int(option("frame_interval_hours", 4) or 4),
            fit_mode=fit_mode,
            display_model=display_model,
            orientation=orientation,
            smart_unused_percent=smart_unused_percent,
            dither=dither,
            dither_strength=dither_strength,
            night_start=str(option("night_start", "23:00")),
            night_end=str(option("night_end", "07:00")),
            data_dir=Path(os.getenv("EPAPER_DATA_DIR", "/data")),
        )
