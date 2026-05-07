from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


SUIT_COLORS = {
    "♥": "#EF4444", "♦": "#3B82F6",
    "♠": "#E5E7EB", "♣": "#10B981",
    "h": "#EF4444", "d": "#3B82F6",
    "s": "#E5E7EB", "c": "#10B981",
}

SUIT_MAP = {"h": "♥", "d": "♦", "s": "♠", "c": "♣"}


class CardView(QWidget):
    """Premium poker card widget with custom painting."""

    def __init__(self, text: str, face_down: bool = False):
        super().__init__()
        self.card_text = text.strip()
        self.face_down = face_down
        self.setFixedSize(52, 72)
        self.setMinimumSize(52, 72)

        # Parse rank and suit
        self.rank = ""
        self.suit = ""
        self.suit_symbol = ""
        self.suit_color = QColor("#E5E7EB")

        if len(self.card_text) >= 2 and not face_down:
            # Handle both "A♥" and "Ah" formats
            self.rank = self.card_text[0]
            suit_char = self.card_text[1]
            if suit_char in SUIT_MAP:
                self.suit_symbol = SUIT_MAP[suit_char]
            else:
                self.suit_symbol = suit_char
            self.suit_color = QColor(SUIT_COLORS.get(suit_char, SUIT_COLORS.get(self.suit_symbol, "#E5E7EB")))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self.face_down:
            self._paint_back(painter, w, h)
        else:
            self._paint_front(painter, w, h)
        painter.end()

    def _paint_back(self, painter: QPainter, w: int, h: int) -> None:
        # Card back — dark with pattern
        painter.setPen(QPen(QColor("#374151"), 2))
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        # Cross-hatch pattern
        painter.setPen(QPen(QColor("#4B5563"), 1))
        for i in range(3, w, 6):
            painter.drawLine(i, 4, i, h - 4)
        for j in range(4, h, 6):
            painter.drawLine(3, j, w - 3, j)

        # Center diamond
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#22D3EE"))
        cx, cy = w // 2, h // 2
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        painter.drawPolygon(QPolygon([
            QPoint(cx, cy - 8), QPoint(cx + 6, cy),
            QPoint(cx, cy + 8), QPoint(cx - 6, cy),
        ]))

    def _paint_front(self, painter: QPainter, w: int, h: int) -> None:
        # Card background — white with subtle gradient
        painter.setPen(QPen(QColor("#6B7280"), 1))
        painter.setBrush(QColor("#F9FAFB"))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        # Inner highlight
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 60))
        painter.drawRoundedRect(3, 3, w - 6, h // 3, 4, 4)

        if not self.rank:
            return

        # Top-left rank
        font = QFont("Inter", 13, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QPen(self.suit_color, 1))
        painter.drawText(5, 17, self.rank)

        # Top-left suit (small)
        suit_font = QFont("Inter", 9)
        painter.setFont(suit_font)
        painter.drawText(5, 29, self.suit_symbol)

        # Center suit (large)
        center_font = QFont("Inter", 22)
        painter.setFont(center_font)
        painter.drawText(
            0, 0, w, h,
            Qt.AlignCenter,
            self.suit_symbol,
        )

        # Bottom-right rank (inverted)
        painter.setFont(font)
        painter.save()
        painter.translate(w - 5, h - 5)
        painter.rotate(180)
        painter.drawText(0, 12, self.rank)
        painter.restore()

        # Bottom-right suit
        painter.setFont(suit_font)
        painter.save()
        painter.translate(w - 5, h - 18)
        painter.rotate(180)
        painter.drawText(0, 12, self.suit_symbol)
        painter.restore()


class CardBackView(CardView):
    """Convenience class for face-down cards."""
    def __init__(self):
        super().__init__("??", face_down=True)
