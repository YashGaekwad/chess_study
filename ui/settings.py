from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from config import EngineSettings


class EngineSettingsDialog(QDialog):
    def __init__(self, settings: EngineSettings, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Engine Settings")
        self.settings = settings

        self.path = QLineEdit(settings.stockfish_path)
        self.depth = self._spin(1, 50, settings.depth)
        self.skill = self._spin(0, 20, settings.skill_level)
        self.threads = self._spin(1, 64, settings.threads)
        self.hash_mb = self._spin(16, 8192, settings.hash_mb)
        self.time_ms = self._spin(50, 30000, settings.analysis_time_ms)

        form = QFormLayout()
        form.addRow("Stockfish path", self.path)
        form.addRow("Depth", self.depth)
        form.addRow("Skill level", self.skill)
        form.addRow("Threads", self.threads)
        form.addRow("Hash MB", self.hash_mb)
        form.addRow("Analysis time ms", self.time_ms)

        save = QPushButton("Save")
        save.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(save)

    def accept(self) -> None:
        self.settings.stockfish_path = self.path.text().strip() or "stockfish"
        self.settings.depth = self.depth.value()
        self.settings.skill_level = self.skill.value()
        self.settings.threads = self.threads.value()
        self.settings.hash_mb = self.hash_mb.value()
        self.settings.analysis_time_ms = self.time_ms.value()
        super().accept()

    def _spin(self, minimum: int, maximum: int, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin
