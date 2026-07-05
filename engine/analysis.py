from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateMove:
    move_uci: str
    move_san: str
    score_cp: int | None
    mate_in: int | None
    pv: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    fen: str
    depth: int
    best_move_uci: str
    best_move_san: str
    score_cp: int | None
    mate_in: int | None
    candidates: tuple[CandidateMove, ...]

    @property
    def evaluation_text(self) -> str:
        if self.mate_in is not None:
            return f"Mate {self.mate_in}"
        if self.score_cp is None:
            return "0.00"
        return f"{self.score_cp / 100:+.2f}"
