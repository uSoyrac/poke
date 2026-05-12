"""RangeMatrix — PeakGTO/GTO Wizard tarzı 13x13 el matrisi.

Her hücre bir starting hand grubu (AA, AKs, AKo, 72o…). Renk frekansa göre
boyanır — kırmızı = raise, mavi = fold, yeşil = call, sarı = mixed.

Frequency map biçimi: {"AA": {"raise": 1.0}, "AKs": {"raise": 0.7, "fold": 0.3}}
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


# 13 ranks high → low
_RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]


def _hand_at(row: int, col: int) -> str:
    """Cell label: AA on diagonal; AKs above (suited); AKo below (offsuit)."""
    r, c = _RANKS[row], _RANKS[col]
    if row == col:        return r + r
    if row < col:         return r + c + "s"
    return c + r + "o"


# Action → primary colour (background fill when 100% that action)
ACTION_COLOURS = {
    "raise":  QColor("#E11D48"),
    "3bet":   QColor("#E11D48"),
    "4bet":   QColor("#7F1D1D"),
    "bet":    QColor("#E11D48"),
    "jam":    QColor("#7F1D1D"),
    "all_in": QColor("#7F1D1D"),
    "call":   QColor("#10B981"),
    "check":  QColor("#10B981"),
    "fold":   QColor("#2563EB"),
}


def _action_colour(action: str) -> QColor:
    return ACTION_COLOURS.get(action.lower(), QColor("#374151"))


class RangeMatrix(QWidget):
    """13x13 grid where each cell is a starting hand, painted per strategy."""

    hand_clicked = Signal(str)  # emits "AKs" / "QQ" / "72o"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._freq_map: dict[str, dict[str, float]] = {}
        self._highlighted: Optional[str] = None
        # mode: "strategy" (default), "strategy_ev", "ev", "equity", "runout", "aggregate"
        self._mode: str = "strategy"
        # Per-hand EV / equity values (filled by set_strategy from chart aggregate)
        self._ev_map: dict[str, float] = {}
        self._equity_map: dict[str, float] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(420, 420)
        self.setMouseTracking(True)

    # ── public API ─────────────────────────────────────────────────────
    def set_strategy(self, freq_map: dict[str, dict[str, float]]) -> None:
        """{"AKs": {"raise": 0.7, "fold": 0.3}, …}"""
        self._freq_map = freq_map or {}
        # Derive EV and equity proxies so EV/Equity tabs have data to paint:
        # EV ≈ aggressive frequency × 2 - 1 (range −1 fold-only … +1 raise-only)
        # Equity ≈ raise/call frequency (proxy for "how much this hand wants to play")
        self._ev_map = {}
        self._equity_map = {}
        for hand, strat in (freq_map or {}).items():
            aggr = sum(v for a, v in strat.items() if any(k in a.lower() for k in ("raise","3bet","4bet","bet","jam","all")))
            passive = sum(v for a, v in strat.items() if any(k in a.lower() for k in ("call","check")))
            fold = sum(v for a, v in strat.items() if "fold" in a.lower())
            total = max(aggr + passive + fold, 0.001)
            self._ev_map[hand]     = round(2.0 * aggr / total - 0.4 * fold / total, 3)
            self._equity_map[hand] = round((aggr + 0.5 * passive) / total, 3)
        self.update()

    def set_mode(self, mode: str) -> None:
        """Switch matrix render mode.
        Valid: 'strategy' | 'strategy_ev' | 'ev' | 'equity' | 'runout' | 'aggregate'
        """
        self._mode = mode if mode in ("strategy", "strategy_ev", "ev", "equity",
                                       "runout", "aggregate") else "strategy"
        self.update()

    @property
    def mode(self) -> str:
        return self._mode

    def highlight_hand(self, hand: Optional[str]) -> None:
        self._highlighted = hand
        self.update()

    def clear(self) -> None:
        self._freq_map = {}
        self._ev_map = {}
        self._equity_map = {}
        self._highlighted = None
        self.update()

    # ── interaction ────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        h = self._hand_at_point(event.position().x(), event.position().y())
        if h:
            self.hand_clicked.emit(h)
            self._highlighted = h
            self.update()

    def _hand_at_point(self, x: float, y: float) -> Optional[str]:
        cell_w, cell_h, ox, oy = self._geometry()
        if cell_w < 1 or cell_h < 1:
            return None
        col = int((x - ox) / cell_w)
        row = int((y - oy) / cell_h)
        if 0 <= row < 13 and 0 <= col < 13:
            return _hand_at(row, col)
        return None

    def _geometry(self) -> tuple[float, float, float, float]:
        side = min(self.width(), self.height())
        cell = side / 13.0
        ox = (self.width()  - cell * 13) / 2
        oy = (self.height() - cell * 13) / 2
        return cell, cell, ox, oy

    # ── paint ──────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cell_w, cell_h, ox, oy = self._geometry()
        font = QFont()
        font.setBold(True)
        size = max(8, int(cell_w * 0.32))
        font.setPixelSize(size)
        painter.setFont(font)

        for row in range(13):
            for col in range(13):
                x = ox + col * cell_w
                y = oy + row * cell_h
                hand = _hand_at(row, col)
                actions = self._freq_map.get(hand, {})

                if self._mode in ("ev", "strategy_ev"):
                    # EV heatmap: green = positive EV, red = negative
                    val = self._ev_map.get(hand, 0.0)  # range roughly [-0.4, 2]
                    intensity = max(-1.0, min(1.0, val / 1.5))
                    if intensity >= 0:
                        # green gradient
                        g = int(60 + 180 * intensity)
                        col_q = QColor(20, g, 60)
                    else:
                        b = int(60 + 180 * (-intensity))
                        col_q = QColor(b, 30, 50)
                    painter.fillRect(int(x), int(y), int(cell_w + 1), int(cell_h + 1), col_q)

                elif self._mode == "equity":
                    # Equity heatmap: yellow→green gradient
                    eq = self._equity_map.get(hand, 0.0)
                    g = int(60 + 180 * eq)
                    r = int(180 * (1.0 - eq))
                    col_q = QColor(max(30, r), g, 60)
                    painter.fillRect(int(x), int(y), int(cell_w + 1), int(cell_h + 1), col_q)

                elif actions:
                    # Default Strategy mode — paint segments per action
                    total = sum(actions.values()) or 1.0
                    seg_x = x
                    for action, freq in actions.items():
                        seg_w = cell_w * (freq / total)
                        painter.fillRect(int(seg_x), int(y), int(seg_w + 1), int(cell_h + 1),
                                          _action_colour(action))
                        seg_x += seg_w
                else:
                    # Empty cell — dark grey
                    painter.fillRect(int(x), int(y), int(cell_w + 1), int(cell_h + 1),
                                      QColor("#1F2937"))

                # Border
                if hand == self._highlighted:
                    painter.setPen(QPen(QColor("#22D3EE"), 2))
                else:
                    painter.setPen(QPen(QColor("#0B0F14"), 1))
                painter.drawRect(int(x), int(y), int(cell_w), int(cell_h))

                # Hand label
                painter.setPen(QColor("#FFFFFF"))
                if self._mode == "strategy_ev":
                    # Smaller hand label on top, EV value below
                    painter.drawText(
                        int(x), int(y) + 2, int(cell_w), int(cell_h * 0.5),
                        Qt.AlignCenter, hand,
                    )
                    ev = self._ev_map.get(hand, 0.0)
                    sub_font = QFont(); sub_font.setBold(False)
                    sub_font.setPixelSize(max(7, int(cell_w * 0.22)))
                    painter.setFont(sub_font)
                    painter.drawText(
                        int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.5 - 2),
                        Qt.AlignCenter, f"{ev:+.2f}",
                    )
                    painter.setFont(font)  # restore
                elif self._mode == "equity":
                    painter.drawText(
                        int(x), int(y) + 2, int(cell_w), int(cell_h * 0.5),
                        Qt.AlignCenter, hand,
                    )
                    eq = self._equity_map.get(hand, 0.0)
                    sub_font = QFont(); sub_font.setBold(False)
                    sub_font.setPixelSize(max(7, int(cell_w * 0.22)))
                    painter.setFont(sub_font)
                    painter.drawText(
                        int(x), int(y + cell_h * 0.5), int(cell_w), int(cell_h * 0.5 - 2),
                        Qt.AlignCenter, f"{eq*100:.0f}%",
                    )
                    painter.setFont(font)
                elif self._mode == "ev":
                    # Pure EV: show value only
                    ev = self._ev_map.get(hand, 0.0)
                    painter.drawText(
                        int(x), int(y), int(cell_w), int(cell_h),
                        Qt.AlignCenter, f"{ev:+.2f}",
                    )
                else:
                    painter.drawText(
                        int(x), int(y), int(cell_w), int(cell_h),
                        Qt.AlignCenter, hand,
                    )

        painter.end()


# ──────────────────────────────────────────────────────────────────────────
# Demo preflop ranges  (RFI / vs RFI / 3-bet defense …)
# Frequency maps for common spots. Real solver CSV can override these.
# ──────────────────────────────────────────────────────────────────────────

def demo_range(spot_key: str) -> dict[str, dict[str, float]]:
    """Return a frequency map for known preflop spots."""
    return _DEMO_RANGES.get(spot_key, _RFI_BTN_40)


def _gen(strong: list[str], mixed: dict[str, float], weak_action: str = "fold") -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for h in strong:
        result[h] = {"raise": 1.0}
    for h, freq in mixed.items():
        result[h] = {"raise": freq, weak_action: 1.0 - freq}
    # Everything else → 100% fold (or weak action)
    for r1 in _RANKS:
        for r2 in _RANKS:
            if r1 == r2:
                h = r1 + r2
            elif _RANKS.index(r1) < _RANKS.index(r2):
                h = r1 + r2 + "s"
            else:
                h = r2 + r1 + "o"
            if h not in result:
                result[h] = {weak_action: 1.0}
    return result


# BTN RFI 40bb (very wide opener)
_RFI_BTN_40 = _gen(
    strong=[
        # Pairs
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        # Suited broadway
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
        "QJs", "QTs", "Q9s", "Q8s",
        "JTs", "J9s", "J8s",
        "T9s", "T8s",
        "98s", "97s",
        "87s", "86s",
        "76s", "75s",
        "65s",
        # Offsuit broadway
        "AKo", "AQo", "AJo", "ATo", "A9o",
        "KQo", "KJo", "KTo",
        "QJo", "QTo",
        "JTo",
    ],
    mixed={
        "A8o": 0.7, "A7o": 0.4, "A6o": 0.3, "A5o": 0.2,
        "K9o": 0.6, "K8o": 0.3,
        "Q9o": 0.4, "Q8o": 0.2,
        "J9o": 0.5, "J8o": 0.2,
        "T9o": 0.5, "T8o": 0.3,
        "98o": 0.4, "87o": 0.3,
        "K4s": 0.7, "K3s": 0.5, "K2s": 0.4,
        "Q7s": 0.5, "Q6s": 0.4, "Q5s": 0.3, "Q4s": 0.2,
        "J7s": 0.5, "T7s": 0.4, "96s": 0.4, "85s": 0.3, "74s": 0.3, "64s": 0.3, "54s": 0.5, "53s": 0.4, "43s": 0.3,
    },
)

# UTG RFI 40bb (tight opener)
_RFI_UTG_40 = _gen(
    strong=[
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        "AKs", "AQs", "AJs", "ATs", "A5s", "A4s",
        "KQs", "KJs", "KTs",
        "QJs", "QTs",
        "JTs",
        "T9s", "98s", "87s",
        "AKo", "AQo",
    ],
    mixed={
        "66": 0.8, "55": 0.6,
        "A9s": 0.7, "A8s": 0.5, "A7s": 0.4, "A3s": 0.3,
        "K9s": 0.5,
        "Q9s": 0.4, "J9s": 0.4,
        "T8s": 0.3, "97s": 0.3, "76s": 0.3, "65s": 0.3,
        "AJo": 0.7, "KQo": 0.6,
    },
)

# LJ RFI 40bb (medium-tight)
_RFI_LJ_40 = _gen(
    strong=[
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A5s", "A4s",
        "KQs", "KJs", "KTs", "K9s",
        "QJs", "QTs", "Q9s",
        "JTs", "J9s",
        "T9s", "98s", "87s", "76s",
        "AKo", "AQo", "AJo", "KQo",
    ],
    mixed={
        "55": 0.7, "44": 0.4, "33": 0.2, "22": 0.2,
        "A8s": 0.7, "A7s": 0.5, "A6s": 0.4, "A3s": 0.4, "A2s": 0.4,
        "K8s": 0.4, "Q8s": 0.3, "J8s": 0.3, "T8s": 0.3,
        "97s": 0.3, "86s": 0.2, "65s": 0.4, "54s": 0.3,
        "ATo": 0.6, "KJo": 0.5,
    },
)

# BB defense vs BTN RFI (call/3bet/fold)
def _bb_vs_btn_40() -> dict[str, dict[str, float]]:
    res: dict[str, dict[str, float]] = {}
    # 3-bet for value
    for h in ["AA", "KK", "QQ", "JJ", "TT", "AKs", "AKo", "AQs"]:
        res[h] = {"3bet": 1.0}
    # 3-bet bluffs (mixed)
    for h in ["A5s", "A4s", "A3s", "K5s", "Q5s", "76s", "65s", "54s"]:
        res[h] = {"3bet": 0.4, "call": 0.6}
    # Call wide
    calls = [
        "99", "88", "77", "66", "55", "44", "33", "22",
        "AQo", "AJo", "ATo", "A9o", "A8o", "A7o",
        "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K4s", "K3s",
        "KQo", "KJo", "KTo", "K9o",
        "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s",
        "QJo", "QTo", "Q9o",
        "JTs", "J9s", "J8s", "J7s",
        "JTo", "J9o",
        "T9s", "T8s", "T7s", "T9o",
        "98s", "97s", "98o",
        "87s", "86s",
        "75s", "74s",
        "64s", "53s", "43s",
    ]
    for h in calls:
        if h not in res:
            res[h] = {"call": 1.0}
    # Fold everything else
    for r1 in _RANKS:
        for r2 in _RANKS:
            if r1 == r2:        h = r1 + r2
            elif _RANKS.index(r1) < _RANKS.index(r2):  h = r1 + r2 + "s"
            else:               h = r2 + r1 + "o"
            if h not in res:
                res[h] = {"fold": 1.0}
    return res


_DEMO_RANGES = {
    "BTN-RFI-40":    _RFI_BTN_40,
    "BTN-RFI-25":    _RFI_BTN_40,  # similar shape
    "UTG-RFI-40":    _RFI_UTG_40,
    "LJ-RFI-40":     _RFI_LJ_40,
    "LJ-RFI-25":     _RFI_LJ_40,
    "BB-vs-BTN-40":  _bb_vs_btn_40(),
    "BB-vs-BTN-25":  _bb_vs_btn_40(),
    "BB-vs-LJ-40":   _bb_vs_btn_40(),  # similar
}


def spot_key_for(position: str, action_context: str, stack_bb: int) -> str:
    """Map a spot dict to a demo range key."""
    p = position.upper() if position else "BTN"
    stack_bucket = 25 if stack_bb <= 30 else 40
    ctx = (action_context or "").lower()
    if "vs btn" in ctx or "vs btn rfi" in ctx:
        return f"BB-vs-BTN-{stack_bucket}"
    if "vs lj" in ctx:
        return f"BB-vs-LJ-{stack_bucket}"
    return f"{p}-RFI-{stack_bucket}"
