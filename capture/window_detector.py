from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from config import CaptureRegion


@dataclass(slots=True)
class WindowInfo:
    handle: int
    title: str
    region: CaptureRegion


class WindowDetector:
    def list_windows(self) -> list[WindowInfo]:
        user32 = ctypes.windll.user32
        windows: list[WindowInfo] = []

        enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, _: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            if width > 100 and height > 100:
                windows.append(
                    WindowInfo(
                        handle=int(hwnd),
                        title=buffer.value,
                        region=CaptureRegion(rect.left, rect.top, width, height),
                    )
                )
            return True

        user32.EnumWindows(enum_proc_type(callback), 0)
        return windows

    def find_chesscom_window(self) -> WindowInfo | None:
        candidates = [
            window
            for window in self.list_windows()
            if "chess.com" in window.title.lower() or "chess" in window.title.lower()
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.region.width * item.region.height)
