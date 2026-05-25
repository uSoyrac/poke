"""Poker table components.

Two widgets live here:

- ``PokerTableView`` — legacy compact card (kept for trainers that just want
  hero cards + community on a felt). Old API: ``set_hand(hero, board, pot)``.

- ``LivePokerTable`` — full table render based on the Poke design spec
  (stadium felt, % seat positions, action chips, dealer button, bet chips,
  hero offset hole cards). Used by Play Session and Tournament Simulator
  to give one unified poker experience.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.ui.components.card_view import CardBackView, CardPlaceholder, CardView


# ───────────────────────── LEGACY (preserved) ─────────────────────────

class PlayerSeat(QFrame):
    def __init__(self, name: str, stack: str, highlight: bool = False):
        super().__init__()
        self.setObjectName("Elevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        name_label = QLabel(name)
        name_label.setObjectName("Cyan" if highlight else "Muted")
        stack_label = QLabel(stack)
        stack_label.setObjectName("Green" if highlight else "Meta")
        layout.addWidget(name_label)
        layout.addWidget(stack_label)


class PokerTableView(QFrame):
    """Legacy compact table card. Kept so other trainers keep working."""

    def __init__(self):
        super().__init__()
        self.setObjectName("PokerTable")
        self.hero_cards = QHBoxLayout()
        self.board_cards = QHBoxLayout()
        self.pot_label = QLabel("Pot 0bb")
        self.pot_label.setObjectName("SectionTitle")
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(PlayerSeat("UTG Bot", "100bb"), 0, 1)
        layout.addWidget(PlayerSeat("CO Bot", "96bb"), 1, 0)
        layout.addWidget(PlayerSeat("BTN Bot", "112bb"), 1, 2)
        layout.addWidget(PlayerSeat("Hero", "100bb", True), 2, 1)
        center = QVBoxLayout()
        center.setAlignment(Qt.AlignCenter)
        center.addWidget(self.pot_label, alignment=Qt.AlignCenter)
        board_holder = QFrame()
        board_holder.setLayout(self.board_cards)
        center.addWidget(board_holder, alignment=Qt.AlignCenter)
        hero_holder = QFrame()
        hero_holder.setLayout(self.hero_cards)
        center.addWidget(hero_holder, alignment=Qt.AlignCenter)
        layout.addLayout(center, 1, 1)

    def set_hand(self, hero_cards: str, board: str, pot: float) -> None:
        _clear_layout(self.hero_cards)
        _clear_layout(self.board_cards)
        cards = [hero_cards[i : i + 2] for i in range(0, min(len(hero_cards), 4), 2)]
        for card in cards:
            self.hero_cards.addWidget(CardView(card))
        if board and board != "preflop":
            for card in [board[i : i + 2] for i in range(0, len(board), 2)]:
                self.board_cards.addWidget(CardView(card))
        else:
            self.board_cards.addWidget(QLabel("Preflop"))
        self.pot_label.setText(f"Pot {pot:.1f}bb")


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()


# ───────────────────────── DESIGN TOKENS ──────────────────────────────

# Mirrors theme.css from the design bundle (Poke dark)
BG          = "#0a0c0a"
BG2         = "#131613"
INK         = "#f4f5ee"
INK2        = "#d6d8cf"
LINE        = "#23271f"
LINE2       = "#33382c"
MUTED       = "#898d80"
DIM         = "#5a5e54"
ACCENT      = "#5ad17a"   # lime — HERO
ACCENT_INK  = "#0a0c0a"
DANGER      = "#e87474"   # red — VILLAIN / RAISE / JAM
DANGER2     = "#f29090"
INFO        = "#5ad1ce"   # cyan — CHECK
WARN        = "#d6c668"
FELT_TINT   = QColor(90, 209, 122, int(0.14 * 255))   # accent @ 14%
FELT_TINT2  = QColor(90, 209, 122, int(0.06 * 255))


# ───────────────────────── SLOT LAYOUTS ───────────────────────────────
# Slots are (x%, y%) inside the felt. Slot 0 = hero (bottom-center).
# Other slots are arranged in player-list order from hero (CCW on screen,
# which matches real-table clockwise action order — hero's first opponent
# sits to hero's left).

SLOTS = {
    2: [(50, 90), (50, 10)],
    3: [(50, 90), (10, 35), (90, 35)],
    4: [(50, 92), (10, 60), (50, 10), (90, 60)],
    5: [(50, 92), (10, 70), (25, 12), (75, 12), (90, 70)],
    6: [(50, 92), (12, 78), (8, 35), (35, 8), (75, 8), (92, 45)],
    7: [(50, 92), (15, 82), (5, 50), (22, 12), (78, 12), (95, 50), (85, 82)],
    8: [(50, 94), (22, 90), (5, 60), (10, 22), (50, 5),
        (90, 22), (95, 60), (78, 90)],
    9: [(50, 94), (22, 90), (5, 62), (8, 28), (28, 6), (72, 6),
        (92, 28), (95, 62), (78, 90)],
}


def _slots_for(n: int) -> List[Tuple[int, int]]:
    if n <= 2:
        return SLOTS[2]
    return SLOTS.get(n, SLOTS[9])


# ───────────────────────── ACTION TONE ────────────────────────────────

def _action_tone(action: str) -> str:
    a = (action or "").upper()
    if a in ("FOLD",):                                          return "fold"
    if a in ("CHECK",):                                         return "check"
    if a in ("CALL", "OPEN", "LIMP"):                           return "call"
    if a in ("ALL-IN", "ALL_IN", "JAM"):                        return "jam"
    return "raise"  # BET, RAISE, 3-BET, 4-BET


_CHIP_STYLE = {
    "fold":  f"background:{BG2}; color:{MUTED}; border:1px solid {LINE2};",
    "check": f"background:{BG2}; color:{INFO};  border:1px solid {INFO};",
    "call":  f"background:{ACCENT}; color:{ACCENT_INK}; border:1px solid {ACCENT};",
    "raise": f"background:{DANGER}; color:#fff; border:1px solid {DANGER};",
    "jam":   f"background:{DANGER}; color:#fff; border:2px solid {DANGER2};",
    "blind": f"background:#1f1a0d; color:{WARN}; border:1px solid #5a4f28;",
}


# ───────────────────────── SEAT WIDGET ────────────────────────────────

@dataclass
class SeatState:
    pos: str = ""           # poker position (UTG, BTN, …)
    name: str = ""
    stack: float = 0.0
    bet: float = 0.0
    action: str = ""        # FOLD/CHECK/CALL/RAISE/BET/ALL-IN/3-BET…
    is_hero: bool = False
    is_villain: bool = False
    is_acting: bool = False
    is_folded: bool = False
    is_all_in: bool = False
    is_eliminated: bool = False
    is_blind_post: bool = False              # SB/BB forced bet (pre-action)
    is_winner: bool = False                  # crown / WIN badge at showdown
    hole: Optional[Sequence[str]] = None     # showdown reveal
    stack_unit: str = "bb"                   # "bb" or "chips"
    hud_stats: Optional[dict] = None         # VPIP/PFR/AF/etc. for tooltip


class _Seat(QFrame):
    """Single seat tile — pos + stack + action chip."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build()

    def _build(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.setAlignment(Qt.AlignHCenter)

        self.tag = QLabel("")
        self.tag.setAlignment(Qt.AlignCenter)
        self.tag.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; font-size:9px; "
            f"letter-spacing:2px; color:{ACCENT}; padding:0; background:transparent;"
        )
        v.addWidget(self.tag)

        self.card = QFrame()
        self.card.setObjectName("PTSeatCard")
        c_l = QVBoxLayout(self.card)
        c_l.setContentsMargins(10, 6, 10, 6)
        c_l.setSpacing(1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.pos_label = QLabel("")
        self.pos_label.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; font-size:10px; "
            f"letter-spacing:1.5px; color:{MUTED}; background:transparent;"
        )
        self.stack_label = QLabel("")
        self.stack_label.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; font-size:14px; "
            f"font-weight:500; color:{INK}; background:transparent;"
        )
        row.addWidget(self.pos_label)
        row.addStretch(1)
        row.addWidget(self.stack_label)
        c_l.addLayout(row)

        self.name_label = QLabel("")
        self.name_label.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; font-size:10px; "
            f"color:{MUTED}; background:transparent;"
        )
        c_l.addWidget(self.name_label)
        v.addWidget(self.card)

        self.action_chip = QLabel("")
        self.action_chip.setAlignment(Qt.AlignCenter)
        self.action_chip.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; font-size:10px; "
            f"font-weight:600; letter-spacing:1.4px; padding:2px 8px;"
        )
        self.action_chip.hide()
        v.addWidget(self.action_chip)

    def apply(self, state: SeatState, show_name: bool) -> None:
        if state.is_eliminated:
            self.hide()
            return
        self.show()

        # Tone — hero / villain / folded / default
        if state.is_hero:
            tone = "hero"
        elif state.is_villain:
            tone = "villain"
        elif state.is_folded:
            tone = "out"
        else:
            tone = "default"

        # Tag (HERO / VILLAIN / WIN)
        if state.is_winner:
            self.tag.setText("◆ WINNER")
            self.tag.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"font-weight:700; letter-spacing:2px; "
                f"color:{ACCENT_INK}; background:{ACCENT}; padding:2px 6px;"
            )
        elif tone == "hero":
            self.tag.setText("HERO")
            self.tag.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:2px;"
                f"color:{ACCENT}; background:transparent;"
            )
        elif tone == "villain":
            self.tag.setText("VILLAIN")
            self.tag.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:9px; letter-spacing:2px;"
                f"color:{DANGER2}; background:transparent;"
            )
        else:
            self.tag.setText("")

        # Seat card colors
        if tone == "hero":
            border, bg = ACCENT, "#11241a"
        elif tone == "villain":
            border, bg = DANGER, "#1f1316"
        elif tone == "out":
            border, bg = LINE, BG
        else:
            border, bg = LINE2, BG2
        self.card.setStyleSheet(
            f"QFrame#PTSeatCard {{ background:{bg}; border:1px solid {border}; }}"
        )
        op = 0.55 if state.is_folded else 1.0
        self.setWindowOpacity(op)  # no-op on most platforms; use stylesheet color drop
        if state.is_folded:
            self.pos_label.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"letter-spacing:1.5px; color:{DIM}; background:transparent;"
            )
            self.stack_label.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:14px; "
                f"color:{DIM}; background:transparent;"
            )
        else:
            pos_color = ACCENT if tone == "hero" else (DANGER2 if tone == "villain" else MUTED)
            self.pos_label.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"letter-spacing:1.5px; color:{pos_color}; background:transparent;"
            )
            self.stack_label.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:14px; "
                f"font-weight:500; color:{INK}; background:transparent;"
            )

        # Acting border ring
        if state.is_acting and not state.is_folded:
            self.card.setStyleSheet(
                f"QFrame#PTSeatCard {{ background:{bg}; border:2px solid {WARN}; }}"
            )

        # Content
        self.pos_label.setText(state.pos.upper())
        unit = state.stack_unit
        if unit == "chips":
            self.stack_label.setText(f"{int(state.stack):,}")
        else:
            self.stack_label.setText(f"{state.stack:.1f}{unit}")
        if show_name and state.name:
            self.name_label.setText(state.name[:12])
            self.name_label.show()
        else:
            self.name_label.hide()

        # HUD tooltip — opponent stats on hover
        if state.hud_stats and not state.is_hero:
            h = state.hud_stats
            af = h.get("af", h.get("aggression", 0))
            self.card.setToolTip(
                f"<b style='color:#5ad17a'>{state.name or state.pos}</b><br>"
                f"<table cellpadding='2'>"
                f"<tr><td>VPIP</td><td><b>{h.get('vpip',0):.0f}%</b></td>"
                f"    <td>&nbsp;PFR</td><td><b>{h.get('pfr',0):.0f}%</b></td>"
                f"    <td>&nbsp;3bet</td><td><b>{h.get('three_bet',0):.0f}%</b></td></tr>"
                f"<tr><td>AF</td><td><b>{af:.1f}</b></td>"
                f"    <td>&nbsp;F-cbet</td><td><b>{h.get('fold_to_cbet',0):.0f}%</b></td>"
                f"    <td>&nbsp;Call↓</td><td><b>{h.get('call_down',0)*100:.0f}%</b></td></tr>"
                f"<tr><td>RvBluff</td><td><b>{h.get('river_bluff',0)*100:.0f}%</b></td>"
                f"    <td>&nbsp;Overbet</td><td><b>{h.get('overbet_freq',0)*100:.0f}%</b></td></tr>"
                f"</table>"
                f"<i style='color:#898d80'>{h.get('notes','')}</i>"
            )
        else:
            self.card.setToolTip("")

        # Action chip
        action = state.action.upper()
        if state.is_folded and not action:
            action = "FOLD"
        # SB/BB before any voluntary action — show explicit blind tag
        if state.is_blind_post and not action:
            pos = state.pos.upper()
            if "BB" in pos:
                action = "BB POST"
            elif "SB" in pos:
                action = "SB POST"
            else:
                action = "POST"
        if action and not state.is_eliminated:
            tone_key = _action_tone(action)
            if state.is_blind_post:
                tone_key = "blind"
            txt = action
            if state.bet > 0 and tone_key not in ("fold", "check"):
                if unit == "chips":
                    txt = f"{action} · {int(state.bet):,}"
                else:
                    txt = f"{action} · {state.bet:.1f}"
            self.action_chip.setText(txt)
            chip_css = _CHIP_STYLE.get(tone_key, _CHIP_STYLE["raise"])
            self.action_chip.setStyleSheet(
                f"font-family:'JetBrains Mono',monospace; font-size:10px; "
                f"font-weight:700; letter-spacing:1.4px; padding:3px 9px; "
                + chip_css
            )
            self.action_chip.show()
        else:
            self.action_chip.hide()

    def sizeHint(self):  # type: ignore[override]
        return self.minimumSizeHint()


