"""GTOTrainerScreen — PeakGTO / GTO Wizard tarzı tam ekran trainer.

İki mod:
  • Range mode:  13x13 matriks + strategy bars + hand combo cards
  • Table mode:  oval poker masa + GTO action buttons + feedback

Üst pozisyon şeridi her zaman görünür. Trainer Scenario modal'ı ile filtrele.
"""
from __future__ import annotations

import random
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills, get_spot_categories
from app.solver.mock_solver import compare_action, solve_spot
from app.solver.preflop_charts import chart_for_spot, hand_169_from_cards, strategy_for_hand
from app.ui.components.action_chip import parse_action_string
from app.ui.components.live_poker_table import LivePokerTable
from app.ui.components.range_matrix import RangeMatrix

# colour constants
_C_BG     = "#0A0E14"
_C_CARD   = "#0F141C"
_C_PANEL  = "#131A24"
_C_BORDER = "#1E2733"
_C_MUTED  = "#6B7280"
_C_TEXT   = "#E5E7EB"
_C_CYAN   = "#22D3EE"
_C_GREEN  = "#10B981"
_C_RED    = "#E11D48"
_C_BLUE   = "#2563EB"
_C_AMBER  = "#F59E0B"


# ── pretty action label ───────────────────────────────────────────────────

def _action_display(action: str, spot: dict) -> str:
    a = action.lower()
    pot = float(spot.get("pot_bb", 10))
    stk = float(spot.get("stack_bb", 40))
    if a == "fold":   return "FOLD"
    if a == "check":  return "CHECK"
    if a == "call":   return "CALL"
    if a in ("jam", "all_in", "all-in"): return f"ALLIN {stk:.0f}"
    if "small" in a:  return f"BET {pot*0.33:.1f}"
    if "medium" in a: return f"BET {pot*0.66:.1f}"
    if "large" in a:  return f"BET {pot*1.10:.1f}"
    if a in ("raise", "3bet", "4bet", "bet"):
        size = pot * 2.4 if a == "raise" else pot * 3 if a == "3bet" else pot * 4
        return f"RAISE {size:.1f}"
    return action.upper()


def _action_colour_qss(action: str) -> tuple[str, str, str]:
    a = action.lower()
    if "fold" in a:                                                 return ("#1B2D4A", "#3B82F6", "#93C5FD")
    if a in ("check", "call"):                                      return ("#0E2A1E", "#10B981", "#6EE7B7")
    if "jam" in a or "all" in a:                                    return ("#1A0E0E", "#7F1D1D", "#FCA5A5")
    if any(t in a for t in ("raise", "3bet", "4bet", "bet")):       return ("#2A1B1B", "#E11D48", "#FCA5A5")
    return (_C_PANEL, _C_BORDER, _C_TEXT)


# ── small reusable widgets ────────────────────────────────────────────────

class _PositionChip(QFrame):
    """Top strip chip: position name + stack + ALL strategy actions stacked.

    Like PeakGTO screenshot 1 where each chip shows e.g.
       SB
       39.5
       [Fold]
       [Call]
       [Raise 3.2]
    """
    def __init__(self, position: str, stack: float, actions: list[tuple[str, str]], is_hero: bool = False):
        """actions = [(label, kind)]; kind ∈ {fold, call, raise}"""
        super().__init__()
        self._is_hero = is_hero
        self.setFixedWidth(110)
        self.setFixedHeight(112)
        border = _C_GREEN if is_hero else _C_BORDER
        self.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:2px solid {border};border-radius:8px;}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(3)

        head = QHBoxLayout()
        head.setSpacing(4)
        name = QLabel(position)
        name.setStyleSheet(f"color:{_C_TEXT};font-weight:700;font-size:12px;")
        stk = QLabel(f"{stack:g}")
        stk.setStyleSheet(f"color:{_C_MUTED};font-size:11px;")
        stk.setAlignment(Qt.AlignRight)
        head.addWidget(name)
        head.addStretch(1)
        head.addWidget(stk)
        v.addLayout(head)

        for label, kind in actions[:3]:
            pill = QLabel(label)
            pill.setAlignment(Qt.AlignCenter)
            pill.setFixedHeight(20)
            k = kind.lower()
            if "fold" in k:    bg, fg = "#1B2D4A", "#93C5FD"
            elif "call" in k or "check" in k: bg, fg = "#0E2A1E", "#6EE7B7"
            else:              bg, fg = "#2A1B1B", "#FCA5A5"
            pill.setStyleSheet(
                f"QLabel{{background:{bg};color:{fg};border-radius:4px;"
                "font-size:10px;font-weight:600;padding:2px 6px;}}"
            )
            v.addWidget(pill)
        v.addStretch(1)


