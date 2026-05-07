"""Visual chips for poker action sequences (R 2.3, B 75%, C, X, F, AI)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget


# Action -> (background, foreground) colour pair
ACTION_STYLES: dict[str, tuple[str, str]] = {
    "F": ("#1B3A5C", "#5BA9F0"),     # fold = blue
    "C": ("#1F3D24", "#3DD37C"),     # call = green
    "X": ("#1F3D24", "#3DD37C"),     # check = green
    "B": ("#5C1F22", "#F87171"),     # bet = red
    "R": ("#5C1F22", "#F87171"),     # raise = red
    "AI": ("#3D0E10", "#FCA5A5"),    # all-in = darker red
}


def parse_action_token(token: str) -> tuple[str, str]:
    """Return (kind, label) for a token like 'R 2.3', 'B 75%', 'F', 'AI'."""
    token = token.strip()
    if not token:
        return ("F", "F")
    upper = token.upper()
    if upper == "AI" or upper.startswith("AI "):
        return ("AI", "AI")
    head = token[0].upper()
    if head not in ACTION_STYLES:
        head = "F"
    label = token if " " in token or len(token) > 1 else head
    return (head, label)


class ActionChip(QWidget):
    """Single colored pill showing an action like 'R 2.3' or 'B 75%'."""

    def __init__(self, token: str, scale: float = 1.0):
        super().__init__()
        self.kind, self.label = parse_action_token(token)
        self.scale = scale
        bg, _ = ACTION_STYLES[self.kind]
        self._bg = QColor(bg)
        self._fg = QColor(ACTION_STYLES[self.kind][1])
        font = QFont()
        font.setPointSizeF(9.5 * scale)
        font.setBold(True)
        self._font = font
        # measure to size
        metrics = self.fontMetrics()
        text_w = metrics.horizontalAdvance(self.label)
        self.setFixedSize(int(max(28 * scale, text_w + 14 * scale)), int(22 * scale))
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bg)
        painter.drawRoundedRect(rect, 5, 5)
        painter.setFont(self._font)
        painter.setPen(QPen(self._fg))
        painter.drawText(rect, Qt.AlignCenter, self.label)
        painter.end()


class ActionSequence(QWidget):
    """Horizontal row of ActionChips separated by tiny dots, e.g. R 2.3 • R 33% • B 75% • AI."""

    def __init__(self, tokens: list[str], scale: float = 1.0):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for i, token in enumerate(tokens):
            if i > 0:
                dot = QLabel("•")
                dot.setStyleSheet("color: #4B5563; font-weight: 700;")
                layout.addWidget(dot)
            layout.addWidget(ActionChip(token, scale=scale))
        layout.addStretch(1)


def parse_action_string(s: str) -> list[str]:
    """Parse compact strings like 'CRC' or 'BC' or 'XBR' into ['C','R','C']."""
    if not s:
        return []
    # If already contains spaces or %, split sensibly
    if " " in s or "%" in s or "," in s:
        return [t.strip() for t in s.replace(",", " ").split() if t.strip()]
    return list(s)
