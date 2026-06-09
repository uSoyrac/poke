from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QWidget


SUIT_GLYPH = {
    "h": "♥", "d": "♦",
    "s": "♠", "c": "♣",
    "♥": "♥", "♦": "♦",
    "♠": "♠", "♣": "♣",
}

# 4-Color Deck (4CD) — online poker convention. Each suit gets its own
# colour so the user can read holdings at a glance, especially at small
# card sizes where the glyph alone is hard to distinguish.
#
#   ♠ Spades   — orange     (the only one outside the design's 4 semantic
#                            colours; needed because we have 4 suits and
#                            only 3 of {accent, danger, info} read as
#                            distinct hues)
#   ♥ Hearts   — danger red (classic)
#   ♦ Diamonds — blue       (distinct from hearts to avoid red/red mixup)
#   ♣ Clubs    — accent lime (distinct from spades to avoid orange/orange)
SUIT_COLORS = {
    "s": "#f0a04b", "♠": "#f0a04b",   # spades  → orange
    "h": "#e87474", "♥": "#e87474",   # hearts  → red
    "d": "#5a9eef", "♦": "#5a9eef",   # diamonds → blue
    "c": "#5ad17a", "♣": "#5ad17a",   # clubs   → green
}

# Kept for back-compat with any other module that imported RED_SUITS.
RED_SUITS = {"♥", "h", "♦", "d"}


class CardView(QWidget):
    """Brutalist poker card — sharp corners, mono rank, suit glyph."""

    def __init__(self, text: str, face_down: bool = False, size: str = "md",
                 peekable: bool = False):
        super().__init__()
        self.card_text = (text or "").strip()
        self.face_down = face_down
        self.size_key = size
        # D137: fold sonrası kapalı kart — mouse ile üzerine gelince yüzü
        # yarı-saydam görünsün (ne fold ettiğini gör). peekable=True olunca aktif.
        self.peekable = peekable
        self._peek = False

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
        self.suit_color = "#0a0c0a"   # fallback ink — overridden per suit
        # Veriyi HER ZAMAN ayrıştır (face_down olsa da) → peek için yüz çizilebilir
        if len(self.card_text) >= 2:
            self.rank = self.card_text[0].upper()
            if self.rank == "1" and self.card_text[1] == "0":
                self.rank = "T"
                suit_raw = self.card_text[2] if len(self.card_text) > 2 else ""
            else:
                suit_raw = self.card_text[1]
            self.suit_glyph = SUIT_GLYPH.get(suit_raw, suit_raw)
            self.suit_char = suit_raw
            self.suit_color = SUIT_COLORS.get(suit_raw, "#0a0c0a")
            self.is_red = suit_raw in RED_SUITS

    def enterEvent(self, event) -> None:
        if self.peekable and self.face_down and self.rank:
            self._peek = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._peek:
            self._peek = False
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        w, h = self.width(), self.height()
        if self.face_down and self._peek and self.rank:
            # D137: peek — kapalı kartın yüzünü YARI-SAYDAM ama OKUNUR göster.
            # Önce arkalığı karart (her suit rengi okunsun), sonra yüzü %82 çiz.
            self._paint_back(painter, w, h)
            painter.fillRect(0, 0, w, h, QColor(8, 10, 8, 165))
            painter.setOpacity(0.82)
            self._paint_front(painter, w, h)
            painter.setOpacity(1.0)
        elif self.face_down:
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

        # Suit-specific colour (4-Color Deck). The rank + both suit glyphs
        # share the same colour so the card reads as one chromatic unit.
        text_color = QColor(self.suit_color)

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


def hand_key_to_cards(hand_key: str) -> tuple[str, str]:
    """'AKs'/'QJo'/'77' → iki somut kart kodu (CardView için).

    Suited → aynı suit (♠♠), offsuit → ayrı renk (♠♥), pair → ♠♥.
    Geçersiz girdide ('') boş döner.
    """
    hk = (hand_key or "").strip()
    if len(hk) < 2:
        return ("", "")
    r1, r2 = hk[0].upper(), hk[1].upper()
    if len(hk) == 2 or r1 == r2:            # pair: 77 → 7s 7h
        return (f"{r1}s", f"{r2}h")
    if hk.endswith("s"):                    # suited: AKs → As Ks
        return (f"{r1}s", f"{r2}s")
    return (f"{r1}s", f"{r2}h")             # offsuit: AKo → As Kh


def cards_from_string(s: str) -> list[str]:
    """'KsQh8s' / 'Ah 7c 2d' / 'QdQs' → ['Ks','Qh','8s'] kart kodları.

    Boşlukları yok sayar; 'T' ve '10' rank'lerini destekler.
    """
    s = (s or "").replace(" ", "")
    out: list[str] = []
    i = 0
    while i < len(s) - 1:
        if s[i] == "1" and i + 2 < len(s) and s[i + 1] == "0":
            out.append("T" + s[i + 2])
            i += 3
        else:
            out.append(s[i] + s[i + 1])
            i += 2
    return out


class CardRow(QWidget):
    """Yatay kart dizisi (board / hero) — güvenilir CardView'lerden.

    ``set_cards('KsQh8s', size='md')`` ile güncellenir; boş string → boş.
    """

    def __init__(self, size: str = "md", parent=None):
        super().__init__(parent)
        self._size = size
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(6)
        self._lay.setAlignment(Qt.AlignLeft)

    def set_cards(self, cards: str, size: str | None = None) -> None:
        size = size or self._size
        while self._lay.count():
            it = self._lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for code in cards_from_string(cards):
            self._lay.addWidget(CardView(code, size=size))


class TwoCardHand(QWidget):
    """Hero'nun iki hole-card'ını güvenilir CardView ile gösterir.

    Sabit boyutlu CardView kullanır → manuel paintEvent geometri/genişlik
    kırılganlığı yok. ``set_hand('AKs')`` ile güncellenir.
    """

    def __init__(self, size: str = "xl", parent=None):
        super().__init__(parent)
        self._size = size
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(10)
        self._lay.setAlignment(Qt.AlignCenter)
        self._c1 = None
        self._c2 = None
        self.set_hand("AKs")

    def set_hand(self, hand_key: str) -> None:
        code1, code2 = hand_key_to_cards(hand_key)
        # CardView içeriğini __init__'te parse eder → yeniden yaratırız (ucuz)
        while self._lay.count():
            it = self._lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._c1 = CardView(code1, size=self._size)
        self._c2 = CardView(code2, size=self._size)
        self._lay.addWidget(self._c1)
        self._lay.addWidget(self._c2)


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