# ───────────────────────── CENTER WIDGET ──────────────────────────────

class _Center(QFrame):
    """Pot + board + street tag at the heart of the felt."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.setAlignment(Qt.AlignCenter)

        self.street_tag = QLabel("PREFLOP")
        self.street_tag.setAlignment(Qt.AlignCenter)
        self.street_tag.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"letter-spacing:1.6px; color:{ACCENT}; "
            f"padding:3px 10px; border:1px solid #2a4a30; background:#0f1d11;"
        )
        tag_row = QHBoxLayout()
        tag_row.addStretch(1); tag_row.addWidget(self.street_tag); tag_row.addStretch(1)
        v.addLayout(tag_row)

        self.board_row = QHBoxLayout()
        self.board_row.setSpacing(4)
        self.board_row.setAlignment(Qt.AlignCenter)
        v.addLayout(self.board_row)

        self.pot_label = QLabel("POT")
        self.pot_label.setAlignment(Qt.AlignCenter)
        self.pot_label.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"letter-spacing:2.2px; color:{MUTED}; background:transparent;"
        )
        v.addWidget(self.pot_label)

        self.pot_value = QLabel("0")
        self.pot_value.setAlignment(Qt.AlignCenter)
        self.pot_value.setStyleSheet(
            f"font-family:'Space Grotesk','Inter',sans-serif; font-size:44px; "
            f"font-weight:700; color:{INK}; letter-spacing:-1.5px; background:transparent;"
        )
        v.addWidget(self.pot_value)

        self.note = QLabel("")
        self.note.setAlignment(Qt.AlignCenter)
        self.note.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:10px; "
            f"letter-spacing:1.5px; color:{DIM}; background:transparent;"
        )
        v.addWidget(self.note)

    def update_state(self, street: str, board: Sequence[str], pot: float,
                     unit: str, note: str, big_pot: bool,
                     to_call: float = 0.0) -> None:
        # TO CALL is rendered by the action deck now (see LivePokerTable
        # docstring + screens), not in the center — keeps the felt clean
        # under the hero hole cards.
        self.street_tag.setText(street.upper())
        _clear_layout(self.board_row)
        size = "md"
        cards_to_show = list(board)
        for c in cards_to_show:
            self.board_row.addWidget(CardView(c, size=size))
        for _ in range(5 - len(cards_to_show)):
            self.board_row.addWidget(CardPlaceholder(size=size))

        # Pot value — for bb mode include the unit; for chips show clean integer
        if unit == "chips":
            pot_txt = f"{int(pot):,}"
        else:
            pot_txt = f"{pot:.1f}bb"
        self.pot_value.setText(pot_txt)
        self.pot_value.setStyleSheet(
            f"font-family:'Space Grotesk','Inter',sans-serif; "
            f"font-size:{56 if big_pot else 40}px; "
            f"font-weight:700; color:{INK}; letter-spacing:-2px; background:transparent;"
        )
        self.note.setText(note)
        self.note.setVisible(bool(note))


# ───────────────────────── DEALER + BET CHIP ──────────────────────────

class _DealerButton(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__("D", parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(22, 22)
        self.setStyleSheet(
            f"font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; "
            f"color:{BG}; background:{INK}; border:1px solid {LINE2}; border-radius:11px;"
        )


class _BetChip(QFrame):
    """Bet indicator at a seat — chip stack icon + amount in bb + % of pot.

    Lives between the seat and the felt center. Big and readable so the
    user can see at a glance who put what in.
    """

    # Fixed size — Qt sizeHint() is unreliable for freshly-created child widgets
    # that haven't been through a layout pass yet, so we lock the chip's
    # geometry instead of trusting adjustSize().
    _CHIP_W = 96
    _CHIP_H = 58

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("PTBetChip")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(self._CHIP_W, self._CHIP_H)
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 3, 6, 3)
        v.setSpacing(1)
        v.setAlignment(Qt.AlignCenter)

        # Chip stack (rectangular bands, sharp corners — Poke brutalist)
        self.chips = QLabel("▬▬▬")
        self.chips.setAlignment(Qt.AlignCenter)
        v.addWidget(self.chips)

        self.amount = QLabel("0")
        self.amount.setAlignment(Qt.AlignCenter)
        v.addWidget(self.amount)

        self.pot_pct = QLabel("")
        self.pot_pct.setAlignment(Qt.AlignCenter)
        v.addWidget(self.pot_pct)

    def apply(self, amount: float, tone: str, unit: str,
              pot: float, kind: str = "bet") -> None:
        """kind: 'bet' (chips committed) or 'blind' (forced post)."""
        if kind == "blind":
            color, border, bg = WARN, "#5a4f28", "#1f1a0d"
            chip_glyph = "▬▬"
        elif tone == "hero":
            color, border, bg = ACCENT, ACCENT, "#11241a"
            chip_glyph = "▬▬▬▬"
        elif tone == "villain":
            color, border, bg = DANGER2, DANGER, "#1f1316"
            chip_glyph = "▬▬▬▬"
        else:
            color, border, bg = INK2, LINE2, BG2
            chip_glyph = "▬▬▬"

        self.setStyleSheet(
            f"QFrame#PTBetChip {{ background:{bg}; border:1px solid {border}; }}"
        )
        self.chips.setStyleSheet(
            f"color:{color}; font-size:11px; font-weight:900; "
            f"letter-spacing:-2px; background:transparent;"
        )
        self.chips.setText(chip_glyph)

        # Main amount — readable size, mono numbers
        if unit == "chips":
            amt_txt = f"{int(amount):,}"
        else:
            amt_txt = f"{amount:.1f} bb"
        self.amount.setText(amt_txt)
        self.amount.setStyleSheet(
            f"font-family:'JetBrains Mono','Menlo',monospace; "
            f"font-size:13px; font-weight:700; color:{color}; "
            f"background:transparent; letter-spacing:0.5px;"
        )

        # Percent of pot — only meaningful when there IS a pot to compare against
        if pot > 0 and kind != "blind":
            pct = int(round(100 * amount / pot))
            self.pot_pct.setText(f"{pct}% pot")
            self.pot_pct.setStyleSheet(
                f"font-family:'JetBrains Mono','Menlo',monospace; "
                f"font-size:9px; color:{MUTED}; background:transparent; "
                f"letter-spacing:1px;"
            )
            self.pot_pct.show()
        elif kind == "blind":
            self.pot_pct.setText("BLIND")
            self.pot_pct.setStyleSheet(
                f"font-family:'JetBrains Mono','Menlo',monospace; "
                f"font-size:9px; font-weight:700; color:{WARN}; "
                f"background:transparent; letter-spacing:1.4px;"
            )
            self.pot_pct.show()
        else:
            self.pot_pct.hide()


# ───────────────────────── MAIN WIDGET ────────────────────────────────

class LivePokerTable(QWidget):
    """Full live poker table — stadium felt with absolutely-positioned seats."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(380)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

        self._seats: List[_Seat] = []
        self._hole_widgets: List[QWidget] = []     # hero hole + opponent backs
        self._bet_chips: List[_BetChip] = []
        self._slot_positions: List[Tuple[int, int]] = []
        self._seat_states: List[SeatState] = []
        self._hero_cards: Optional[Sequence[str]] = None
        self._unit: str = "bb"
        self._dealer_slot_idx: int = -1
        self._hero_slot_idx: int = 0

        # The center (pot/board) is a child positioned by resizeEvent
        self.center = _Center(self)
        self.dealer_btn = _DealerButton(self)
        self.dealer_btn.hide()

    # ── PUBLIC API ─────────────────────────────────────────────────

    def set_unit(self, unit: str) -> None:
        """'bb' for cash, 'chips' for tournament."""
        self._unit = "chips" if unit == "chips" else "bb"

    def render_state(
        self,
        seats: Sequence[SeatState],
        hero_slot_idx: int,
        dealer_slot_idx: int,
        street: str,
        board: Sequence[str],
        pot: float,
        hero_cards: Optional[Sequence[str]] = None,
        note: str = "",
        big_pot: bool = False,
        show_opponent_backs: bool = True,
        to_call: float = 0.0,
    ) -> None:
        """Replace the entire visual state. seats are in slot-order (slot 0 = hero)."""
        n = len(seats)
        self._slot_positions = _slots_for(n)
        self._seat_states = list(seats)
        self._hero_cards = hero_cards
        self._hero_slot_idx = max(0, min(hero_slot_idx, n - 1))
        self._dealer_slot_idx = dealer_slot_idx if 0 <= dealer_slot_idx < n else -1

        # Resize seat pool to match
        while len(self._seats) < n:
            self._seats.append(_Seat(self))
        while len(self._seats) > n:
            w = self._seats.pop()
            w.setParent(None)
            w.deleteLater()

        # Resize bet chip pool (one per seat — only those with bet>0 will be shown)
        while len(self._bet_chips) < n:
            self._bet_chips.append(_BetChip(self))
        while len(self._bet_chips) > n:
            w = self._bet_chips.pop()
            w.setParent(None)
            w.deleteLater()

        # Apply seat data
        for idx, (seat, st) in enumerate(zip(self._seats, seats)):
            st.stack_unit = self._unit
            seat.apply(st, show_name=bool(st.name))

        # Hole / opponent cards: tear down and rebuild
        for w in self._hole_widgets:
            w.setParent(None)
            w.deleteLater()
        self._hole_widgets = []

        # Hero hole
        if hero_cards and len(hero_cards) >= 2:
            for card in list(hero_cards)[:2]:
                cv = CardView(card, size="lg")
                cv.setParent(self)
                cv.show()
                self._hole_widgets.append(cv)

        # Opponent backs / showdown reveals
        for idx, st in enumerate(seats):
            if idx == hero_slot_idx:
                continue
            if st.is_eliminated or st.is_folded:
                continue
            if st.hole and len(st.hole) >= 2:
                for code in list(st.hole)[:2]:
                    cv = CardView(code, size="sm")
                    cv.setParent(self)
                    cv._slot_idx = idx
                    cv.show()
                    self._hole_widgets.append(cv)
            elif show_opponent_backs:
                for _ in range(2):
                    cv = CardBackView(size="sm")
                    cv.setParent(self)
                    cv._slot_idx = idx
                    cv.show()
                    self._hole_widgets.append(cv)

        # Bet chips — surface every chips-on-the-table commitment so the user
        # can read who put what in. Blinds get their own warning-yellow style.
        for chip, st in zip(self._bet_chips, seats):
            if st.bet > 0 and not st.is_folded and not st.is_eliminated:
                tone = "hero" if st.is_hero else ("villain" if st.is_villain else "neutral")
                kind = "blind" if st.is_blind_post else "bet"
                chip.apply(st.bet, tone, self._unit, pot=pot, kind=kind)
                chip.show()
                chip.raise_()  # always on top — never hidden by hole cards
            else:
                chip.hide()

        # Center
        self.center.update_state(street, board, pot, self._unit, note, big_pot,
                                 to_call=to_call)
        self.dealer_btn.setVisible(self._dealer_slot_idx >= 0)

        # Lay out immediately AND on the next event-loop tick. The deferred
        # pass catches the case where render_state runs before the parent
        # layout has resized this widget — width()/height() at this instant
        # may still be small / default, and chips would be placed against
        # those wrong bounds. The deferred pass corrects them once Qt has
        # finalised our geometry.
        self._layout_children()
        QTimer.singleShot(0, self._layout_children)
        self.update()

    # ── LAYOUT / PAINT ─────────────────────────────────────────────

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_children()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        # Qt only finalises this widget's geometry when it's actually shown —
        # rerun layout here so chips/cards land at the correct screen
        # coordinates even if render_state ran before the first show.
        self._layout_children()

    def _felt_rect(self) -> QRectF:
        w, h = self.width(), self.height()
        # 8% horizontal / 6% vertical inset for the felt oval
        return QRectF(w * 0.08, h * 0.06, w * 0.84, h * 0.88)

    def _slot_xy(self, x_pct: int, y_pct: int) -> QPointF:
        r = self._felt_rect()
        return QPointF(r.x() + r.width() * x_pct / 100.0,
                       r.y() + r.height() * y_pct / 100.0)

    def _center_point(self) -> QPointF:
        r = self._felt_rect()
        return QPointF(r.center().x(), r.center().y())

    def _layout_children(self) -> None:
        if not self._slot_positions:
            # Still center the center widget
            self.center.adjustSize()
            cw, ch = self.center.sizeHint().width(), self.center.sizeHint().height()
            self.center.setGeometry(int(self.width() / 2 - cw / 2),
                                    int(self.height() / 2 - ch / 2), cw, ch)
            return

        # Position center
        self.center.adjustSize()
        c_size = self.center.sizeHint()
        cw, ch = max(c_size.width(), 180), max(c_size.height(), 180)
        cx, cy = self._center_point().x(), self._center_point().y()
        self.center.setGeometry(int(cx - cw / 2), int(cy - ch / 2), cw, ch)

        # Position seats
        for slot_idx, (xp, yp) in enumerate(self._slot_positions):
            if slot_idx >= len(self._seats):
                break
            seat = self._seats[slot_idx]
            seat.adjustSize()
            sh = seat.sizeHint()
            sw, shh = max(sh.width(), 132), sh.height()
            p = self._slot_xy(xp, yp)
            seat.setGeometry(int(p.x() - sw / 2), int(p.y() - shh / 2), sw, shh)

        cx, cy = self._center_point().x(), self._center_point().y()

        # Hero hole cards — 32% toward center. Far enough from the seat
        # tile that the position/stack stays readable behind the cards;
        # close enough that they don't crowd the pot.
        if self._hero_cards and self._hero_slot_idx < len(self._slot_positions):
            xp, yp = self._slot_positions[self._hero_slot_idx]
            hero_point = self._slot_xy(xp, yp)
            tx = hero_point.x() + (cx - hero_point.x()) * 0.32
            ty = hero_point.y() + (cy - hero_point.y()) * 0.32
            hero_holes = self._hole_widgets[:2]
            if hero_holes:
                gap = 6
                total_w = sum(w.width() for w in hero_holes) + gap * (len(hero_holes) - 1)
                wh = hero_holes[0].height()
                start_x = tx - total_w / 2
                for w in hero_holes:
                    w.setGeometry(int(start_x), int(ty - wh / 2), w.width(), w.height())
                    start_x += w.width() + gap

        # Opponent back/face cards — tight against their seat tile (10%).
        # NB: this MUST run independently of `if self._hero_cards` above,
        # otherwise opponent cards stay at (0,0) whenever hero has no cards.
        opponent_card_widgets = self._hole_widgets[2:] if self._hero_cards else self._hole_widgets
        by_slot: dict[int, list[QWidget]] = {}
        for w in opponent_card_widgets:
            slot = getattr(w, "_slot_idx", None)
            if slot is None:
                continue
            by_slot.setdefault(slot, []).append(w)
        for slot, ws in by_slot.items():
            if slot >= len(self._slot_positions):
                continue
            sx, sy = self._slot_positions[slot]
            p = self._slot_xy(sx, sy)
            # 28% toward center — clears the seat tile (which is ±4% wide)
            # AND stays well clear of the bet chip at 55%.
            tx2 = p.x() + (cx - p.x()) * 0.28
            ty2 = p.y() + (cy - p.y()) * 0.28
            gap2 = 2
            total_w2 = sum(w.width() for w in ws) + gap2 * (len(ws) - 1)
            wh2 = ws[0].height()
            start_x2 = tx2 - total_w2 / 2
            for w in ws:
                w.setGeometry(int(start_x2), int(ty2 - wh2 / 2), w.width(), w.height())
                start_x2 += w.width() + gap2

        # Bet chips — fixed-size, positioned 52% from seat toward center.
        # We iterate over ALL chip slots (not just visible ones) so a chip
        # that's about to be shown lands at the right coordinates *before*
        # Qt's first paint, never at the parent's (0, 0) origin.
        # Belt-and-braces: both setGeometry() and move() — the move() call
        # wins against any latent layout pass that might still own the
        # widget. raise_() keeps visible chips on top of the felt paint.
        cw, ch = _BetChip._CHIP_W, _BetChip._CHIP_H
        for slot_idx, (xp, yp) in enumerate(self._slot_positions):
            if slot_idx >= len(self._bet_chips):
                break
            chip = self._bet_chips[slot_idx]
            p = self._slot_xy(xp, yp)
            tx = p.x() + (cx - p.x()) * 0.52
            ty = p.y() + (cy - p.y()) * 0.52
            x = int(tx - cw / 2)
            y = int(ty - ch / 2)
            chip.setFixedSize(cw, ch)
            chip.setGeometry(x, y, cw, ch)
            chip.move(x, y)
            if chip.isVisible():
                chip.raise_()

        # Dealer button — 22% toward center from dealer's slot
        if self._dealer_slot_idx >= 0 and self._dealer_slot_idx < len(self._slot_positions):
            xp, yp = self._slot_positions[self._dealer_slot_idx]
            p = self._slot_xy(xp, yp)
            cx, cy = self._center_point().x(), self._center_point().y()
            tx = p.x() + (cx - p.x()) * 0.22
            ty = p.y() + (cy - p.y()) * 0.22
            self.dealer_btn.move(int(tx - 11), int(ty - 11))

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Background
        painter.fillRect(self.rect(), QColor(BG))

        # Felt — stadium ellipse with radial glow
        r = self._felt_rect()
        glow = QRadialGradient(r.center(), max(r.width(), r.height()) / 2)
        glow.setColorAt(0.0, FELT_TINT)
        glow.setColorAt(0.5, FELT_TINT2)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow))
        painter.setPen(QPen(QColor(LINE2), 2))
        # Stadium = rounded with 50%/40% radii — Qt: rx/ry
        rx, ry = r.width() * 0.5, r.height() * 0.4
        painter.drawRoundedRect(r, rx, ry)

        # Inner faint ring for depth
        inner = QRectF(r.x() + r.width() * 0.07, r.y() + r.height() * 0.10,
                       r.width() * 0.86, r.height() * 0.80)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(35, 39, 31), 1))
        painter.drawRoundedRect(inner, inner.width() * 0.5, inner.height() * 0.4)

        painter.end()


