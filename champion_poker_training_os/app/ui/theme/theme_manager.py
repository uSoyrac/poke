from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.config import THEME_PATH


def apply_dark_theme(app: QApplication, path: Path = THEME_PATH) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(path.read_text(encoding="utf-8"))

