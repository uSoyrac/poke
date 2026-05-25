"""GTO Range Widget — pozisyon, stack derinliği ve oyun tipine göre
optimal aralık bilgisini gösteren kompakt panel.

Kullanım:
    widget = GTORangeWidget()
    widget.update_range(position="CO", stack_bb=45.0, game_type="tournament")
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

# ── Renk tokenleri (tema ile uyumlu) ──────────────────────────────
_ACCENT  = "#5ad17a"
_DANGER  = "#e87474"
_WARN    = "#d6c668"
_MUTED   = "#898d80"
_INK     = "#f4f5ee"
_BG2     = "#131613"
_LINE2   = "#33382c"
_INFO    = "#5ad1ce"

# ── GTO Range veri tabanı ─────────────────────────────────────────
# Her pozisyon için: stack aralığına göre (min_bb, range_str, hands_hint, note)
_RANGE_DB: dict[str, list] = {
    # (min_stack_bb, pct, hands, note)
    "UTG": [
        (40,  "13–15%", "AA–22 · AKs–ATs · AKo–AQo · KQs–KJs · JTs · T9s",
               "GTO açılış — sadece güçlü eller"),
        (12,  "11–12%", "44+ · ATs+ · AKo–AQo · KQs",
               "12-40bb: 22-33 ve zayıf AXs çıkar"),
        (0,   "7–8%",   "TT+ · ATs+ · AKo",
               "<12bb push/fold zone — premium only"),
    ],
    "MP": [
        (40,  "17–19%", "UTG + 97s+ · 87s+ · 76s+ · 65s+ · 44-33 · KQo · QJo",
               "Orta pozisyon — suited connectors ekler"),
        (12,  "15–17%", "66+ · AJs+ · AQo+ · KQs · KJs · QJs",
               "Offsuit broadways artar, weak suiteds çıkar"),
        (0,   "10–12%", "88+ · AJs+ · AQo+ · KQs",
               "Push/fold zone"),
    ],
    "CO": [
        (40,  "25–28%", "MP + 54s · 43s · T8s · 98s · AJo · KJo · QJo",
               "CO geniş açılır — BTN'den sonra en iyi pozisyon"),
        (20,  "20–22%", "55+ · ATs+ · AJo+ · KQs · KJs · QJs · JTs",
               "Orta derinlikte sıkılaş"),
        (0,   "14–16%", "77+ · ATs+ · AJo+ · KQs · QJs",
               "Push/fold zone"),
    ],
    "BTN": [
        (40,  "45–50%", "A2s+ · K9s+ · QTs+ · J9s+ · T8s+ · 98s · 87s · 76s · 65s · 22+",
               "BTN: en geniş range — pozisyon çok değerli"),
        (20,  "35–40%", "22+ · A2s+ · KTs+ · QTs+ · J9s+ · T9s · 98s · KJo+ · ATo+",
               "Orta derinlikte biraz daralt"),
        (0,   "22–25%", "55+ · A9s+ · ATo+ · KQs · KJs · QJs · JTs",
               "Push/fold zone"),
    ],
    "SB": [
        (40,  "40–45%", "BTN'e yakın ama OOP — K2s+ · Q6s+ · J7s+ · T8s+ · 22+",
               "OOP dezavantajı var — pozisyon kaybı ciddi"),
        (20,  "28–32%", "33+ · A2s+ · KTs+ · QTs+ · JTs · T9s · KJo+ · AJo+",
               "Orta derinlikte daralt"),
        (0,   "18–22%", "44+ · A7s+ · ATo+ · KQs · QJs",
               "Push/fold zone"),
    ],
    "BB": [
        (40,  "MDF ~52%", "K2s+ · Q4s+ · J7s+ · T8s+ · 97s+ · 86s+ · 75s+ · K9o+ · Q9o+ · J9o+",
               "BB: halihazırda para yatırıldı — geniş defend"),
        (20,  "MDF ~45%", "Suited hands wide · suited broadways · K9o+ · Q9o+ · JTo",
               "Kısa stackte ICM ile daralt"),
        (0,   "MDF ~35%", "22+ · A2s+ · KTs+ · QJs · ATo+ · KQo",
               "Çok kısa stack — sadece yeterli equity"),
    ],
}

# Özel turnuva notları
_TOURNEY_NOTE: dict[str, str] = {
    "UTG":  "Bubble yakınsa sıkılaş. Ante varsa %2-3 genişle.",
    "MP":   "Stack basıncı varsa (20bb altı) push/fold'a geç.",
    "CO":   "Steal frekansı yüksek tut ama ICM baskısına dikkat.",
    "BTN":  "En değerli steal pozisyonu. Short stackleri zorla.",
    "SB":   "OOP. Heads-up steal'de agresif ol, postflop dikkatli.",
    "BB":   "Antes ile defend range genişler. Multiway'de sıkılaş.",
}


def _range_info(pos: str, stack_bb: float) -> tuple[str, str, str, str]:
    """(pct, hands, note, tourney_note) döner."""
    entries = _RANGE_DB.get(pos.upper(), _RANGE_DB.get("CO", []))
    for min_bb, pct, hands, note in entries:
        if stack_bb >= min_bb:
            return pct, hands, note, _TOURNEY_NOTE.get(pos.upper(), "")
    # Fallback
    if entries:
        _, pct, hands, note = entries[-1]
        return pct, hands, note, _TOURNEY_NOTE.get(pos.upper(), "")
    return "—", "—", "", ""


class GTORangeWidget(QFrame):
    """Kompakt GTO range paneli — action deck'in üstüne entegre edilir."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("GTORangePanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame#GTORangePanel {{"
            f"  background: {_BG2};"
            f"  border: 1px solid {_LINE2};"
            f"  border-left: 3px solid {_INFO};"
            f"}}"
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 6, 12, 6)
        root.setSpacing(12)

        # Sol: pozisyon + yüzde
        left = QVBoxLayout()
        left.setSpacing(1)
        self._pos_lbl = QLabel("—")
        self._pos_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; "
            f"letter-spacing:2px; color:{_INFO}; background:transparent; font-weight:700;"
        )
        self._pct_lbl = QLabel("—")
        self._pct_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:13px; "
            f"font-weight:700; color:{_INK}; background:transparent;"
        )
        left.addWidget(self._pos_lbl)
        left.addWidget(self._pct_lbl)
        root.addLayout(left)

        # Orta: eller ve not
        mid = QVBoxLayout()
        mid.setSpacing(1)
        self._hands_lbl = QLabel("—")
        self._hands_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"color:{_MUTED}; background:transparent;"
        )
        self._hands_lbl.setWordWrap(True)
        self._note_lbl = QLabel("")
        self._note_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:9px; "
            f"color:{_WARN}; background:transparent;"
        )
        self._note_lbl.setWordWrap(True)
        mid.addWidget(self._hands_lbl)
        mid.addWidget(self._note_lbl)
        root.addLayout(mid, 1)

        # Sağ: stack bilgisi
        self._stack_lbl = QLabel("")
        self._stack_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._stack_lbl.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"color:{_MUTED}; background:transparent;"
        )
        root.addWidget(self._stack_lbl)

    def update_range(
        self,
        position: str,
        stack_bb: float,
        game_type: str = "cash",   # "cash" veya "tournament"
    ) -> None:
        """Pozisyon ve stack'e göre GTO range bilgisini güncelle."""
        if not position:
            return

        pct, hands, note, tourney_note = _range_info(position, stack_bb)

        self._pos_lbl.setText(f"GTO · {position.upper()}")
        self._pct_lbl.setText(f"Açılış: {pct}")
        self._hands_lbl.setText(hands)

        display_note = tourney_note if game_type == "tournament" and tourney_note else note
        self._note_lbl.setText(display_note)
        self._note_lbl.setVisible(bool(display_note))

        self._stack_lbl.setText(f"{stack_bb:.0f}bb")

        # Renk uyarısı: çok kısa stack
        if stack_bb < 15:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_DANGER}; background:transparent;"
            )
            self._note_lbl.setText("⚠ Push/fold zone — Nash chart kullan")
            self._note_lbl.setVisible(True)
        elif stack_bb < 30:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_WARN}; background:transparent;"
            )
        else:
            self._pct_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:13px; "
                f"font-weight:700; color:{_INK}; background:transparent;"
            )
