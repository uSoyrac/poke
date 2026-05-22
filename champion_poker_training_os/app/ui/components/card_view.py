from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygon, QLinearGradient
from PySide6.QtWidgets import QWidget


SUIT_GLYPH = {
    "h": "♥", "d": "♦",
    "s": "♠", "c": "♣",
    "♥": "♥", "♦": "♦",
    "♠": "♠", "♣": "♣",
}

RED_SUITS = {"♥", "h", "♦", "d"}


class CardView(QWidget):
    """Brutalist poker card — sharp corners, mono rank, suit glyph."""

    def __init__(self, text: str, face_down: bool = False, size: str = "md"):
        super().__init__()
        self.card_text = (text or "").strip()
        self.face_down = face_down
        self.size_key = size

        sizes = {
            "xs": (22, 30),
            "sm": (32, 44),
            "md": (44, 60),
            "lg": (60, 84),
            "xl": (80, 112),
        }
        w, h = sizes.get(size, sizes["md"])
        self.setFixedSize(w, h)

        self.rank = ""
        self.suit_char = ""
        self.suit_glyph = ""
        self.is_red = False
        if len(self.card_text) >= 2 and not face_down:
            self.rank = self.card_text[0].upper()
            if self.rank == "1" and self.card_text[1] == "0":
                self.rank = "T"
                suit_raw = self.card_text[2] if len(self.card_text) > 2 else ""
            else:
                suit_raw = self.card_text[1]
            self.suit_glyph = SUIT_GLYPH.get(suit_raw, suit_raw)
            self.is_red = suit_raw in RED_SUITS

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        w, h = self.width(), self.height()
        if self.face_down:
            self._paint_back(painter, w, h)
        else:
            self._paint_front(painter, w, h)
        painter.end()

    def _paint_back(self, painter: QPainter, w: int, h: int) -> None:
        painter.fillRect(0, 0, w, h, QColor("#5ad17a"))
        # diagonal stripes
        painter.setPen(QPen(QColor("#0a0c0a"), 1))
        for i in range(-h, w, 4):
            painter.drawLine(i, 0, i + h, h)
        # frame
        painter.setPen(QPen(QColor("#0a0c0a"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, w - 1, h - 1)

    def _paint_front(self, painter: QPainter, w: int, h: int) -> None:
        # Card body — solid ink (--ink: #f4f5ee)
        painter.fillRect(0, 0, w, h, QColor("#f4f5ee"))
        painter.setPen(QPen(QColor("#33382c"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, w - 1, h - 1)

        if not self.rank:
            return

        text_color = QColor("#e87474") if self.is_red else QColor("#0a0c0a")

        # Big centered rank
        rank_size = max(14, int(h * 0.42))
        rank_font = QFont("Space Grotesk", rank_size)
        rank_font.setWeight(QFont.Bold)
        rank_font.setLetterSpacing(QFont.AbsoluteSpacing, -1.5)
        painter.setFont(rank_font)
        painter.setPen(QPen(text_color, 1))
        painter.drawText(0, 0, w, h, Qt.AlignCenter, self.rank)

        # Bottom-right suit glyph
        suit_size = max(8, int(h * 0.16))
        suit_font = QFont("Space Grotesk", suit_size)
        suit_font.setWeight(QFont.Bold)
        painter.setFont(suit_font)
        painter.drawText(0, 0, w - 4, h - 3, Qt.AlignRight | Qt.AlignBottom, self.suit_glyph)

        # Top-left suit glyph
        painter.drawText(4, 3, w, h, Qt.AlignLeft | Qt.AlignTop, self.suit_glyph)


class CardBackView(CardView):
    def __init__(self, size: str = "md"):
        super().__init__("??", face_down=True, size=size)


class CardPlaceholder(QWidget):
    """Empty card slot (faint outline)."""
    def __init__(self, size: str = "md"):
        super().__init__()
        sizes = {"xs": (22, 30), "sm": (32, 44), "md": (44, 60), "lg": (60, 84)}
        w, h = sizes.get(size, sizes["md"])
        self.setFixedSize(w, h)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        pen = QPen(QColor("#23271f"), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        painter.end()
