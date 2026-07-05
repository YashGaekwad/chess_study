from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from config import CaptureRegion

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CapturedFrame:
    image: np.ndarray
    timestamp: float
    region: CaptureRegion


class ScreenCapture:
    def __init__(self) -> None:
        try:
            import mss
        except ImportError as exc:  # pragma: no cover - dependency missing path
            raise RuntimeError("mss is required for screen capture") from exc
        self._mss_factory = mss.mss
        self._session = None

    def __enter__(self) -> "ScreenCapture":
        self._session = self._mss_factory()
        return self

    def __exit__(self, *_: object) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def capture_region(self, region: CaptureRegion) -> CapturedFrame:
        if self._session is None:
            self._session = self._mss_factory()

        monitor = {
            "left": region.left,
            "top": region.top,
            "width": region.width,
            "height": region.height,
        }
        raw = self._session.grab(monitor)
        image = np.asarray(raw, dtype=np.uint8)[:, :, :3]
        image = np.ascontiguousarray(image[:, :, ::-1])
        return CapturedFrame(image=image, timestamp=perf_counter(), region=region)

    def primary_monitor_region(self) -> CaptureRegion:
        with self._mss_factory() as session:
            monitor = session.monitors[1]
        return CaptureRegion(
            left=int(monitor["left"]),
            top=int(monitor["top"]),
            width=int(monitor["width"]),
            height=int(monitor["height"]),
        )
