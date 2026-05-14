from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


# White-card colour scheme — high contrast on dark UI
SUIT_COLORS = {
    "♥": "#DC2626", "♦": "#2563EB",
    "♠": "#0F1419", "♣": "#059669",
    "h": "#DC2626", "d": "#2563EB",
    "s": "#0F1419", "c": "#059669",
}

SUIT_MAP = {"h": "♥", "d": "♦", "s": "♠", "c": "♣",
            "H": "♥", "D": "♦", "S": "♠", "C": "♣"}


class CardView(QWidget):
    """Premium poker card widget with custom painting.

    Resilient to empty / partial / odd inputs — always paints SOMETHING:
      • empty string → face-down back
      • "??" / "X" → face-down back
      • "A" (no suit) → white card with rank only
      • "A♥" or "Ah" → full card
    """

    def __init__(self, text: str | None = "", face_down: bool = False):
        super().__init__()
        self.card_text = (text or "").strip()
        # Auto-fall-back to face-down for empty/unknown inputs
        if not self.card_text or self.card_text in ("??", "?", "X", "W"):
            face_down = True
        self.face_down = face_down
        self.setFixedSize(52, 72)
        self.setMinimumSize(52, 72)

        # Parse rank and suit (only meaningful when face_up)
        self.rank = ""
        self.suit_symbol = ""
        self.suit_color = QColor("#0F1419")

        if not face_down and self.card_text:
            self.rank = self.card_text[0].upper()
            if self.rank == "T":
                self.rank = "10"
            suit_char = self.card_text[1] if len(self.card_text) > 1 else ""
            if suit_char in SUIT_MAP:
                self.suit_symbol = SUIT_MAP[suit_char]
            elif suit_char in ("♥", "♦", "♠", "♣"):
                self.suit_symbol = suit_char
            else:
                self.suit_symbol = ""
            self.suit_color = QColor(
                SUIT_COLORS.get(suit_char, SUIT_COLORS.get(self.suit_symbol, "#0F1419"))
            )

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
        # Card background — clean white with thin grey border
        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.setBrush(QColor("#FAFAFA"))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)

        # Subtle top highlight for depth
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawRoundedRect(3, 3, w - 6, h // 3, 4, 4)

        if not self.rank:
            return

        # Top-left rank — bigger so it's readable even small
        rank_font = QFont()
        rank_font.setPointSize(14)
        rank_font.setBold(True)
        painter.setFont(rank_font)
        painter.setPen(QPen(self.suit_color))
        # "10" needs slightly less padding
        rank_x = 4 if self.rank == "10" else 5
        painter.drawText(rank_x, 18, self.rank)

        # Top-left suit (small under rank)
        suit_font = QFont()
        suit_font.setPointSize(10)
        suit_font.setBold(True)
        painter.setFont(suit_font)
        painter.drawText(5, 32, self.suit_symbol)

        # Center suit (LARGE — the visual anchor)
        center_font = QFont()
        center_font.setPointSize(26)
        center_font.setBold(True)
        painter.setFont(center_font)
        painter.drawText(0, 0, w, h, Qt.AlignCenter, self.suit_symbol)

        # Bottom-right rank (inverted)
        painter.setFont(rank_font)
        painter.save()
        painter.translate(w - 5, h - 5)
        painter.rotate(180)
        painter.drawText(0, 13, self.rank)
        painter.restore()

        # Bottom-right suit
        painter.setFont(suit_font)
        painter.save()
        painter.translate(w - 5, h - 19)
        painter.rotate(180)
        painter.drawText(0, 13, self.suit_symbol)
        painter.restore()


class CardBackView(CardView):
    """Convenience class for face-down cards."""
    def __init__(self):
        super().__init__("??", face_down=True)
