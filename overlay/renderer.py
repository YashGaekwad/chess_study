from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverlayBoard:
    left: int = 0
    top: int = 0
    size: int = 0
    flipped: bool = False


@dataclass(frozen=True, slots=True)
class OverlayAnalysis:
    best_move: str = ""
    best_move_uci: str = ""
    evaluation: str = ""
    depth: int = 0
    candidates: tuple[str, ...] = ()
