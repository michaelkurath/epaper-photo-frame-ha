from __future__ import annotations

import time

from frame_app.config import Settings
from frame_app.image_pipeline import SPECTRA6_PALETTE


DEVICE_PROTOCOL_VERSION = 1
PALETTE_NAMES = ("white", "black", "red", "yellow", "blue", "green")


def device_config_payload(
    settings: Settings, *, server_time: int | None = None
) -> dict[str, object]:
    width, height = settings.dimensions
    return {
        "protocol_version": DEVICE_PROTOCOL_VERSION,
        "server_time": server_time if server_time is not None else int(time.time()),
        "width": width,
        "height": height,
        "palette": list(PALETTE_NAMES),
        "palette_rgb": [list(colour) for colour in SPECTRA6_PALETTE],
        "raw_packing": "two 4-bit palette indices per byte, high nibble first",
        "raw_size_bytes": width * height // 2,
        "frame_interval_seconds": settings.frame_interval_hours * 3600,
        "night_start": settings.night_start,
        "night_end": settings.night_end,
        "report_endpoint": "/api/device/report",
    }