class _StrategyBar(QFrame):
    """Horizontal frequency bar with action name + percentage."""

    def __init__(self, action: str, frequency: float):
        super().__init__()
        self.setFixedHeight(48)
        bg, border, fg = _action_colour_qss(action)
        pct = frequency * 100
        # Solid coloured bar with text overlay
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {border};border-radius:6px;}}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        name = QLabel(action.upper())
        name.setStyleSheet(f"color:{fg};font-weight:800;font-size:13px;")
        pct_lbl = QLabel(f"{pct:.2f}%")
        pct_lbl.setStyleSheet(f"color:{fg};font-weight:800;font-size:14px;")
        pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(name)
        layout.addStretch(1)
        layout.addWidget(pct_lbl)


class _HandComboCard(QFrame):
    """Specific 2-card combo card showing the strategy for THIS combo."""

    def __init__(self, combo: str, strategy: dict[str, float]):
        super().__init__()
        self.setFixedSize(130, 86)
        self.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:7px;}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(3)

        # Card visual row
        cards = QHBoxLayout()
        cards.setSpacing(3)
        for card in self._parse_combo(combo):
            c = QLabel(card["text"])
            c.setAlignment(Qt.AlignCenter)
            c.setFixedSize(28, 36)
            c.setStyleSheet(
                f"QLabel{{background:{card['bg']};color:white;border-radius:3px;"
                "font-size:14px;font-weight:800;}}"
            )
            cards.addWidget(c)
        cards.addStretch(1)
        v.addLayout(cards)

        # Strategy lines
        for action, freq in sorted(strategy.items(), key=lambda x: -x[1]):
            if freq < 0.01:
                continue
            _, _, fg = _action_colour_qss(action)
            line = QHBoxLayout()
            l1 = QLabel(action.title())
            l1.setStyleSheet(f"color:{fg};font-size:10px;font-weight:600;")
            l2 = QLabel(f"{freq*100:.0f}%")
            l2.setStyleSheet(f"color:{fg};font-size:10px;font-weight:700;")
            l2.setAlignment(Qt.AlignRight)
            line.addWidget(l1)
            line.addStretch(1)
            line.addWidget(l2)
            v.addLayout(line)

    @staticmethod
    def _parse_combo(combo: str) -> list[dict]:
        """e.g. 'A♠A♥' → two cards. Falls back to text."""
        suit_colors = {"♠": "#1F2937", "♥": "#B91C1C", "♦": "#1E40AF", "♣": "#065F46"}
        cards: list[dict] = []
        i = 0
        while i < len(combo):
            if i + 1 < len(combo) and combo[i+1] in suit_colors:
                cards.append({"text": combo[i:i+2], "bg": suit_colors[combo[i+1]]})
                i += 2
            else:
                i += 1
        if not cards:
            cards.append({"text": combo[:4], "bg": _C_PANEL})
        return cards


# ── trainer scenario modal (filter dialog) ────────────────────────────────

