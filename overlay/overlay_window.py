from __future__ import annotations

import math
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QWidget

from config import OverlaySettings
from overlay.renderer import OverlayAnalysis, OverlayBoard


class OverlayWindow(QWidget):
    def __init__(self, settings: OverlaySettings) -> None:
        super().__init__()
        self.settings = settings
        self.analysis = OverlayAnalysis()
        self.board = OverlayBoard()
        self._drag_start: QPoint | None = None
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(settings.opacity)
        self._fit_virtual_desktop()
        self._excluded_from_capture = False

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        self._exclude_from_capture()

    def _exclude_from_capture(self) -> None:
        """Hide this window from screen capture so the app never screenshots its
        own arrow/box (which would sit on a piece and break detection).

        Uses WDA_EXCLUDEFROMCAPTURE (Windows 10 2004+ / Windows 11). The overlay
        stays fully visible to the user; it just doesn't appear in captures.
        """
        if self._excluded_from_capture or not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            hwnd = int(self.winId())
            if ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
                self._excluded_from_capture = True
        except Exception:  # noqa: BLE001 - best effort; fall back to the button
            pass

    def update_analysis(self, analysis: OverlayAnalysis, board: OverlayBoard | None = None) -> None:
        self.analysis = analysis
        if board is not None:
            self.board = board
        self.update()

    def paintEvent(self, _: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self._draw_board_arrow(painter)
        self._draw_status_panel(painter)

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: object) -> None:
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, _: object) -> None:
        self._drag_start = None

    def _fit_virtual_desktop(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.setGeometry(self.settings.left, self.settings.top, self.settings.width, self.settings.height)
            return
        geometry = screen.virtualGeometry()
        self.setGeometry(geometry)

    def _draw_board_arrow(self, painter: QPainter) -> None:
        if self.board.size <= 0 or len(self.analysis.best_move_uci) < 4:
            return

        source = self.analysis.best_move_uci[:2]
        target = self.analysis.best_move_uci[2:4]
        source_center = self._square_center(source)
        target_center = self._square_center(target)
        if source_center is None or target_center is None:
            return

        offset = self.geometry().topLeft()
        start = QPoint(source_center.x() - offset.x(), source_center.y() - offset.y())
        end = QPoint(target_center.x() - offset.x(), target_center.y() - offset.y())
        square_size = self.board.size / 8.0

        painter.setBrush(QColor(88, 166, 255, 70))
        painter.setPen(QPen(QColor(88, 166, 255, 190), 4))
        painter.drawRoundedRect(
            int(start.x() - square_size / 2),
            int(start.y() - square_size / 2),
            int(square_size),
            int(square_size),
            8,
            8,
        )
        painter.setBrush(QColor(95, 220, 120, 85))
        painter.drawRoundedRect(
            int(end.x() - square_size / 2),
            int(end.y() - square_size / 2),
            int(square_size),
            int(square_size),
            8,
            8,
        )

        painter.setPen(QPen(QColor(255, 184, 77, 235), max(8, int(square_size * 0.09)), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(start, end)
        self._draw_arrow_head(painter, start, end, max(22, int(square_size * 0.24)))

    def _draw_status_panel(self, painter: QPainter) -> None:
        if self.board.size > 0:
            offset = self.geometry().topLeft()
            panel_left = self.board.left - offset.x()
            panel_top = max(12, self.board.top - offset.y() - 88)
        else:
            panel_left = 24
            panel_top = 24

        width = 360
        height = 74
        painter.setBrush(QColor(20, 24, 30, 215))
        painter.setPen(QPen(QColor(95, 180, 120), 2))
        painter.drawRoundedRect(panel_left, panel_top, width, height, 8, 8)
        painter.setPen(QColor(235, 238, 244))
        painter.drawText(panel_left + 14, panel_top + 28, f"Move: {self.analysis.best_move or '-'}")
        painter.drawText(
            panel_left + 14,
            panel_top + 54,
            f"Eval: {self.analysis.evaluation or '-'}   Depth: {self.analysis.depth}",
        )

    def _square_center(self, square: str) -> QPoint | None:
        if len(square) != 2 or square[0] not in "abcdefgh" or square[1] not in "12345678":
            return None
        file_index = "abcdefgh".index(square[0])
        rank_index = "12345678".index(square[1])
        if self.board.flipped:
            col = 7 - file_index
            row = rank_index
        else:
            col = file_index
            row = 7 - rank_index
        square_size = self.board.size / 8.0
        return QPoint(
            int(self.board.left + (col + 0.5) * square_size),
            int(self.board.top + (row + 0.5) * square_size),
        )

    def _draw_arrow_head(self, painter: QPainter, start: QPoint, end: QPoint, size: int) -> None:
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        left = QPoint(
            int(end.x() - size * math.cos(angle - math.pi / 6)),
            int(end.y() - size * math.sin(angle - math.pi / 6)),
        )
        right = QPoint(
            int(end.x() - size * math.cos(angle + math.pi / 6)),
            int(end.y() - size * math.sin(angle + math.pi / 6)),
        )
        painter.setBrush(QColor(255, 184, 77, 235))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([end, left, right]))
