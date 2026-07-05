from __future__ import annotations

import logging
import time

import chess
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QAction, QImage, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from capture.screen_capture import ScreenCapture
from capture.window_detector import WindowDetector, WindowInfo
from config import ASSETS_DIR, AppSettings, CaptureRegion
from engine.analysis import AnalysisResult
from engine.stockfish_engine import StockfishEngine
from overlay.overlay_window import OverlayWindow
from overlay.renderer import OverlayAnalysis, OverlayBoard
from ui.orientation_control import OrientationControl
from ui.settings import EngineSettingsDialog
from vision.board_detector import BoardDetection, BoardDetector
from vision.fen_generator import FenGenerator
from vision.piece_detector import TemplatePieceDetector

LOGGER = logging.getLogger(__name__)


class AnalysisWorker(QThread):
    status_changed = Signal(str)
    frame_ready = Signal(QImage)
    fen_ready = Signal(str, bool, str)
    analysis_ready = Signal(object)
    board_ready = Signal(object)
    overlay_clear = Signal()
    stats_ready = Signal(str)

    def __init__(self, settings: AppSettings, region: CaptureRegion) -> None:
        super().__init__()
        self.settings = settings
        self.region = region
        self.paused = False
        self.running = True
        self.board_detector = BoardDetector()
        self.fen_generator = FenGenerator()
        self.piece_detector = TemplatePieceDetector(ASSETS_DIR / "pieces" / "chesscom")
        self.engine = StockfishEngine(settings.engine)
        self.last_fen = ""
        self.last_seen_position = ""
        self.last_analyzed_board: chess.Board | None = None
        self.last_best_move_uci = ""
        self.waiting_for_opponent = False
        self.last_recognition_at = 0.0
        self.last_preview_at = 0.0
        # Debounce: only act on a position once it has been detected identically
        # across a couple of consecutive frames, so noisy recognition can't make
        # the arrow flicker between moves.
        self._pending_position = ""
        self._pending_count = 0
        self._stable_frames_required = 2
        # Orientation: "auto" detects it; "white"/"black" force it. _flipped_lock
        # caches the confident auto reading (None until determined).
        self._orientation_mode = settings.gameplay.orientation_mode
        self._flipped_lock: bool | None = None
        # Skill level to apply on the worker thread before the next analysis.
        self._pending_skill: int | None = None

    def set_orientation_mode(self, mode: str) -> None:
        """Change orientation on the fly and force an immediate re-read."""
        self._orientation_mode = mode
        self._flipped_lock = None
        self.last_seen_position = ""
        self._pending_position = ""
        self._pending_count = 0

    def set_skill_level(self, level: int) -> None:
        """Queue a skill change; applied on the worker thread before next analysis."""
        self._pending_skill = level
        self.last_seen_position = ""

    def run(self) -> None:
        frame_count = 0
        started = time.perf_counter()
        interval = 1.0 / max(1, min(self.settings.capture.fps, 60))

        try:
            with ScreenCapture() as capture:
                while self.running:
                    if self.paused:
                        self.msleep(100)
                        continue

                    loop_start = time.perf_counter()
                    frame = capture.capture_region(self.region)
                    now = time.perf_counter()
                    detection = None
                    should_recognize = (
                        now - self.last_recognition_at
                    ) >= self.settings.gameplay.recognition_interval_ms / 1000.0

                    if should_recognize:
                        self.last_recognition_at = now
                        detection = self.board_detector.detect(frame.image)

                        if detection is None:
                            self.status_changed.emit("Board detection failed; retrying")
                        else:
                            self._emit_preview(frame.image, detection)
                            self._process_board(frame.image, detection)
                    elif now - self.last_preview_at >= 0.5:
                        self._emit_preview(frame.image, None)

                    frame_count += 1
                    elapsed = max(time.perf_counter() - started, 0.001)
                    self.stats_ready.emit(f"Capture FPS: {frame_count / elapsed:.1f}")

                    sleep_for = interval - (time.perf_counter() - loop_start)
                    if sleep_for > 0:
                        self.msleep(int(sleep_for * 1000))
        except Exception as exc:
            LOGGER.exception("Analysis worker failed")
            self.status_changed.emit(f"Error: {exc}")
        finally:
            try:
                self.engine.close()
            except Exception:  # noqa: BLE001 - never let teardown crash the thread
                LOGGER.exception("Engine close failed")

    def stop(self) -> None:
        self.running = False

    def _process_board(self, image: object, detection: BoardDetection) -> None:
        cells = self.piece_detector.detect_cells(image, detection)

        # Auto-detect orientation: your own pieces sit on the bottom of the
        # screen, so whichever colour is lower is the player's colour. This maps
        # squares correctly (a board read the wrong way round gives a rotated
        # position and a wrong move) without needing the colour dropdown.
        detection.flipped = self._detect_orientation(cells)
        player_color = chess.BLACK if detection.flipped else chess.WHITE

        pieces = self.piece_detector.map_cells(cells, detection)
        fen_result = self.fen_generator.generate(pieces, side_to_move=player_color)
        self.fen_ready.emit(fen_result.fen, fen_result.valid, "; ".join(fen_result.errors))

        if not self.piece_detector.has_templates:
            self.status_changed.emit("Board found. Add piece templates to enable FEN analysis.")
            return
        if not fen_result.valid:
            # Noisy frame (e.g. a king briefly missed). Reset the debounce and
            # wait for a clean read instead of disturbing the arrow.
            self._pending_position = ""
            self._pending_count = 0
            return

        current_board = chess.Board(fen_result.fen)
        # Skip illegal-but-parseable positions; these crash Stockfish.
        if not current_board.is_valid():
            self._pending_position = ""
            self._pending_count = 0
            return

        current_position = current_board.board_fen()

        # Require the same position across a few consecutive frames before acting
        # on it, so transient mis-reads don't make the arrow jump around.
        if current_position != self._pending_position:
            self._pending_position = current_position
            self._pending_count = 1
            return
        self._pending_count += 1
        if self._pending_count < self._stable_frames_required:
            return

        if current_position == self.last_seen_position:
            return
        self.last_seen_position = current_position

        self.board_ready.emit(
            OverlayBoard(
                left=self.region.left + detection.left,
                top=self.region.top + detection.top,
                size=detection.size,
                flipped=detection.flipped,
            )
        )

        if self._is_user_move_on_board(current_board):
            self.waiting_for_opponent = True
            self.overlay_clear.emit()
            self.status_changed.emit("Your move detected. Waiting for opponent.")
            return

        if self.waiting_for_opponent:
            self.status_changed.emit("Opponent moved. Finding your next move.")

        self.last_fen = fen_result.fen
        if self._pending_skill is not None:
            self.engine.set_skill_level(self._pending_skill)
            self._pending_skill = None
        self.status_changed.emit("Analyzing position")
        try:
            result = self.engine.analyze(fen_result.fen)
        except Exception as exc:  # noqa: BLE001 - keep the worker alive on engine faults
            LOGGER.warning("Analysis skipped: %s", exc)
            self.status_changed.emit("Engine hiccup; recovering")
            # Allow this position to be retried on the next stable read.
            self.last_seen_position = ""
            return

        self.last_analyzed_board = current_board
        self.last_best_move_uci = result.best_move_uci
        self.waiting_for_opponent = False
        self.analysis_ready.emit(result)

    def _detect_orientation(self, cells: list[tuple[int, int, str, float]]) -> bool:
        """Return True if the board is shown from black's side (flipped).

        A forced mode ("white"/"black") wins immediately. Otherwise it's decided
        by which colour's pieces are lower on screen, falling back to the last
        confident reading (or the colour dropdown) when it's ambiguous, and
        locking the result so it doesn't flicker mid-game.
        """
        if self._orientation_mode == "white":
            return False
        if self._orientation_mode == "black":
            return True

        fallback = (
            self._flipped_lock
            if self._flipped_lock is not None
            else self.settings.gameplay.player_color.lower() == "black"
        )
        white_rows = [row for row, _, code, _ in cells if code.startswith("w")]
        black_rows = [row for row, _, code, _ in cells if code.startswith("b")]
        if len(white_rows) < 2 or len(black_rows) < 2:
            return fallback

        white_mean = sum(white_rows) / len(white_rows)
        black_mean = sum(black_rows) / len(black_rows)
        if abs(white_mean - black_mean) < 0.75:
            return fallback  # too symmetric to be sure

        flipped = black_mean > white_mean  # black lower on screen -> playing black
        if flipped != self._flipped_lock:
            self._flipped_lock = flipped
            self.status_changed.emit(
                f"Detected orientation: playing {'black' if flipped else 'white'}"
            )
        return flipped

    def _is_user_move_on_board(self, current_board: chess.Board) -> bool:
        if self.last_analyzed_board is None:
            return False
        for move in self.last_analyzed_board.legal_moves:
            expected = self.last_analyzed_board.copy(stack=False)
            expected.push(move)
            if current_board.board_fen() == expected.board_fen():
                return True
        return False

    def _emit_preview(self, image: object, detection: BoardDetection | None) -> None:
        import cv2

        preview = image.copy()
        self.last_preview_at = time.perf_counter()
        if detection is not None:
            cv2.rectangle(
                preview,
                (detection.left, detection.top),
                (detection.right, detection.bottom),
                (95, 180, 120),
                3,
            )
        height, width = preview.shape[:2]
        bytes_per_line = width * 3
        qimage = QImage(preview.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        self.frame_ready.emit(qimage.copy())


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self.worker: AnalysisWorker | None = None
        self.window_detector = WindowDetector()
        self.windows: list[WindowInfo] = []
        self.overlay = OverlayWindow(settings.overlay)
        self.latest_board = OverlayBoard()

        self.orientation_control = OrientationControl(
            settings.gameplay.orientation_mode, settings.engine.skill_level
        )
        self.orientation_control.mode_changed.connect(self._set_orientation_mode)
        self.orientation_control.clear_requested.connect(self.clear_and_restart)
        self.orientation_control.skill_changed.connect(self._set_skill_level)

        self.setWindowTitle("Chess Study Assistant")
        self.resize(1180, 760)
        self._build_ui()
        self._build_shortcuts()
        self._apply_theme()
        self.refresh_windows()

        if settings.overlay.visible:
            self.overlay.show()
        # Park the on-the-fly toggle near the top-left of the overlay area.
        self.orientation_control.move(settings.overlay.left + 24, settings.overlay.top + 24)
        self.orientation_control.show()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        self.window_combo = QComboBox()
        self.color_combo = QComboBox()
        self.color_combo.addItems(["White", "Black"])
        self.color_combo.setCurrentText(self.settings.gameplay.player_color.title())
        self.start_button = QPushButton("Start Analysis")
        self.stop_button = QPushButton("Stop")
        self.pause_button = QPushButton("Pause")
        self.resume_button = QPushButton("Resume")
        self.refresh_button = QPushButton("Refresh Detection")
        self.settings_button = QPushButton("Engine Settings")

        for widget in (
            self.window_combo,
            self.color_combo,
            self.start_button,
            self.stop_button,
            self.pause_button,
            self.resume_button,
            self.refresh_button,
            self.settings_button,
        ):
            toolbar.addWidget(widget)
        root.addLayout(toolbar)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.preview = QLabel("Board preview")
        self.preview.setMinimumSize(520, 420)
        self.preview.setScaledContents(True)
        left_layout.addWidget(self.preview)

        right = QWidget()
        grid = QGridLayout(right)
        self.status_label = QLabel("Idle")
        self.stats_label = QLabel("Capture FPS: 0.0")
        self.fen_text = QPlainTextEdit()
        self.fen_text.setReadOnly(True)
        self.eval_text = QTextEdit()
        self.eval_text.setReadOnly(True)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)

        grid.addWidget(QLabel("Status"), 0, 0)
        grid.addWidget(self.status_label, 0, 1)
        grid.addWidget(QLabel("Performance"), 1, 0)
        grid.addWidget(self.stats_label, 1, 1)
        grid.addWidget(QLabel("Current Position"), 2, 0, 1, 2)
        grid.addWidget(self.fen_text, 3, 0, 1, 2)
        grid.addWidget(QLabel("Evaluation"), 4, 0, 1, 2)
        grid.addWidget(self.eval_text, 5, 0, 1, 2)
        grid.addWidget(QLabel("Logs"), 6, 0, 1, 2)
        grid.addWidget(self.logs, 7, 0, 1, 2)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([640, 520])
        root.addWidget(splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        self.start_button.clicked.connect(self.start_analysis)
        self.stop_button.clicked.connect(self.stop_analysis)
        self.pause_button.clicked.connect(self.pause_analysis)
        self.resume_button.clicked.connect(self.resume_analysis)
        self.refresh_button.clicked.connect(self.refresh_windows)
        self.settings_button.clicked.connect(self.show_engine_settings)

    def _build_shortcuts(self) -> None:
        shortcuts = [
            ("F1", self.start_analysis),
            ("F2", self.pause_analysis),
            ("F3", self.resume_analysis),
            ("F4", self.toggle_overlay),
            ("F5", self.refresh_windows),
            ("F6", self.show_engine_settings),
            ("Esc", self.close),
        ]
        for key, callback in shortcuts:
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(callback)
            self.addAction(action)

    def _apply_theme(self) -> None:
        if not self.settings.ui.dark_mode:
            return
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #151922; color: #ecf0f4; }
            QPushButton, QComboBox { background: #242b36; border: 1px solid #3b4554; padding: 7px; }
            QPushButton:hover { background: #303948; }
            QPlainTextEdit, QTextEdit { background: #0f131a; border: 1px solid #333d4b; color: #dfe6ee; }
            QLabel { color: #ecf0f4; }
            """
        )

    def refresh_windows(self) -> None:
        self.windows = self.window_detector.list_windows()
        self.window_combo.clear()
        for window in self.windows:
            label = f"{window.title} ({window.region.width}x{window.region.height})"
            self.window_combo.addItem(label)

        chess_window = self.window_detector.find_chesscom_window()
        if chess_window:
            for index, window in enumerate(self.windows):
                if window.handle == chess_window.handle:
                    self.window_combo.setCurrentIndex(index)
                    break
            self._log(f"Detected Chess.com window: {chess_window.title}")
        else:
            self._log("No Chess.com window found. Select a browser window manually.")

    def start_analysis(self) -> None:
        if self.worker is not None:
            return
        self.settings.gameplay.player_color = self.color_combo.currentText().lower()
        self.settings.save()
        region = self._selected_region()
        self.worker = AnalysisWorker(self.settings, region)
        self.worker.status_changed.connect(self._set_status)
        self.worker.frame_ready.connect(self._set_preview)
        self.worker.fen_ready.connect(self._set_fen)
        self.worker.analysis_ready.connect(self._set_analysis)
        self.worker.board_ready.connect(self._set_overlay_board)
        self.worker.overlay_clear.connect(self._clear_overlay_arrow)
        self.worker.stats_ready.connect(self.stats_label.setText)
        self.worker.start()
        self._set_status("Analysis started")

    def stop_analysis(self) -> None:
        if self.worker is None:
            return
        worker = self.worker
        # Drop our reference only after the thread has actually finished, so the
        # QThread is never destroyed while still running (which aborts the app).
        self.worker = None
        worker.stop()
        if not worker.wait(5000):
            LOGGER.warning("Analysis worker did not stop in time; terminating")
            worker.terminate()
            worker.wait(2000)
        self._set_status("Stopped")

    def pause_analysis(self) -> None:
        if self.worker:
            self.worker.paused = True
            self._set_status("Paused")

    def resume_analysis(self) -> None:
        if self.worker:
            self.worker.paused = False
            self._set_status("Running")

    def toggle_overlay(self) -> None:
        self.overlay.setVisible(not self.overlay.isVisible())

    def _set_orientation_mode(self, mode: str) -> None:
        self.settings.gameplay.orientation_mode = mode
        if self.worker is not None:
            self.worker.set_orientation_mode(mode)
        self._log(f"Orientation: {mode}")

    def _set_skill_level(self, level: int) -> None:
        self.settings.engine.skill_level = max(0, min(20, level))
        if self.worker is not None:
            self.worker.set_skill_level(self.settings.engine.skill_level)
        self._log(f"Skill level: {self.settings.engine.skill_level}")

    def clear_and_restart(self) -> None:
        # Wipe any arrow/box so the next capture is clean, then restart analysis.
        self.latest_board = OverlayBoard()
        self.overlay.update_analysis(OverlayAnalysis(), self.latest_board)
        if self.worker is not None:
            self.stop_analysis()
        self.start_analysis()
        self._log("Cleared overlay and restarted analysis")

    def show_engine_settings(self) -> None:
        dialog = EngineSettingsDialog(self.settings.engine, self)
        if dialog.exec():
            self.settings.save()
            self._log("Engine settings saved")

    def closeEvent(self, event: object) -> None:
        self.stop_analysis()
        self.settings.overlay.left = self.overlay.x()
        self.settings.overlay.top = self.overlay.y()
        self.settings.overlay.width = self.overlay.width()
        self.settings.overlay.height = self.overlay.height()
        self.settings.overlay.visible = self.overlay.isVisible()
        self.settings.gameplay.player_color = self.color_combo.currentText().lower()
        self.settings.save()
        self.orientation_control.close()
        self.overlay.close()
        event.accept()

    def _selected_region(self) -> CaptureRegion:
        if self.settings.capture.manual_region is not None:
            return self.settings.capture.manual_region
        index = self.window_combo.currentIndex()
        if 0 <= index < len(self.windows):
            return self.windows[index].region
        return ScreenCapture().primary_monitor_region()

    def _set_preview(self, image: QImage) -> None:
        self.preview.setPixmap(QPixmap.fromImage(image))

    def _set_fen(self, fen: str, valid: bool, errors: str) -> None:
        self.fen_text.setPlainText(fen)
        if not valid and errors:
            self._log(errors)

    def _set_analysis(self, result: AnalysisResult) -> None:
        lines = [
            f"Best move: {result.best_move_san} ({result.best_move_uci})",
            f"Evaluation: {result.evaluation_text}",
            f"Depth: {result.depth}",
            "",
            "Top candidates:",
        ]
        candidate_labels = []
        for index, candidate in enumerate(result.candidates, start=1):
            score = f"mate {candidate.mate_in}" if candidate.mate_in is not None else f"{(candidate.score_cp or 0) / 100:+.2f}"
            line = f"{index}. {candidate.move_san} {score} PV: {' '.join(candidate.pv[:8])}"
            candidate_labels.append(f"{candidate.move_san} {score}")
            lines.append(line)
        self.eval_text.setPlainText("\n".join(lines))
        self.overlay.update_analysis(
            OverlayAnalysis(
                best_move=result.best_move_san,
                best_move_uci=result.best_move_uci,
                evaluation=result.evaluation_text,
                depth=result.depth,
                candidates=tuple(candidate_labels),
            ),
            self.latest_board,
        )

    def _set_overlay_board(self, board: OverlayBoard) -> None:
        self.latest_board = board

    def _clear_overlay_arrow(self) -> None:
        self.overlay.update_analysis(
            OverlayAnalysis(
                best_move="Waiting for opponent",
                best_move_uci="",
                evaluation="",
                depth=0,
            ),
            self.latest_board,
        )

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.statusBar().showMessage(text)
        self._log(text)

    def _log(self, text: str) -> None:
        self.logs.appendPlainText(text)