class TrainerScenarioDialog(QDialog):
    """PeakGTO-style filter modal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trainer Scenario")
        self.setMinimumSize(720, 560)
        self.setStyleSheet(f"QDialog{{background:{_C_BG};}}")
        self._result: dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        # Settings card
        settings_card = QFrame()
        settings_card.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
        )
        sl = QVBoxLayout(settings_card)
        sl.setContentsMargins(20, 16, 20, 16)
        sl.setSpacing(12)

        # Library / Format / Game Mode / Ante row
        row1 = QGridLayout()
        row1.setHorizontalSpacing(20)
        self._library = _make_toggle_group(["Tournament", "Cash Games"], active="Tournament")
        self._format  = _make_toggle_group(["8Max", "HU", "ICM"], active="8Max", disabled=["ICM"])
        self._mode    = _make_toggle_group(["Preflop", "Full Hand"], active="Full Hand")
        self._ante    = _make_toggle_group(["12.5%"], active="12.5%")
        row1.addWidget(_section_label("Library"),    0, 0); row1.addLayout(self._library["layout"], 1, 0)
        row1.addWidget(_section_label("Format"),     0, 1); row1.addLayout(self._format["layout"],  1, 1)
        row1.addWidget(_section_label("Game Mode"),  0, 2); row1.addLayout(self._mode["layout"],    1, 2)
        row1.addWidget(_section_label("Ante"),       0, 3); row1.addLayout(self._ante["layout"],    1, 3)
        sl.addLayout(row1)

        # Stack size + Difficulty
        sl.addWidget(_section_label("Stack Size"))
        self._stack = _make_toggle_group(
            ["Any","10bb","12bb","15bb","20bb","25bb","30bb","40bb","50bb","60bb","80bb"],
            active="40bb",
        )
        sl.addLayout(self._stack["layout"])

        diff_row = QHBoxLayout()
        diff_row.addWidget(_section_label("Difficulty"))
        diff_row.addSpacing(12)
        self._difficulty = _make_toggle_group(["Easy", "Hard"], active="Easy")
        diff_row.addLayout(self._difficulty["layout"])
        diff_row.addStretch(1)
        sl.addLayout(diff_row)
        root.addWidget(settings_card)

        # Starting spot + Hero/Villain seat
        body_row = QHBoxLayout()

        spot_card = QFrame()
        spot_card.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
        )
        sc = QVBoxLayout(spot_card)
        sc.setContentsMargins(20, 14, 20, 14)
        sc.setSpacing(10)
        sc.addWidget(_section_label("Starting Spot"))
        self._spot = _make_toggle_group(["Preflop", "Flop", "Custom"], active="Preflop")
        sc.addLayout(self._spot["layout"])
        sc.addWidget(_section_label("Preflop Action"))
        self._pre = _make_toggle_grid(
            [["Any","RFI","vs RFI"], ["vs 3bet","vs 4bet","vs Limp"], ["vs Squeeze","vs ISO","vs Limp-Raise"]],
            active="Any", disabled=["vs Squeeze"],
        )
        sc.addLayout(self._pre["layout"])
        body_row.addWidget(spot_card, 1)

        seat_card = QFrame()
        seat_card.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:8px;}}"
        )
        seat_v = QVBoxLayout(seat_card)
        seat_v.setContentsMargins(20, 14, 20, 14)
        seat_v.setSpacing(10)
        seat_v.addWidget(_section_label("Hero Seat"))
        self._hero_seat = _make_toggle_group(
            ["Any","UTG","UTG+1","LJ","HJ","CO","BTN","SB","BB"], active="Any",
        )
        seat_v.addLayout(self._hero_seat["layout"])
        seat_v.addWidget(_section_label("Villain Seat"))
        self._vill_seat = _make_toggle_group(
            ["Any","UTG","UTG+1","LJ","HJ","CO","BTN","SB","BB"], active="Any",
        )
        seat_v.addLayout(self._vill_seat["layout"])
        body_row.addWidget(seat_card, 1)
        root.addLayout(body_row)

        # Footer
        footer = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(38)
        close_btn.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            "border-radius:8px;padding:4px 22px;font-weight:600;}}"
        )
        close_btn.clicked.connect(self.reject)
        save_btn = QPushButton("📌 Save Preset")
        save_btn.setFixedHeight(38)
        save_btn.setStyleSheet(close_btn.styleSheet())
        start_btn = QPushButton("Start Training")
        start_btn.setFixedHeight(38)
        start_btn.setStyleSheet(
            f"QPushButton{{background:{_C_GREEN};color:#000;border-radius:8px;"
            "padding:4px 22px;font-weight:800;font-size:13px;border:none;}}"
        )
        start_btn.clicked.connect(self._accept_with_result)
        footer.addWidget(close_btn)
        footer.addStretch(1)
        footer.addWidget(save_btn)
        footer.addWidget(start_btn)
        root.addLayout(footer)

    def _accept_with_result(self) -> None:
        self._result = {
            "library":    self._library["selected"](),
            "format":     self._format["selected"](),
            "mode":       self._mode["selected"](),
            "ante":       self._ante["selected"](),
            "stack":      self._stack["selected"](),
            "difficulty": self._difficulty["selected"](),
            "spot":       self._spot["selected"](),
            "preflop":    self._pre["selected"](),
            "hero_seat":  self._hero_seat["selected"](),
            "vill_seat":  self._vill_seat["selected"](),
        }
        self.accept()

    def result_data(self) -> dict:
        return self._result


# Helper for toggle button groups
def _section_label(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(f"color:{_C_MUTED};font-size:12px;font-weight:600;margin-bottom:4px;")
    return l


def _make_toggle_group(options: list[str], active: str, disabled: Optional[list[str]] = None) -> dict:
    disabled = disabled or []
    layout = QHBoxLayout()
    layout.setSpacing(8)
    btns: dict[str, QPushButton] = {}
    selected = [active]
    def style(is_active: bool, is_disabled: bool) -> str:
        if is_disabled:
            return (
                f"QPushButton{{background:{_C_PANEL};color:#374151;border:1px solid {_C_BORDER};"
                "border-radius:6px;padding:6px 14px;font-size:12px;}}"
            )
        if is_active:
            return (
                f"QPushButton{{background:{_C_PANEL};color:{_C_GREEN};border:1px solid {_C_GREEN};"
                "border-radius:6px;padding:6px 14px;font-size:12px;font-weight:700;}}"
            )
        return (
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            "border-radius:6px;padding:6px 14px;font-size:12px;}}"
            f"QPushButton:hover{{border-color:{_C_GREEN};}}"
        )

    def make_handler(opt: str):
        def handler():
            if opt in disabled:
                return
            selected[0] = opt
            for k, b in btns.items():
                b.setStyleSheet(style(k == opt, k in disabled))
        return handler

    for opt in options:
        b = QPushButton(opt)
        b.setFixedHeight(32)
        b.setStyleSheet(style(opt == active, opt in disabled))
        b.clicked.connect(make_handler(opt))
        btns[opt] = b
        layout.addWidget(b)
    layout.addStretch(1)
    return {"layout": layout, "buttons": btns, "selected": lambda: selected[0]}


def _make_toggle_grid(rows: list[list[str]], active: str, disabled: Optional[list[str]] = None) -> dict:
    disabled = disabled or []
    outer = QVBoxLayout()
    outer.setSpacing(6)
    selected = [active]
    btns: dict[str, QPushButton] = {}

    def style(is_active: bool, is_disabled: bool) -> str:
        if is_disabled:
            return (
                f"QPushButton{{background:{_C_PANEL};color:#374151;border:1px solid {_C_BORDER};"
                "border-radius:6px;padding:6px 14px;font-size:12px;}}"
            )
        if is_active:
            return (
                f"QPushButton{{background:{_C_PANEL};color:{_C_GREEN};border:1px solid {_C_GREEN};"
                "border-radius:6px;padding:6px 14px;font-size:12px;font-weight:700;}}"
            )
        return (
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            "border-radius:6px;padding:6px 14px;font-size:12px;}}"
        )

    def make_handler(opt: str):
        def handler():
            if opt in disabled:
                return
            selected[0] = opt
            for k, b in btns.items():
                b.setStyleSheet(style(k == opt, k in disabled))
        return handler

    for row in rows:
        rl = QHBoxLayout()
        rl.setSpacing(8)
        for opt in row:
            b = QPushButton(opt)
            b.setFixedHeight(32)
            b.setStyleSheet(style(opt == active, opt in disabled))
            b.clicked.connect(make_handler(opt))
            btns[opt] = b
            rl.addWidget(b)
        rl.addStretch(1)
        outer.addLayout(rl)
    return {"layout": outer, "buttons": btns, "selected": lambda: selected[0]}


# ──────────────────────────────────────────────────────────────────────────
# Main screen
# ──────────────────────────────────────────────────────────────────────────

class GTOTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = generate_spot_drills(120)
        self.index = random.randint(0, max(0, len(self.drills) - 1))
        self._mode = "range"  # "range" | "table"
        self._answered = False
        self._action_btns: list[tuple[QPushButton, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top scenario bar ───────────────────────────────────────────
        scenario_bar = QFrame()
        scenario_bar.setFixedHeight(48)
        scenario_bar.setStyleSheet(f"background:{_C_PANEL};border-bottom:1px solid {_C_BORDER};")
        sb = QHBoxLayout(scenario_bar)
        sb.setContentsMargins(16, 6, 16, 6)
        sb.setSpacing(10)

        title = QLabel("🎯  GTO Trainer")
        title.setStyleSheet(f"color:{_C_TEXT};font-weight:700;font-size:14px;")
        sb.addWidget(title)
        sb.addSpacing(20)

        self._scenario_lbl = QLabel("MTT  ·  8Max  ·  40bb  ·  12.5% ante")
        self._scenario_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        sb.addWidget(self._scenario_lbl)
        sb.addStretch(1)

        self._mode_btn = QPushButton("▶ Play Spot (Table View)")
        self._mode_btn.setFixedHeight(32)
        self._mode_btn.setStyleSheet(_pill_style(active=False))
        self._mode_btn.clicked.connect(self._toggle_mode)
        sb.addWidget(self._mode_btn)

        scenario_btn = QPushButton("⚙ Scenario")
        scenario_btn.setFixedHeight(32)
        scenario_btn.setStyleSheet(_pill_style(active=False))
        scenario_btn.clicked.connect(self._open_scenario)
        sb.addWidget(scenario_btn)

        next_btn = QPushButton("Next ▶")
        next_btn.setFixedHeight(32)
        next_btn.setStyleSheet(_pill_style(active=True))
        next_btn.clicked.connect(self._next_spot)
        sb.addWidget(next_btn)
        root.addWidget(scenario_bar)

        # ── Position strip ─────────────────────────────────────────────
        pos_strip = QFrame()
        pos_strip.setFixedHeight(132)
        pos_strip.setStyleSheet(f"background:{_C_CARD};border-bottom:1px solid {_C_BORDER};")
        self._pos_row = QHBoxLayout(pos_strip)
        self._pos_row.setContentsMargins(12, 10, 12, 10)
        self._pos_row.setSpacing(8)
        root.addWidget(pos_strip)

        # ── Stacked body: range view OR table view ─────────────────────
        self._stack = QStackedWidget()
        self._range_view  = self._build_range_view()
        self._table_view  = self._build_table_view()
        self._stack.addWidget(self._range_view)
        self._stack.addWidget(self._table_view)
        root.addWidget(self._stack, 1)

        # Load first spot
        self.load_spot()

    # ── range view ─────────────────────────────────────────────────────
    def _build_range_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_C_BG};")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # LEFT panel — spot context + strategy bars + hand combos
        left = QFrame()
        left.setFixedWidth(280)
        left.setStyleSheet(f"background:{_C_CARD};border-right:1px solid {_C_BORDER};")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(14, 14, 14, 14)
        lv.setSpacing(10)

        self._spot_meta_label = QLabel()
        self._spot_meta_label.setStyleSheet(f"color:{_C_TEXT};font-weight:700;font-size:14px;")
        self._spot_meta_label.setWordWrap(True)
        lv.addWidget(self._spot_meta_label)

        self._pot_label = QLabel("Pot 2.5bb")
        self._pot_label.setStyleSheet(f"color:{_C_CYAN};font-size:13px;font-weight:700;")
        lv.addWidget(self._pot_label)

        sep1 = QFrame()
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background:{_C_BORDER};")
        lv.addWidget(sep1)

        lv.addWidget(_section_label("Strategy"))
        self._strategy_box = QVBoxLayout()
        self._strategy_box.setSpacing(6)
        lv.addLayout(self._strategy_box)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{_C_BORDER};")
        lv.addWidget(sep2)

        lv.addWidget(_section_label("Hand Combos"))
        combos_scroll = QScrollArea()
        combos_scroll.setWidgetResizable(True)
        combos_scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:transparent;}}"
            "QScrollBar:vertical{width:5px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:2px;}"
        )
        combos_w = QWidget()
        self._combos_grid = QGridLayout(combos_w)
        self._combos_grid.setContentsMargins(0, 0, 0, 0)
        self._combos_grid.setSpacing(6)
        combos_scroll.setWidget(combos_w)
        lv.addWidget(combos_scroll, 1)

        h.addWidget(left)

        # RIGHT — matrix + tabs
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(14, 14, 14, 14)
        rv.setSpacing(8)

        # Tabs row
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(4)
        for tab in ["Strategy", "Strategy + EV", "EV", "Equity", "Runout Comparison", "Aggregate Reports"]:
            tb = QPushButton(tab)
            tb.setFixedHeight(32)
            tb.setStyleSheet(_pill_style(active=(tab == "Strategy")))
            tabs_row.addWidget(tb)
        tabs_row.addStretch(1)
        rv.addLayout(tabs_row)

        # Range matrix
        self._matrix = RangeMatrix()
        self._matrix.hand_clicked.connect(self._on_hand_clicked)
        rv.addWidget(self._matrix, 1)
        h.addWidget(right, 1)
        return w

    # ── table view ─────────────────────────────────────────────────────
    def _build_table_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{_C_BG};")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        self._live_table = LivePokerTable()
        self._live_table.setMinimumHeight(360)
        v.addWidget(self._live_table, 1)

        ctx_bar = QFrame()
        ctx_bar.setFixedHeight(40)
        ctx_bar.setStyleSheet(f"background:#0A0F16;border-top:1px solid {_C_BORDER};")
        ctx_l = QHBoxLayout(ctx_bar)
        ctx_l.setContentsMargins(16, 4, 16, 4)
        self._tbl_ctx_label = QLabel()
        self._tbl_ctx_label.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        ctx_l.addWidget(self._tbl_ctx_label)
        ctx_l.addStretch(1)
        v.addWidget(ctx_bar)

        # Action buttons
        act_frame = QFrame()
        act_frame.setFixedHeight(90)
        act_frame.setStyleSheet(f"background:{_C_BG};border-top:2px solid {_C_BORDER};")
        self._tbl_act_layout = QHBoxLayout(act_frame)
        self._tbl_act_layout.setContentsMargins(16, 14, 16, 14)
        self._tbl_act_layout.setSpacing(10)
        v.addWidget(act_frame)

        # Feedback
        self._tbl_fb = QFrame()
        self._tbl_fb.setStyleSheet(f"QFrame{{background:{_C_CARD};border-top:1px solid {_C_BORDER};}}")
        self._tbl_fb_layout = QVBoxLayout(self._tbl_fb)
        self._tbl_fb_layout.setContentsMargins(16, 8, 16, 8)
        self._tbl_fb.setMaximumHeight(0)
        v.addWidget(self._tbl_fb)
        return w

    # ── mode toggle ────────────────────────────────────────────────────
    def _toggle_mode(self) -> None:
        self._mode = "table" if self._mode == "range" else "range"
        self._stack.setCurrentIndex(1 if self._mode == "table" else 0)
        self._mode_btn.setText("📊 Range View" if self._mode == "table" else "▶ Play Spot (Table View)")
        if self._mode == "table":
            self._populate_table()
        else:
            self.load_spot()

    # ── load current spot ──────────────────────────────────────────────
    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot

        # Scenario top label
        name   = spot.get("name") or spot.get("title", spot.get("id", ""))
        stack  = spot.get("stack_bb", 40)
        fmt    = spot.get("format", "MTT")
        tbl    = spot.get("table", "8-max")
        self._scenario_lbl.setText(f"{fmt}  ·  {tbl}  ·  {stack}bb  ·  {name}")

        # Position strip
        self._rebuild_position_strip(spot)

        # Range view content
        self._spot_meta_label.setText(name)
        self._pot_label.setText(f"Pot {spot.get('pot_bb', 2.5):.1f}bb")

        # Strategy bars from solver
        solver = solve_spot(spot)
        _clear_layout(self._strategy_box)
        for a in solver.actions:
            bar = _StrategyBar(a.action, a.frequency)
            self._strategy_box.addWidget(bar)

        # Range matrix — driven by real pre-solved chart for this spot
        chart = chart_for_spot(spot)
        self._matrix.set_strategy(chart)
        # Highlight hero hand on matrix
        h169 = hand_169_from_cards(spot.get("hero_cards", ""))
        if h169:
            self._matrix.highlight_hand(h169)

        # Hand combos for hero hand — strategy from the live chart, NOT hardcoded
        _clear_layout(self._combos_grid)
        hero_hand = h169 or "AKs"
        hand_strat = strategy_for_hand(chart, hero_hand) if chart else {"fold": 1.0}
        combos = self._combos_for(hero_hand, hand_strat)
        for i, (combo_str, strat) in enumerate(combos):
            card = _HandComboCard(combo_str, strat)
            self._combos_grid.addWidget(card, i // 2, i % 2)

        # If currently in table mode, also refresh that
        if self._mode == "table":
            self._populate_table()

    def _rebuild_position_strip(self, spot: dict) -> None:
        _clear_layout(self._pos_row)
        positions = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        hero_pos = spot.get("position", "BTN")
        stack    = spot.get("stack_bb", 40)
        for pos in positions:
            is_hero = (pos == hero_pos)
            actions = self._actions_for_position(pos, hero_pos)
            chip = _PositionChip(pos, stack, actions, is_hero=is_hero)
            self._pos_row.addWidget(chip)
        self._pos_row.addStretch(1)

    def _actions_for_position(self, pos: str, hero_pos: str) -> list[tuple[str, str]]:
        """Demo: most positions fold preflop, hero shows raise+fold strategy."""
        if pos == hero_pos:
            return [("Fold", "fold"), ("Raise 2.3", "raise")]
        # Adjacent positions show a mix
        priors = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        try:
            hidx = priors.index(hero_pos); pidx = priors.index(pos)
        except ValueError:
            return [("Fold", "fold")]
        if pidx < hidx:  # before hero
            return [("Fold", "fold"), ("Raise 2.3", "raise")]
        return [("Fold", "fold")]

    # ── table mode helpers ─────────────────────────────────────────────
    def _populate_table(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        # Build a HandState-like state via LivePokerTable demo path
        # For simplicity, just describe context and let user pick action
        name  = spot.get("name") or spot.get("title", spot.get("id", ""))
        stack = spot.get("stack_bb", 40)
        fmt   = spot.get("format", "MTT")
        tbl   = spot.get("table", "8-max")
        pos   = spot.get("position", "BTN")
        self._tbl_ctx_label.setText(
            f"{stack}bb {tbl} {fmt}  ·  {pos}  ·  {name}  ·  pot {spot.get('pot_bb', 2.5):.1f}bb"
        )
        self._answered = False
        self._tbl_fb.setMaximumHeight(0)
        # Draw a static-ish table view
        self._live_table.update_state(None)  # clear

        # Action buttons
        _clear_layout(self._tbl_act_layout)
        self._action_btns = []
        options = spot.get("options") or ("fold", "call", "raise", "jam")
        for action in options:
            label = _action_display(action, spot)
            bg, border, fg = _action_colour_qss(action)
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton{{background:{bg};border:2px solid {border};border-radius:10px;"
                f"color:{fg};font-size:15px;font-weight:800;padding:12px 24px;"
                "min-height:58px;min-width:120px;}}"
                f"QPushButton:hover{{background:{bg}dd;}}"
            )
            btn.clicked.connect(lambda _, a=action: self._table_answer(a))
            self._tbl_act_layout.addWidget(btn)
            self._action_btns.append((btn, action))

    def _table_answer(self, action: str) -> None:
        if self._answered:
            return
        self._answered = True
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        is_ok    = result["is_correct"]
        ev_loss  = result["ev_loss"]
        best     = result["best_action"]

        # Show frequencies on buttons
        freq_map = {a["action"]: a["frequency"] for a in result["solver"]["actions"]}
        for btn, act in self._action_btns:
            btn.setEnabled(False)
            f = freq_map.get(act, 0.0)
            btn.setText(btn.text() + f"\n{f*100:.1f}%")

        # Feedback panel
        self._tbl_fb.setMaximumHeight(9999)
        _clear_layout(self._tbl_fb_layout)
        if is_ok:
            verdict = QLabel(f"✅  Doğru — EV kayıp: {ev_loss:.2f}bb")
            verdict.setStyleSheet(f"color:{_C_GREEN};font-size:14px;font-weight:700;")
        else:
            verdict = QLabel(f"❌  Hatalı — Sen: {action}  |  GTO: {best}  |  EV kayıp: {ev_loss:.2f}bb")
            verdict.setStyleSheet(f"color:{_C_RED};font-size:14px;font-weight:700;")
        self._tbl_fb_layout.addWidget(verdict)

        # Quick switch to range view
        ret_btn = QPushButton("📊 Show range matrix")
        ret_btn.setStyleSheet(_pill_style(active=True))
        ret_btn.clicked.connect(self._toggle_mode)
        self._tbl_fb_layout.addWidget(ret_btn)
        self.coach_message.emit(explain_spot(spot, action))

    # ── next spot ──────────────────────────────────────────────────────
    def _next_spot(self) -> None:
        self.index = (self.index + 1) % len(self.drills)
        self._answered = False
        self.load_spot()

    # ── hand-click in matrix ───────────────────────────────────────────
    def _on_hand_clicked(self, hand: str) -> None:
        self.coach_message.emit(f"{hand}: strategy detayı sol panelde gösteriliyor.")

    # ── scenario modal ─────────────────────────────────────────────────
    def _open_scenario(self) -> None:
        dlg = TrainerScenarioDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.result_data()
            # Filter drills based on selection
            stack = data.get("stack", "Any")
            filt = self.drills
            if stack != "Any":
                target = int(stack.replace("bb", ""))
                filt = [d for d in filt if abs(d.get("stack_bb", 40) - target) <= 5]
            hero_seat = data.get("hero_seat", "Any")
            if hero_seat != "Any":
                filt = [d for d in filt if d.get("position") == hero_seat]
            if filt:
                self.drills = filt
                self.index  = 0
                self.load_spot()
                self.coach_message.emit(f"Scenario uygulandı: {len(filt)} spot.")
            else:
                self.coach_message.emit("Bu filtre ile spot yok — varsayılan listeye dönülüyor.")

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _extract_grid_hand(hero_cards: str) -> Optional[str]:
        """'AsKh' → 'AKs' / 'AKo'. Best-effort."""
        if not hero_cards or len(hero_cards) < 4:
            return None
        ranks = "AKQJT98765432"
        c1, c2 = hero_cards[0], hero_cards[2]
        s1, s2 = hero_cards[1], hero_cards[3]
        if c1 == c2:
            return c1 + c2
        # higher rank first
        if ranks.index(c1) > ranks.index(c2):
            c1, c2 = c2, c1
            s1, s2 = s2, s1
        return c1 + c2 + ("s" if s1 == s2 else "o")

    @staticmethod
    def _combos_for(grid_hand: str, strategy: dict[str, float]) -> list[tuple[str, dict[str, float]]]:
        """Return up to 6 specific combos using the ACTUAL strategy for this hand."""
        suits = ["♠", "♥", "♦", "♣"]
        results: list[tuple[str, dict[str, float]]] = []
        # All combos for the same 169-hand share the strategy
        if len(grid_hand) == 2:  # Pair
            r = grid_hand[0]
            pairs = [(suits[i], suits[j]) for i in range(4) for j in range(i+1, 4)]
            for s1, s2 in pairs:
                results.append((f"{r}{s1}{r}{s2}", strategy))
        elif grid_hand.endswith("s"):
            r1, r2 = grid_hand[0], grid_hand[1]
            for s in suits:
                results.append((f"{r1}{s}{r2}{s}", strategy))
        else:  # offsuit
            r1, r2 = grid_hand[0], grid_hand[1]
            for s1 in suits:
                for s2 in suits:
                    if s1 != s2:
                        results.append((f"{r1}{s1}{r2}{s2}", strategy))
                        if len(results) >= 6: break
                if len(results) >= 6: break
        return results[:6]


# ── styling helper ────────────────────────────────────────────────────────

def _pill_style(active: bool) -> str:
    if active:
        return (
            f"QPushButton{{background:{_C_GREEN};color:#000;border-radius:6px;"
            "padding:5px 14px;font-weight:700;font-size:12px;border:none;}}"
            f"QPushButton:hover{{background:#0EA371;}}"
        )
    return (
        f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};border:1px solid {_C_BORDER};"
        "border-radius:6px;padding:5px 14px;font-size:12px;}}"
        f"QPushButton:hover{{border-color:{_C_CYAN};}}"
    )


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        cl = item.layout()
        if w:  w.deleteLater()
        if cl: _clear_layout(cl)
