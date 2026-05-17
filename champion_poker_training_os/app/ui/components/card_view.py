"""CardView — premium poker card widget, font-bağımsız 4-color deck.

User feedback: unicode ♠♥♦♣ glyph'leri bazı sistemlerde render olmuyordu →
'?' gibi görünüyordu. Şimdi suit'ler:
  • Maça (♠) → MAVİ filled rounded shape
  • Kupa (♥) → KIRMIZI heart shape (path-drawn)
  • Karo (♦) → TURUNCU diamond rhombus
  • Sinek (♣) → SARI clover shape (3 circles + stem)

Hiçbir font'a bağımlı değil — saf QPainter primitives.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


# 4-color deck — user's preferred scheme
SUIT_COLORS = {
    "s": "#2563EB",   # MAÇA → MAVİ
    "h": "#DC2626",   # KUPA → KIRMIZI
    "d": "#F59E0B",   # KARO → TURUNCU
    "c": "#EAB308",   # SİNEK → SARI
}

SUIT_NAMES = {"s": "Maça", "h": "Kupa", "d": "Karo", "c": "Sinek"}


def _normalize_suit(s: str) -> str:
    """Tek harfli (s/h/d/c) suit code'una çevir."""
    if not s:
        return ""
    c = s[0]
    if c in "shdc":
        return c
    if c in "SHDC":
        return c.lower()
    if c == "♠": return "s"
    if c == "♥": return "h"
    if c == "♦": return "d"
    if c == "♣": return "c"
    return ""


def paint_suit_shape(painter: QPainter, x: float, y: float, size: float,
                      suit: str) -> None:
    """Suit'i renkli geometrik şekil olarak çiz — hiç font kullanmaz.

    x, y = center coordinates. size = shape diameter approx.
    """
    s = _normalize_suit(suit)
    if not s:
        return
    col = QColor(SUIT_COLORS[s])
    painter.setBrush(QBrush(col))
    painter.setPen(Qt.NoPen)

    half = size / 2

    if s == "s":   # MAÇA → blue spade (path: tear-drop with stem)
        path = QPainterPath()
        # Top point
        path.moveTo(x, y - half)
        # Right curve
        path.cubicTo(x + half * 1.2, y - half * 0.2,
                     x + half, y + half * 0.3,
                     x + half * 0.5, y + half * 0.5)
        # Bottom right notch
        path.cubicTo(x + half * 0.2, y + half * 0.5,
                     x + half * 0.05, y + half * 0.45,
                     x, y + half * 0.35)
        # Bottom left notch
        path.cubicTo(x - half * 0.05, y + half * 0.45,
                     x - half * 0.2, y + half * 0.5,
                     x - half * 0.5, y + half * 0.5)
        # Left curve back
        path.cubicTo(x - half, y + half * 0.3,
                     x - half * 1.2, y - half * 0.2,
                     x, y - half)
        painter.drawPath(path)
        # Stem
        painter.drawPolygon(QPolygonF([
            QPointF(x - half * 0.25, y + half * 0.5),
            QPointF(x + half * 0.25, y + half * 0.5),
            QPointF(x + half * 0.4, y + half * 0.9),
            QPointF(x - half * 0.4, y + half * 0.9),
        ]))

    elif s == "h":   # KUPA → red heart
        path = QPainterPath()
        # Two top lobes meeting at bottom point
        path.moveTo(x, y + half * 0.85)
        path.cubicTo(x - half * 1.1, y + half * 0.1,
                     x - half * 0.9, y - half * 0.9,
                     x, y - half * 0.25)
        path.cubicTo(x + half * 0.9, y - half * 0.9,
                     x + half * 1.1, y + half * 0.1,
                     x, y + half * 0.85)
        painter.drawPath(path)

    elif s == "d":   # KARO → orange diamond (rhombus)
        painter.drawPolygon(QPolygonF([
            QPointF(x, y - half),
            QPointF(x + half * 0.75, y),
            QPointF(x, y + half),
            QPointF(x - half * 0.75, y),
        ]))

    elif s == "c":   # SİNEK → yellow clover (3 circles + stem)
        r = half * 0.4
        painter.drawEllipse(QPointF(x, y - half * 0.45), r, r)         # top
        painter.drawEllipse(QPointF(x - half * 0.5, y + half * 0.15), r, r)  # left
        painter.drawEllipse(QPointF(x + half * 0.5, y + half * 0.15), r, r)  # right
        # Stem
        painter.drawPolygon(QPolygonF([
            QPointF(x - half * 0.2, y + half * 0.1),
            QPointF(x + half * 0.2, y + half * 0.1),
            QPointF(x + half * 0.4, y + half * 0.9),
            QPointF(x - half * 0.4, y + half * 0.9),
        ]))


class CardView(QWidget):
    """Premium poker card — font-bağımsız geometric suit shapes.

    Resilient to empty / partial / odd inputs:
      • empty / "??" / "X" / "W" → face-down back
      • "A" (no suit) → white card with rank only
      • "Ah" / "A♥" → full card with red heart shape
    """

    def __init__(self, text: str | None = "", face_down: bool = False):
        super().__init__()
        self.card_text = (text or "").strip()
        if not self.card_text or self.card_text in ("??", "?", "X", "W"):
            face_down = True
        self.face_down = face_down
        self.setFixedSize(52, 72)
        self.setMinimumSize(52, 72)

        # Parse
        self.rank = ""
        self.suit = ""    # normalized: 'c','d','h','s'
        self.suit_color = QColor("#0F1419")
        if not face_down and self.card_text:
            self.rank = self.card_text[0].upper()
            if self.rank == "T":
                self.rank = "10"
            suit_char = self.card_text[1] if len(self.card_text) > 1 else ""
            self.suit = _normalize_suit(suit_char)
            if self.suit:
                self.suit_color = QColor(SUIT_COLORS[self.suit])

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
        # Card back — dark with cross-hatch
        painter.setPen(QPen(QColor("#374151"), 2))
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)
        painter.setPen(QPen(QColor("#4B5563"), 1))
        for i in range(3, w, 6):
            painter.drawLine(i, 4, i, h - 4)
        for j in range(3, h, 6):
            painter.drawLine(4, j, w - 4, j)

    def _paint_front(self, painter: QPainter, w: int, h: int) -> None:
        # White card body with subtle shadow border
        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.setBrush(QColor("#FAFAFA"))
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 6, 6)
        # Subtle highlight top
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawRoundedRect(3, 3, w - 6, h // 3, 4, 4)

        if not self.rank:
            return

        # Top-left rank (size 14) — coloured per suit
        rank_font = QFont()
        rank_font.setPointSize(14)
        rank_font.setBold(True)
        painter.setFont(rank_font)
        painter.setPen(QPen(self.suit_color))
        rank_x = 4 if self.rank == "10" else 5
        painter.drawText(rank_x, 18, self.rank)

        # Top-left small suit shape just under rank
        paint_suit_shape(painter, 9, 30, 12, self.suit)

        # Center LARGE suit shape — the visual anchor
        paint_suit_shape(painter, w / 2, h / 2 + 3, 28, self.suit)

        # Bottom-right rank (inverted)
        painter.setFont(rank_font)
        painter.setPen(QPen(self.suit_color))
        painter.save()
        painter.translate(w - 5, h - 5)
        painter.rotate(180)
        painter.drawText(0, 13, self.rank)
        painter.restore()

        # Bottom-right small suit
        paint_suit_shape(painter, w - 9, h - 32, 12, self.suit)


class CardBackView(CardView):
    """Convenience class for face-down cards."""
    def __init__(self):
        super().__init__("??", face_down=True)
