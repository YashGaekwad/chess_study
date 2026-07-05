from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_STYLE = """
#card {
    background: rgba(22, 26, 34, 0.97);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 14px;
}
#handle { color: #4b5666; font-size: 15px; }
#caption { color: #8a94a3; font-size: 11px; font-weight: 600; }
QLabel { color: #dfe6ee; }

QPushButton#chip {
    background: transparent;
    color: #b7c0cd;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
}
QPushButton#chip:hover { background: rgba(255, 255, 255, 0.06); color: #ecf0f4; }
QPushButton#chip:checked {
    background: #2e7d46;
    color: #ffffff;
    font-weight: 700;
}

#divider { background: rgba(255, 255, 255, 0.09); }

QSpinBox {
    background: #0e1219;
    color: #ecf0f4;
    border: 1px solid #333d4b;
    border-radius: 8px;
    padding: 3px 4px;
    min-width: 40px;
    font-weight: 600;
}
QSpinBox::up-button, QSpinBox::down-button { width: 16px; border: none; background: transparent; }
QSpinBox::up-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
                     border-bottom: 5px solid #8a94a3; }
QSpinBox::down-arrow { image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
                       border-top: 5px solid #8a94a3; }

QPushButton#reset {
    background: rgba(190, 90, 90, 0.16);
    color: #f0b9b9;
    border: 1px solid rgba(190, 90, 90, 0.45);
    border-radius: 8px;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#reset:hover { background: rgba(190, 90, 90, 0.30); color: #ffffff; }
"""


class OrientationControl(QWidget):
    """Tiny always-on-top toolbar to switch board orientation and engine skill on
    the fly. Draggable so it can be parked anywhere over the game.
    """

    mode_changed = Signal(str)
    clear_requested = Signal()
    skill_changed = Signal(int)

    def __init__(self, mode: str = "auto", skill_level: int = 20) -> None:
        super().__init__()
        self._mode = mode if mode in ("auto", "white", "black") else "auto"
        self._drag_start: QPoint | None = None
        self._excluded_from_capture = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowTitle("Assistant Controls")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Outer margin leaves room for the drop shadow; fixed-size constraint
        # makes the window wrap its contents exactly so the card always covers
        # every control.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 170))
        card.setGraphicsEffect(shadow)

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 9, 12, 9)
        row.setSpacing(8)

        handle = QLabel("⠇")  # braille dots -> drag handle
        handle.setObjectName("handle")
        handle.setCursor(Qt.CursorShape.SizeAllCursor)
        row.addWidget(handle)

        caption = QLabel("PLAYING")
        caption.setObjectName("caption")
        row.addWidget(caption)

        self.btn_auto = self._chip("Auto")
        self.btn_white = self._chip("White")
        self.btn_black = self._chip("Black")
        for button, mode_value in (
            (self.btn_auto, "auto"),
            (self.btn_white, "white"),
            (self.btn_black, "black"),
        ):
            button.clicked.connect(lambda _=False, m=mode_value: self._set_mode(m))
            row.addWidget(button)

        row.addWidget(self._make_divider())

        skill_label = QLabel("LEVEL")
        skill_label.setObjectName("caption")
        row.addWidget(skill_label)
        self.skill_spin = QSpinBox()
        self.skill_spin.setRange(0, 20)
        self.skill_spin.setValue(max(0, min(20, skill_level)))
        self.skill_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        self.skill_spin.setToolTip("Engine skill: 0 = weakest, 20 = full strength")
        self.skill_spin.valueChanged.connect(self.skill_changed.emit)
        row.addWidget(self.skill_spin)

        row.addWidget(self._make_divider())

        self.btn_clear = QPushButton("↺  Reset")
        self.btn_clear.setObjectName("reset")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setToolTip("Clear the arrow/box and restart analysis")
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        row.addWidget(self.btn_clear)

        self.setStyleSheet(_STYLE)
        self._refresh()

    def _chip(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("chip")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def _make_divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedWidth(1)
        line.setFrameShape(QFrame.Shape.VLine)
        return line

    def showEvent(self, event: object) -> None:
        super().showEvent(event)
        if self._excluded_from_capture or not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            if ctypes.windll.user32.SetWindowDisplayAffinity(
                int(self.winId()), WDA_EXCLUDEFROMCAPTURE
            ):
                self._excluded_from_capture = True
        except Exception:  # noqa: BLE001 - best effort
            pass

    def set_mode(self, mode: str) -> None:
        """Update the shown selection without re-emitting the signal."""
        if mode in ("auto", "white", "black"):
            self._mode = mode
            self._refresh()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._refresh()
        self.mode_changed.emit(mode)

    def _refresh(self) -> None:
        self.btn_auto.setChecked(self._mode == "auto")
        self.btn_white.setChecked(self._mode == "white")
        self.btn_black.setChecked(self._mode == "black")

    def mousePressEvent(self, event: object) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: object) -> None:
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_start)

    def mouseReleaseEvent(self, _: object) -> None:
        self._drag_start = None
