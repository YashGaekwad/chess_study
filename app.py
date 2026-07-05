from __future__ import annotations

import sys

from config import AppSettings
from logger import configure_logging


def run() -> int:
    configure_logging()

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - depends on local desktop env
        print("PySide6 is not installed. Run: python -m pip install -r requirements.txt")
        raise SystemExit(1) from exc

    from ui.main_window import MainWindow

    settings = AppSettings.load()
    application = QApplication(sys.argv)
    application.setApplicationName("Chess Study Assistant")
    window = MainWindow(settings)
    window.show()
    return application.exec()
