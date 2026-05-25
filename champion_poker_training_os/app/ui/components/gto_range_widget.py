"""GTO Range Widget — pozisyon, stack derinliği ve oyun tipine göre
optimal aralık bilgisini gösteren kompakt panel.

Kullanım:
    widget = GTORangeWidget()
    widget.update_range(position="CO", stack_bb=45.0, game_type="tournament")

Ayrıca ``_HandMatrixWidget`` — 13×13 el matrisi, her hücre range üyeliğine
göre renklendirilir (yeşil=premium, cyan=range içi, mor=küçük pair, koyu=dışı).
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

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


# ══════════════════════════════════════════════════════════════════════════
#  Hand Matrix — 13×13 colour-coded range grid
# ══════════════════════════════════════════════════════════════════════════

_MATRIX_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
_MATRIX_RIDX  = {r: i for i, r in enumerate(_MATRIX_RANKS)}

# Cell colour buckets
_MC_PREMIUM = "#5ad17a"   # lime-green  — AA/KK/QQ/JJ + AKs/AKo
_MC_VALUE   = "#5ad1ce"   # cyan        — other in-range hands
_MC_PAIR_SM = "#7c3aed"   # indigo      — pairs 77 and below when in range
_MC_OUT     = "#0f1210"   # near-black  — out of range
_MC_OUT_TXT = "#23271f"   # border-only text
_MC_IN_TXT  = "#0a0c0a"   # ink on coloured cells
_MC_SM_TXT  = "#e0d0ff"   # light text on purple cells


def _matrix_cell_hand(i: int, j: int) -> str:
    """Canonical hand string for matrix cell (row i, col j)."""
    r = _MATRIX_RANKS
    if i == j:
        return r[i] + r[j]              # pair  e.g. "AA"
    elif i < j:
        return r[i] + r[j] + "s"       # suited e.g. "AKs"
    else:
        return r[j] + r[i] + "o"       # offsuit e.g. "AKo"


def _matrix_cell_colors(hand: str, in_range: bool) -> tuple[str, str]:
    """Return (bg, fg) for a matrix cell."""
    if not in_range:
        return _MC_OUT, _MC_OUT_TXT
    # Premium
    if hand in ("AA", "KK", "QQ", "JJ", "AKs", "AKo"):
        return _MC_PREMIUM, _MC_IN_TXT
    # Small pairs (77 and below → index ≥ 6)
    if len(hand) == 2 and hand[0] == hand[1]:
        if _MATRIX_RIDX.get(hand[0], 0) >= 6:
            return _MC_PAIR_SM, _MC_SM_TXT
    return _MC_VALUE, _MC_IN_TXT


def parse_range_str(s: str) -> set[str]:
    """Parse a GTO range string into a set of canonical hand tokens.

    Supported notations:
        AKs, AKo, AA          – single hand
        JJ+, A2s+, K9o+      – plus (hand and better)
        AKs–ATs, AA–22       – dash range
    Non-hand text (Turkish notes, percentages) is silently ignored.
    """
    result: set[str] = set()
    # Normalise dash variants
    s = s.replace("–", "-").replace("–", "-")
    # Split on middle-dot separator; fall back to comma/space
    tokens = re.split(r"[·,]", s)

    # Regex for a valid hand token: 2 rank chars + optional s/o
    _H = r"[AKQJT98765432]{2}[so]?"

    for raw in tokens:
        raw = raw.strip()
        # Dash range first (must precede single-hand match)
        m = re.search(rf"({_H})\s*-\s*({_H})", raw)
        if m:
            _matrix_expand_dash(m.group(1), m.group(2), result)
            continue
        # Plus or single
        m = re.search(_H, raw)
        if m:
            hand = m.group(0)
            if "+" in raw[m.end():m.end() + 1] or raw.endswith("+"):
                _matrix_expand_plus(hand, result)
            else:
                result.add(hand)
    return result


def _matrix_expand_dash(start: str, end: str, out: set) -> None:
    r, ri = _MATRIX_RANKS, _MATRIX_RIDX
    if not start or not end:
        return
    suf = start[2] if len(start) == 3 else ""
    # Pair range e.g. "AA-22"
    if start[0] == start[1] and end[0] == end[1]:
        lo = min(ri.get(start[0], 0), ri.get(end[0], 12))
        hi = max(ri.get(start[0], 0), ri.get(end[0], 12))
        for i in range(lo, hi + 1):
            out.add(r[i] + r[i])
    # Same first card e.g. "AKs-ATs"
    elif start[0] == end[0] and len(start) == 3 and len(end) == 3:
        first_i = ri.get(start[0], 0)
        lo = min(ri.get(start[1], 0), ri.get(end[1], 12))
        hi = max(ri.get(start[1], 0), ri.get(end[1], 12))
        for i in range(lo, hi + 1):
            if i != first_i:
                out.add(start[0] + r[i] + suf)


def _matrix_expand_plus(hand: str, out: set) -> None:
    r, ri = _MATRIX_RANKS, _MATRIX_RIDX
    if len(hand) == 2 and hand[0] == hand[1]:
        # Pair+: "JJ+" → JJ, QQ, KK, AA
        top = ri.get(hand[0], 12)
        for i in range(0, top + 1):
            out.add(r[i] + r[i])
    elif len(hand) == 3:
        first, second, suf = hand[0], hand[1], hand[2]
        fi = ri.get(first, 0)
        si = ri.get(second, 12)
        # "K9s+" → KQs, KJs, KTs, K9s  (from si downward to fi+1)
        for i in range(fi + 1, si + 1):
            out.add(first + r[i] + suf)


class _HandMatrixWidget(QWidget):
    """13×13 colour-coded hand-range matrix.

    Upper triangle = suited, diagonal = pairs, lower triangle = offsuit.
    Call ``set_range(hands_str)`` to colour cells that are in the open range.
    """

    CELL_W = 44   # px per cell
    CELL_H = 34

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._in_range: set[str] = set()
        self._cells: list[list[QLabel]] = []
        self._build()

    def _build(self) -> None:
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)

        for i in range(13):
            row: list[QLabel] = []
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                lbl = QLabel(hand)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setFixedSize(self.CELL_W, self.CELL_H)
                lbl.setStyleSheet(self._style(hand, False))
                grid.addWidget(lbl, i, j)
                row.append(lbl)
            self._cells.append(row)

    def _style(self, hand: str, in_r: bool) -> str:
        bg, fg = _matrix_cell_colors(hand, in_r)
        weight = "700" if in_r else "400"
        return (
            f"background:{bg}; color:{fg}; "
            f"font-family:'JetBrains Mono','Menlo',monospace; "
            f"font-size:8px; font-weight:{weight}; "
            f"border:1px solid #1a1e18;"
        )

    def set_range(self, hands_str: str) -> None:
        """Colour cells based on parsed range string."""
        self._in_range = parse_range_str(hands_str)
        for i in range(13):
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                self._cells[i][j].setStyleSheet(self._style(hand, hand in self._in_range))

    def highlight_hero(self, *hero_hands: str) -> None:
        """Add a gold border to the hero's specific hand cell(s).

        Pass one or two hands (suited + offsuit) to highlight both.
        """
        highlighted = set(hero_hands)
        for i in range(13):
            for j in range(13):
                hand = _matrix_cell_hand(i, j)
                in_r = hand in self._in_range
                bg, fg = _matrix_cell_colors(hand, in_r)
                weight = "700" if in_r else "400"
                border = "2px solid #d6c668" if hand in highlighted else "1px solid #1a1e18"
                self._cells[i][j].setStyleSheet(
                    f"background:{bg}; color:{fg}; "
                    f"font-family:'JetBrains Mono','Menlo',monospace; "
                    f"font-size:8px; font-weight:{weight}; "
                    f"border:{border};"
                )