# ───────────────────────── HIGH-LEVEL HELPER ──────────────────────────

def seats_from_hand(
    players: Sequence,
    hero_seat: int,
    action_queue_top: int = -1,
    villain_seat: Optional[int] = None,
    unit: str = "bb",
    hand=None,
    bb_divisor: float = 1.0,
    bot_profiles: Optional[dict] = None,   # {player_idx: BotProfile} for HUD tooltips
) -> Tuple[List[SeatState], int, int]:
    """Map a list of PlayerSeat (game engine) → slot-ordered SeatState list.

    Returns (seat_states, hero_slot_idx, dealer_slot_idx).

    When ``hand`` is provided, SB/BB players whose only commitment on this
    street is the forced blind get flagged as ``is_blind_post`` so the UI
    can show a distinct "SB POST 0.5" / "BB POST 1.0" chip.

    ``bb_divisor``: divide raw chip values (stack, bet) by this before
    storing — used by the tournament screen to display everything in BB
    instead of raw chips. Pass ``hand.big_blind`` for BB conversion, or
    leave at 1.0 to keep chips.
    """
    n = len(players)
    if n == 0:
        return [], 0, -1

    # Identify SB/BB pre-action — they have current_bet > 0 but no recorded
    # preflop action yet.
    blind_posters: set[int] = set()
    if hand is not None:
        try:
            from app.engine.hand_state import Street as _Street
            acted: set[int] = {
                a.player_idx for a in getattr(hand, "actions", [])
                if a.street == _Street.PREFLOP
            }
            if getattr(hand, "street", None) == _Street.PREFLOP:
                for i, p in enumerate(players):
                    pos = (getattr(p, "position", "") or "").upper()
                    if pos in ("SB", "BB", "SB/BTN") and i not in acted and p.current_bet > 0:
                        blind_posters.add(i)
        except Exception:
            pass

    winners_set = set(getattr(hand, "winners", []) or []) if hand is not None else set()
    is_complete = bool(getattr(hand, "is_complete", False)) if hand is not None else False

    seat_states: List[SeatState] = []
    dealer_slot_idx = -1
    hero_slot_idx = 0
    cur = hero_seat
    visited = 0
    div = max(bb_divisor, 1e-9)
    while visited < n:
        p = players[cur]
        if not getattr(p, "is_eliminated", False):
            # Showdown reveal — every contestant still in the hand at
            # hand-complete time gets their hole cards exposed face-up.
            hole_codes: Optional[List[str]] = None
            if (is_complete
                    and not bool(getattr(p, "is_folded", False))
                    and not p.is_hero
                    and getattr(p, "hole_cards", None)):
                hole_codes = [c.display for c in p.hole_cards[:2]]

            # HUD stats from bot profile (if provided)
            hud: Optional[dict] = None
            if bot_profiles and cur in bot_profiles and not p.is_hero:
                prof = bot_profiles[cur]
                hud = {
                    "vpip":         getattr(prof, "vpip", 0),
                    "pfr":          getattr(prof, "pfr", 0),
                    "three_bet":    getattr(prof, "three_bet", 0),
                    "aggression":   getattr(prof, "aggression", 0),
                    "af":           getattr(prof, "aggression", 0),
                    "fold_to_cbet": getattr(prof, "fold_to_cbet", 0),
                    "river_bluff":  getattr(prof, "river_bluff", 0),
                    "call_down":    getattr(prof, "call_down", 0),
                    "overbet_freq": getattr(prof, "overbet_freq", 0),
                    "notes":        getattr(prof, "notes", ""),
                }

            st = SeatState(
                pos=getattr(p, "position", "") or "",
                name=p.name if not p.is_hero else "",
                stack=float(p.stack) / div,
                bet=float(getattr(p, "current_bet", 0.0) or 0.0) / div,
                is_hero=p.is_hero,
                is_acting=(cur == action_queue_top),
                is_folded=bool(getattr(p, "is_folded", False)),
                is_all_in=bool(getattr(p, "is_all_in", False)),
                is_eliminated=False,
                is_blind_post=(cur in blind_posters),
                is_winner=(is_complete and cur in winners_set),
                hole=hole_codes,
                stack_unit=unit,
                hud_stats=hud,
            )
            if villain_seat is not None and cur == villain_seat:
                st.is_villain = True
            elif not p.is_hero and cur == action_queue_top:
                st.is_villain = True

            if st.is_folded:
                st.action = "FOLD"
            elif st.is_all_in:
                st.action = "ALL-IN"

            if cur == hero_seat:
                hero_slot_idx = len(seat_states)
            seat_states.append(st)
            if getattr(p, "position", "").upper() in ("BTN", "SB/BTN") and dealer_slot_idx < 0:
                dealer_slot_idx = len(seat_states) - 1
        cur = (cur + 1) % n
        visited += 1

    return seat_states, hero_slot_idx, dealer_slot_idx
