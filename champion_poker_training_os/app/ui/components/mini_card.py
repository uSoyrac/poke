"""Compact poker card chip for inline use in tables / lists."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget


SUIT_COLORS = {
    "h": "#EF4444",
    "d": "#3B82F6",
    "s": "#10B981",
    "c": "#9CA3AF",
}
SUIT_BG = {
    "h": "#5C1F22",
    "d": "#1E3A5C",
    "s": "#0E2A1E",
    "c": "#2A2F3A",
}


def card_bg(card: str) -> str:
    if not card or len(card) < 2:
        return "#2A2F3A"
    suit = card[1].lower()
    return SUIT_BG.get(suit, "#2A2F3A")


def card_fg(card: str) -> str:
    if not card or len(card) < 2:
        return "#E5E7EB"
    suit = card[1].lower()
    return SUIT_COLORS.get(suit, "#E5E7EB")


class MiniCard(QWidget):
    """Tiny card chip showing just a rank, with suit-tinted background."""

    def __init__(self, card: str, size: int = 22):
        super().__init__()
        self.card = card or "??"
        self._size = size
        self.setFixedSize(size, size + 6)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(card_bg(self.card)))
        painter.drawRoundedRect(rect, 3, 3)
        rank = self.card[0] if self.card else "?"
        font = QFont(); font.setPointSize(10); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#F3F4F6")))
        painter.drawText(rect, Qt.AlignCenter, rank)
        painter.end()


class MiniCardRow(QWidget):
    """Inline row of MiniCard chips for use as a QTableWidget cell widget."""

    def __init__(self, cards: list[str], size: int = 22):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        for c in cards:
            layout.addWidget(MiniCard(c, size=size))
        layout.addStretch(1)
