from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent
# Writable/persistent data (settings, logs) must live next to the exe, not in
# PyInstaller's onefile temp extraction dir, which is wiped on exit.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT_DIR
CONFIG_DIR = APP_DIR / "config"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
ASSETS_DIR = ROOT_DIR / "assets"
MODELS_DIR = ROOT_DIR / "models"
LOGS_DIR = APP_DIR / "logs"

_STOCKFISH_CANDIDATE_NAMES = ("stockfish.exe", "stockfish-windows-x86-64-avx2.exe")


def _default_stockfish_path() -> str:
    """Look for a Stockfish binary shipped next to the app before falling
    back to PATH lookup, so a packaged exe works without extra setup."""
    for directory in (APP_DIR, ROOT_DIR):
        for name in _STOCKFISH_CANDIDATE_NAMES:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    return "stockfish"


@dataclass(slots=True)
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int


@dataclass(slots=True)
class EngineSettings:
    stockfish_path: str = field(default_factory=_default_stockfish_path)
    depth: int = 14
    skill_level: int = 20
    threads: int = 2
    hash_mb: int = 256
    analysis_time_ms: int = 700
    multipv: int = 3


@dataclass(slots=True)
class CaptureSettings:
    fps: int = 30
    use_dxcam: bool = False
    selected_window_title: str = ""
    manual_region: CaptureRegion | None = None


@dataclass(slots=True)
class OverlaySettings:
    visible: bool = True
    opacity: float = 0.85
    left: int = 80
    top: int = 80
    width: int = 440
    height: int = 180


@dataclass(slots=True)
class GameplaySettings:
    player_color: str = "white"
    recognition_interval_ms: int = 250
    # Board orientation: "auto" detects it, "white"/"black" force it.
    orientation_mode: str = "auto"


@dataclass(slots=True)
class UiSettings:
    dark_mode: bool = True
    show_board_preview: bool = True


@dataclass(slots=True)
class AppSettings:
    engine: EngineSettings = field(default_factory=EngineSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    gameplay: GameplaySettings = field(default_factory=GameplaySettings)
    ui: UiSettings = field(default_factory=UiSettings)
    recent_sessions: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "AppSettings":
        if not path.exists():
            settings = cls()
            settings.save(path)
            return settings

        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        capture_data = data.get("capture", {})
        region_data = capture_data.get("manual_region")
        region = CaptureRegion(**region_data) if isinstance(region_data, dict) else None

        return cls(
            engine=EngineSettings(**data.get("engine", {})),
            capture=CaptureSettings(
                fps=capture_data.get("fps", 30),
                use_dxcam=capture_data.get("use_dxcam", False),
                selected_window_title=capture_data.get("selected_window_title", ""),
                manual_region=region,
            ),
            overlay=OverlaySettings(**data.get("overlay", {})),
            gameplay=GameplaySettings(**data.get("gameplay", {})),
            ui=UiSettings(**data.get("ui", {})),
            recent_sessions=list(data.get("recent_sessions", [])),
        )

    def save(self, path: Path = SETTINGS_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2)
