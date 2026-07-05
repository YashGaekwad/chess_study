from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine

from config import EngineSettings
from engine.analysis import AnalysisResult, CandidateMove

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EngineState:
    ready: bool = False
    last_error: str = ""


class StockfishEngine:
    def __init__(self, settings: EngineSettings) -> None:
        self.settings = settings
        self.state = EngineState()
        self._engine: chess.engine.SimpleEngine | None = None

    def start(self) -> None:
        if self._engine is not None:
            return
        path = Path(self.settings.stockfish_path)
        command = str(path) if path.exists() else self.settings.stockfish_path
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(command)
            self._configure()
            self.state.ready = True
            self.state.last_error = ""
        except Exception as exc:
            self.state.ready = False
            self.state.last_error = str(exc)
            LOGGER.exception("Could not start Stockfish")
            raise

    def close(self) -> None:
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:  # noqa: BLE001 - process may already be dead
                pass
            self._engine = None
        self.state.ready = False

    def set_skill_level(self, level: int) -> None:
        """Change engine strength. Call from the worker thread only (the engine
        process is not thread-safe)."""
        self.settings.skill_level = max(0, min(20, level))
        if self._engine is not None:
            try:
                self._configure()
            except Exception:  # noqa: BLE001 - engine may be mid-restart
                pass

    def analyze(self, fen: str) -> AnalysisResult:
        board = chess.Board(fen)
        # Refuse illegal positions: feeding one to Stockfish causes an
        # access-violation crash (Windows exit code 3221225477 / 0xC0000005).
        if not board.is_valid():
            raise ValueError(f"Illegal position, skipping analysis: {board.status()!r}")

        limit = chess.engine.Limit(
            depth=self.settings.depth,
            time=max(self.settings.analysis_time_ms, 50) / 1000.0,
        )
        multipv = max(1, self.settings.multipv)

        # Retry once through a fresh engine if the process dies mid-analysis so a
        # single crash doesn't tear down the whole worker thread.
        last_exc: Exception | None = None
        for attempt in range(2):
            if self._engine is None:
                self.start()
            assert self._engine is not None
            try:
                infos = self._engine.analyse(board, limit, multipv=multipv)
                break
            except chess.engine.EngineError as exc:
                last_exc = exc
                LOGGER.warning("Engine analysis failed (attempt %d): %s", attempt + 1, exc)
                self._force_close(str(exc))
        else:
            raise chess.engine.EngineError(f"engine process died unexpectedly ({last_exc})")

        if isinstance(infos, dict):
            infos = [infos]

        candidates = tuple(self._candidate_from_info(board, info) for info in infos)
        best = candidates[0] if candidates else CandidateMove("", "", None, None, ())
        depth = max((int(info.get("depth", 0)) for info in infos), default=0)
        return AnalysisResult(
            fen=fen,
            depth=depth,
            best_move_uci=best.move_uci,
            best_move_san=best.move_san,
            score_cp=best.score_cp,
            mate_in=best.mate_in,
            candidates=candidates,
        )

    def _force_close(self, error: str = "") -> None:
        """Drop a dead/misbehaving engine so the next call re-spawns it."""
        if self._engine is not None:
            try:
                self._engine.quit()
            except Exception:  # noqa: BLE001 - the process may already be gone
                pass
        self._engine = None
        self.state.ready = False
        self.state.last_error = error

    def _configure(self) -> None:
        assert self._engine is not None
        options: dict[str, int] = {
            "Threads": max(1, self.settings.threads),
            "Hash": max(16, self.settings.hash_mb),
        }
        if "Skill Level" in self._engine.options:
            options["Skill Level"] = max(0, min(20, self.settings.skill_level))
        self._engine.configure(options)

    def _candidate_from_info(
        self, board: chess.Board, info: chess.engine.InfoDict
    ) -> CandidateMove:
        pv = list(info.get("pv", []))
        move = pv[0] if pv else None
        score = info.get("score")
        pov_score = score.pov(board.turn) if score is not None else None
        score_cp = pov_score.score(mate_score=100000) if pov_score is not None else None
        mate_in = pov_score.mate() if pov_score is not None else None

        san = ""
        uci = ""
        if move is not None:
            uci = move.uci()
            san = board.san(move)
        return CandidateMove(
            move_uci=uci,
            move_san=san,
            score_cp=score_cp if mate_in is None else None,
            mate_in=mate_in,
            pv=tuple(item.uci() for item in pv),
        )
