from __future__ import annotations

from config import AppSettings, CaptureRegion


def test_settings_roundtrip_dict() -> None:
    settings = AppSettings()
    settings.capture.manual_region = CaptureRegion(1, 2, 3, 4)
    data = {
        "engine": {"depth": 10},
        "capture": {
            "fps": 60,
            "manual_region": {"left": 1, "top": 2, "width": 3, "height": 4},
        },
    }

    loaded = AppSettings.from_dict(data)

    assert loaded.engine.depth == 10
    assert loaded.capture.fps == 60
    assert loaded.capture.manual_region == settings.capture.manual_region
