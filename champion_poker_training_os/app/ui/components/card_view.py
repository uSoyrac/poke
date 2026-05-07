from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class CardView(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setFixedSize(46, 62)
        self.setAlignment(Qt.AlignCenter)
        red = any(s in text.lower() for s in ("h", "d"))
        self.setStyleSheet(
            "background: #E5E7EB; border: 1px solid #2D3748; border-radius: 6px; "
            f"color: {'#EF4444' if red else '#0B0F14'}; font-size: 18px; font-weight: 800;"
        )
