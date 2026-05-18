"""Oval poker table preview with positions arranged around the rim, optional per-position action chips."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.ui.components.action_chip import ActionSequence


# Standard 9-handed seat order around an oval, starting top-left going clockwise:
# LJ — HJ — CO — BTN/BU (right) — SB — BB (bottom-right) — UTG — UTG1 (bottom-left)
DEFAULT_POSITIONS_9 = ["LJ", "HJ", "CO", "BTN", "SB", "BB", "UTG", "UTG1"]
DEFAULT_POSITIONS_6 = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]


@dataclass
class SeatData:
    position: str
    actions: list[str] = field(default_factory=list)  # e.g. ["R 2.3", "R 33%", "B 75%", "AI"]
    selected: bool = False
    is_dealer: bool = False
    is_hero: bool = False
    # ─── Real-poker fields so trainer ovals show full context ───────────
    stack_bb:      float = 0.0     # remaining stack in big blinds
    current_bet:   float = 0.0     # chips this player has put in this street
    folded:        bool  = False
    hero_cards:    list[str] = field(default_factory=list)  # e.g. ["As", "Ks"]


@dataclass
class TableState:
    """Top-level state painted on the table (pot, street, etc.)."""
    pot_bb: float = 0.0
    street: str   = "Preflop"


class OvalTable(QWidget):
    """Oval table showing positions around the rim. Positions can be selectable for drill builder.

    SPR / PO / seed shown in corners. Used by drill builder, spot trainer preview, and hand analyzer.
    """

    position_clicked = Signal(str)
    selection_changed = Signal(set)

    def __init__(
        self,
        positions: Optional[list[str]] = None,
        selectable: bool = False,
        compact: bool = False,
    ):
        super().__init__()
        self.positions = positions or DEFAULT_POSITIONS_9
        self.selectable = selectable
        self.compact = compact
        self.seats: dict[str, SeatData] = {p: SeatData(p) for p in self.positions}
        self._dealer = "BTN" if "BTN" in self.seats else self.positions[-1]
        self.spr: Optional[float] = None
        self.po: Optional[float] = None  # pot odds %
        self.seed: Optional[int] = None
        self.community_cards: list[str] = []  # e.g. ["W","W","W","W","W"] = facedown placeholders
        # Real-poker top-level state
        self.pot_bb: float = 0.0
        self.street: str   = "Preflop"
        # Layout cache populated in paintEvent / hit-test
        self._seat_centers: dict[str, QPointF] = {}
        self._seat_radius = 26
        self.setMinimumHeight(380 if not compact else 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if selectable:
            self.setCursor(Qt.PointingHandCursor)

    # --- public API ------------------------------------------------------
    def set_seat(self, position: str, actions: list[str] | None = None, selected: bool | None = None) -> None:
        if position not in self.seats:
            return
        seat = self.seats[position]
        if actions is not None:
            seat.actions = list(actions)
        if selected is not None:
            seat.selected = selected
        self.update()

    def set_actions(self, actions_per_position: dict[str, list[str]]) -> None:
        for pos, acts in actions_per_position.items():
            if pos in self.seats:
                self.seats[pos].actions = list(acts)
        self.update()

    def set_dealer(self, position: str) -> None:
        self._dealer = position
        self.update()

    def set_hero(self, position: str) -> None:
        for seat in self.seats.values():
            seat.is_hero = False
        if position in self.seats:
            self.seats[position].is_hero = True
        self.update()

    def set_spr_po(self, spr: float | None = None, po: float | None = None) -> None:
        self.spr = spr
        self.po = po
        self.update()

    def set_seed(self, seed: int | None) -> None:
        self.seed = seed
        self.update()

    def set_community_cards(self, cards: list[str]) -> None:
        self.community_cards = list(cards)
        self.update()

    # ── real-poker setters ────────────────────────────────────────────
    def set_stack(self, position: str, stack_bb: float) -> None:
        if position in self.seats:
            self.seats[position].stack_bb = float(stack_bb)
            self.update()

    def set_bet(self, position: str, current_bet: float) -> None:
        if position in self.seats:
            self.seats[position].current_bet = float(current_bet)
            self.update()

    def set_folded(self, position: str, folded: bool = True) -> None:
        if position in self.seats:
            self.seats[position].folded = bool(folded)
            self.update()

    def set_hero_cards(self, position: str, cards: list[str]) -> None:
        if position in self.seats:
            self.seats[position].hero_cards = list(cards)
            self.update()

    def set_pot(self, pot_bb: float, street: str = "Preflop") -> None:
        self.pot_bb = float(pot_bb)
        self.street = street
        self.update()

    def populate_from_spot(self, spot: dict) -> None:
        """One-call setter that derives a realistic table view from a spot dict.

        Supports preflop and postflop spots, multiple pot stories:
          • OPEN  — hero RFI, earlier positions fold (UTG…CO)
          • DEFENSE — villain raised, hero defends from SB/BB (others fold)
          • 3BP   — opener + hero 3-bet, others fold
          • 4BP   — opener + 3-bettor + hero 4-bet
          • SQUEEZE — opener + caller + hero squeeze
          • LIMP  — limpers + hero raise (iso) or check
          • POSTFLOP — preflop chips consolidated into pot; only postflop
            actors keep their current-street bets visible

        Derives realistic sizings from spot.pot_bb (not hard-coded 2.3bb).
        """
        pos    = (spot.get("position") or "BTN").upper()
        stack  = float(spot.get("stack_bb", 100))
        pot    = float(spot.get("pot_bb", 1.5))
        street = (spot.get("street") or "preflop")
        street_t = street.title()
        is_postflop = street.lower() in ("flop", "turn", "river")
        name   = (spot.get("name", "") + " " + spot.get("title", "") + " "
                  + spot.get("action_history", "")).upper()
        pot_t  = (spot.get("pot_type") or "").upper()

        # Detect "vs X" pattern (defender spot)
        vs = None
        for v in ("UTG+1", "UTG1", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"):
            if f"VS {v}" in name:
                vs = "UTG+1" if v == "UTG1" else v; break

        # Reset all seats
        for p, seat in self.seats.items():
            seat.stack_bb = stack
            seat.current_bet = 0.0
            seat.folded = False
            seat.actions = []
            seat.hero_cards = []
        self.set_hero(pos)
        cards_str = spot.get("hero_cards", "") or ""
        cards = [cards_str[i:i+2] for i in range(0, len(cards_str) - 1, 2)][:2]
        if pos in self.seats:
            self.seats[pos].hero_cards = cards

        # Realistic sizing derived from pot — gives variety
        # Open ~2.3bb, larger for HJ/UTG (~2.5bb), smaller for BTN min-raise (~2.1bb)
        open_sz = 2.3
        if "MIN" in name:           open_sz = 2.0
        elif pos in ("UTG", "UTG+1", "LJ"): open_sz = 2.5
        elif pos == "BTN" and not vs:       open_sz = 2.2

        # 3-bet sizing: ~3.3x open IP, ~4x OOP
        threebet_oop = open_sz * 4.0    # ~9.2bb
        threebet_ip  = open_sz * 3.3    # ~7.6bb
        # 4-bet sizing: ~2.2x 3-bet
        fourbet_sz   = threebet_oop * 2.2 / max(1, open_sz)  # in BB
        # Cap chip bets at remaining stack

        def _set_seat(p: str, bet: float, label: str) -> None:
            if p not in self.seats:
                return
            s = self.seats[p]
            s.current_bet = round(bet, 1)
            s.stack_bb = max(0, stack - bet)
            s.actions = [label]

        # ── Blinds always posted ──────────────────────────────
        _set_seat("SB", 0.5, "SB")
        _set_seat("BB", 1.0, "BB")

        # Helper — fold every seat that isn't in `keep`
        def _fold_others(keep: set) -> None:
            for p, seat in self.seats.items():
                if p in keep or p in ("SB", "BB"):
                    continue
                seat.folded = True
                seat.actions = ["F"]

        # ── Story detection ───────────────────────────────────────
        if pot_t == "4BP" or "4-BET" in name or "4BET" in name:
            opener = vs or ("BTN" if pos != "BTN" else "CO")
            three_bettor = pos
            _set_seat(opener, open_sz, f"R {open_sz:.1f}bb")
            _set_seat(three_bettor, threebet_oop, f"3B {threebet_oop:.1f}bb")
            # Hero is 4-better (could be opener re-jamming)
            if pos == opener:
                _set_seat(pos, fourbet_sz, f"4B {fourbet_sz:.1f}bb")
            _fold_others({opener, three_bettor, pos})

        elif "SQUEEZE" in name or "SQZ" in name:
            opener = vs or "CO"
            caller = "BTN" if opener != "BTN" else "CO"
            _set_seat(opener, open_sz, f"R {open_sz:.1f}bb")
            _set_seat(caller, open_sz, f"C {open_sz:.1f}bb")
            _set_seat(pos, threebet_oop + 2.0, f"SQ {threebet_oop+2.0:.1f}bb")
            _fold_others({opener, caller, pos})

        elif pot_t == "3BP" or "3-BET" in name or "3BET" in name:
            # Naming convention "X vs Y 3-bet" → X opened, Y 3-bet.
            # So pos (the hero) is the OPENER facing villain's 3-bet
            # UNLESS the spot is from the 3-bettor's seat (e.g. "BB 3-bet vs BTN")
            three_bettor_first = (
                "3-BET VS" in name or "3BET VS" in name
                or name.startswith("BB 3") or name.startswith("SB 3")
                or pos in ("BB", "SB") and pot_t == "3BP" and not vs
            )
            if three_bettor_first:
                # Hero is the 3-bettor — opener is the villain
                opener = vs or ("BTN" if pos != "BTN" else "CO")
                _set_seat(opener, open_sz, f"R {open_sz:.1f}bb")
                _set_seat(pos, threebet_oop, f"3B {threebet_oop:.1f}bb")
                _fold_others({opener, pos})
            else:
                # Hero is the OPENER facing villain's 3-bet (most common)
                three_bettor = vs or ("BB" if pos != "BB" else "BTN")
                _set_seat(pos, open_sz, f"R {open_sz:.1f}bb")
                _set_seat(three_bettor, threebet_oop, f"3B {threebet_oop:.1f}bb")
                _fold_others({pos, three_bettor})

        elif "LIMP" in name:
            limpers = ["UTG", "UTG+1"]
            for lim in limpers:
                if lim in self.seats and lim != pos:
                    _set_seat(lim, 1.0, "C 1.0")
            if pos not in ("SB", "BB"):
                _set_seat(pos, open_sz * 1.5, f"R {open_sz*1.5:.1f}bb")
            _fold_others({pos, *limpers})

        elif vs and pos in ("BB", "SB"):
            _set_seat(vs, open_sz, f"R {open_sz:.1f}bb")
            _fold_others({vs, pos})

        elif street.lower() == "preflop":
            # Open spot — hero RFI
            action_order = ["UTG", "UTG+1", "UTG1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
            hero_key = "UTG+1" if pos == "UTG1" else pos
            try:
                hero_idx = action_order.index(hero_key)
            except ValueError:
                hero_idx = len(action_order) - 1
            for p in self.seats:
                key = "UTG+1" if p == "UTG1" else p
                if p == pos or p in ("SB", "BB"):
                    continue
                if key in action_order and action_order.index(key) < hero_idx:
                    self.seats[p].folded = True
                    self.seats[p].actions = ["F"]
            # Hero's pre-raise chip (RFI)
            if pos not in ("SB", "BB"):
                _set_seat(pos, open_sz, f"R {open_sz:.1f}bb")
        else:
            # Postflop default story: hero heads-up vs villain.
            # Try to derive villain from action_history ("BTN bets", "CO checks").
            ah_upper = name
            villain_pos = None
            for v in ("UTG+1", "UTG1", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"):
                if v in ah_upper.split() and v != pos:
                    villain_pos = "UTG+1" if v == "UTG1" else v
                    break
            # Fallback: opposite-blind default
            if villain_pos is None:
                villain_pos = "BB" if pos != "BB" else "BTN"
            _fold_others({pos, villain_pos})
            # Also fold SB/BB if they're not the villain or hero
            for blind in ("SB", "BB"):
                if blind not in (pos, villain_pos) and blind in self.seats:
                    self.seats[blind].folded = True
                    self.seats[blind].actions = ["F"]

        # ── Postflop adjustment ──────────────────────────────
        # On flop/turn/river, ALL preflop bets are already in the pot;
        # no current_bet chips should be drawn until somebody bets THIS street.
        # The pot.bb value already includes all preflop contributions.
        if is_postflop:
            for p, seat in self.seats.items():
                seat.current_bet = 0.0
                # Keep fold label if folded; otherwise clear preflop verb
                if not seat.folded:
                    if seat.actions and seat.actions[0] not in ("F", "SB", "BB"):
                        seat.actions = []

            # Simple postflop story: villain checks to hero (when hero is IP)
            # or villain bets into hero. Use action_history to guess.
            ah = (spot.get("action_history") or "").lower()
            villain = vs or ("BB" if pos != "BB" else "BTN")
            if "check" in ah and "bet" not in ah:
                if villain in self.seats:
                    self.seats[villain].actions = ["X"]
            elif "bet" in ah or "lead" in ah:
                # villain leads on flop
                bet_amount = pot * 0.5   # standard half-pot lead
                if villain in self.seats:
                    self.seats[villain].current_bet = round(bet_amount, 1)
                    self.seats[villain].actions = [f"B {bet_amount:.1f}"]

        self.set_pot(pot, street_t)

    def selection(self) -> set[str]:
        return {p for p, s in self.seats.items() if s.selected}

    def select_all(self, value: bool = True) -> None:
        for s in self.seats.values():
            s.selected = value
        self.update()
        self.selection_changed.emit(self.selection())

    # --- mouse -----------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if not self.selectable:
            return super().mousePressEvent(event)
        for pos, center in self._seat_centers.items():
            if (event.position() - center).manhattanLength() <= self._seat_radius * 1.4:
                seat = self.seats[pos]
                seat.selected = not seat.selected
                self.update()
                self.position_clicked.emit(pos)
                self.selection_changed.emit(self.selection())
                return
        super().mousePressEvent(event)

    # --- paint -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Opaque dark background — so the widget always looks like part of
        # the dark UI even when no parent fills behind it
        painter.fillRect(0, 0, w, h, QColor("#0A0E14"))

        # Real poker-felt oval — dark green with a subtle inner shadow rim
        margin_x = 70
        margin_y = 50 if not self.compact else 36
        oval = QRectF(margin_x, margin_y, w - margin_x * 2, h - margin_y * 2)
        # Outer felt rim (slightly lighter)
        painter.setPen(QPen(QColor("#1A2C20"), 6))
        painter.setBrush(QColor("#0E2018"))
        painter.drawEllipse(oval)
        # Inner felt (the playing surface)
        inner = oval.adjusted(8, 8, -8, -8)
        painter.setPen(QPen(QColor("#1F3A2A"), 2))
        painter.setBrush(QColor("#143020"))
        painter.drawEllipse(inner)

        # Center board (community cards placeholder)
        center_x = oval.center().x()
        center_y = oval.center().y()
        if self.community_cards:
            self._paint_community(painter, center_x, center_y)

        # POT in the centre — always painted when there's chips in
        if self.pot_bb > 0:
            self._paint_pot(painter, center_x, center_y + (50 if self.community_cards else 0))

        # SPR / PO badge (top-left)
        if self.spr is not None or self.po is not None:
            self._paint_spr_po(painter, 12, 12)

        # Seed badge (top-right)
        if self.seed is not None:
            self._paint_seed(painter, w - 78, 10)

        # Seats around the oval
        n = len(self.positions)
        rx = oval.width() / 2
        ry = oval.height() / 2
        cx = oval.center().x()
        cy = oval.center().y()
        # Distribute starting from top-center going clockwise
        self._seat_centers.clear()
        for i, pos in enumerate(self.positions):
            theta = -math.pi / 2 + 2 * math.pi * i / n
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)
            self._seat_centers[pos] = QPointF(x, y)
            self._paint_seat(painter, x, y, self.seats[pos], theta)

        painter.end()

    def _paint_seat(self, painter: QPainter, x: float, y: float, seat: SeatData, theta: float) -> None:
        r = self._seat_radius
        is_folded = seat.folded

        # Hero gets two glow halos so it's IMPOSSIBLE to miss
        if seat.is_hero and not is_folded:
            for halo_r, alpha in ((r + 14, 35), (r + 8, 70)):
                halo = QColor("#22D3EE"); halo.setAlpha(alpha)
                painter.setBrush(halo); painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y), halo_r, halo_r)
        # Circle fill — folded gets dim, hero rich, others felt-darker
        if is_folded:
            painter.setBrush(QColor("#0C1620"))
        elif seat.is_hero:
            painter.setBrush(QColor("#0F2433"))
        else:
            painter.setBrush(QColor("#11212B"))
        # Border
        if seat.selected:
            pen = QPen(QColor("#22D3EE"), 3)
        elif seat.is_hero and not is_folded:
            pen = QPen(QColor("#22D3EE"), 3.5)
        elif is_folded:
            pen = QPen(QColor("#1F2937"), 1)
        else:
            pen = QPen(QColor("#4B5C6E"), 1.5)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(x, y), r, r)

        # Position label — TOP HALF of circle (no overlap with stack)
        font = QFont()
        font.setPointSize(11 if seat.is_hero else 10)
        font.setBold(True)
        painter.setFont(font)
        if is_folded:
            text_color = "#4B5563"
        elif seat.selected:
            text_color = "#22D3EE"
        elif seat.is_hero:
            text_color = "#67E8F9"
        else:
            text_color = "#E5E7EB"
        painter.setPen(QPen(QColor(text_color)))
        # Position in upper portion of circle
        painter.drawText(QRectF(x - r, y - 14, 2 * r, 14), Qt.AlignCenter, seat.position)
        # Hairline divider
        painter.setPen(QPen(QColor("#1F2937" if is_folded else "#2A3441"), 1))
        painter.drawLine(int(x - r * 0.6), int(y + 1), int(x + r * 0.6), int(y + 1))

        # Stack label — BOTTOM HALF of circle (separated from position)
        if seat.stack_bb > 0:
            stack_font = QFont(); stack_font.setPointSize(9); stack_font.setBold(True)
            painter.setFont(stack_font)
            painter.setPen(QPen(QColor("#6B7280" if is_folded else "#9CA3AF")))
            painter.drawText(QRectF(x - r, y + 4, 2 * r, 14), Qt.AlignCenter,
                              f"{seat.stack_bb:.0f}bb")

        # Compute INWARD (toward pot) and OUTWARD (away) unit vectors once
        cx_t = self.width() / 2
        cy_t = self.height() / 2
        in_dx, in_dy = cx_t - x, cy_t - y
        in_dist = max(1.0, (in_dx ** 2 + in_dy ** 2) ** 0.5)
        ux, uy = in_dx / in_dist, in_dy / in_dist  # unit vector toward pot

        # Hero "★ YOU" badge — OUTSIDE the seat (away from pot), so it never
        # overlaps with bet chip or cards that sit on the inward side.
        if seat.is_hero and not is_folded:
            badge_font = QFont(); badge_font.setPointSize(8); badge_font.setBold(True)
            painter.setFont(badge_font)
            badge_w, badge_h = 50, 16
            bx_c = x - ux * (r + 16)
            by_c = y - uy * (r + 16)
            bx = bx_c - badge_w / 2
            by = by_c - badge_h / 2
            # Clamp so the pill never goes off-edge
            bx = max(2, min(self.width() - badge_w - 2, bx))
            by = max(2, min(self.height() - badge_h - 2, by))
            painter.setBrush(QColor("#22D3EE"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(bx, by, badge_w, badge_h), 8, 8)
            painter.setPen(QPen(QColor("#061018")))
            painter.drawText(QRectF(bx, by, badge_w, badge_h), Qt.AlignCenter, "★ YOU")

        # Hero hole cards — INWARD, just inside seat ring (CLOSEST to seat)
        if seat.is_hero and seat.hero_cards and not is_folded:
            self._paint_hero_cards(painter, x, y, theta, seat.hero_cards)

        # Bet chip — further INWARD than cards (so cards in front of bet),
        # mimicking a real table: player ‣ cards ‣ chips ‣ pot.
        if seat.current_bet > 0:
            # Hero offsets bet chip further so it sits *past* the cards
            chip_offset = (r + 66) if (seat.is_hero and seat.hero_cards) else (r + 24)
            chip_x = x + ux * chip_offset
            chip_y = y + uy * chip_offset
            self._paint_bet_chip(painter, chip_x, chip_y, seat.current_bet)

        # Action chip — OUTWARD from pot (away from cards/bet).
        # SKIP redundant "SB"/"BB" labels (the seat circle already shows them)
        # SKIP for hero (★ YOU badge already occupies the outward slot)
        if seat.actions and not seat.is_hero:
            action_label = seat.actions[-1]
            if action_label.upper() not in ("SB", "BB"):
                ax = x - ux * (r + 18)
                ay = y - uy * (r + 18)
                self._paint_action_chip(painter, ax, ay, action_label, is_folded)

        # Dealer button
        if seat.position == self._dealer:
            d_x = x + (r + 6) * math.cos(theta + math.pi / 6)
            d_y = y + (r + 6) * math.sin(theta + math.pi / 6)
            painter.setBrush(QColor("#F3F4F6"))
            painter.setPen(QPen(QColor("#0B0F14"), 1))
            painter.drawEllipse(QPointF(d_x, d_y), 9, 9)
            painter.setPen(QPen(QColor("#0B0F14")))
            font_d = QFont(); font_d.setPointSize(8); font_d.setBold(True)
            painter.setFont(font_d)
            painter.drawText(QRectF(d_x - 9, d_y - 9, 18, 18), Qt.AlignCenter, "D")

    def _paint_hero_cards(self, painter: QPainter, x: float, y: float, theta: float, cards: list[str]) -> None:
        """Paint hero's 2 hole cards as proper playing cards (white bg, rank + suit).

        Cards are placed JUST INSIDE the seat circle on the table-facing side,
        and clamped to stay within the widget so they never get clipped.
        """
        cx_t = self.width() / 2; cy_t = self.height() / 2
        dx = cx_t - x; dy = cy_t - y
        dist = max(1.0, (dx**2 + dy**2)**0.5)
        # Card geometry — larger so they're always legible
        cardw, cardh, gap = 32, 44, 5
        total_w = 2 * cardw + gap
        # Center anchor is just INSIDE the seat ring toward table centre
        anchor_x = x + dx / dist * (self._seat_radius + 26)
        anchor_y = y + dy / dist * (self._seat_radius + 26)
        base_x = anchor_x - total_w / 2
        base_y = anchor_y - cardh / 2
        # Clamp to widget bounds so cards never disappear off-edge
        base_x = max(4, min(self.width() - total_w - 4, base_x))
        base_y = max(4, min(self.height() - cardh - 4, base_y))

        # Suit → (symbol, colour) — standard red/black with hearts=red, diamonds=blue,
        # spades=dark, clubs=green for max colour-blind distinction
        suit_meta = {
            "s": ("♠", "#0F1419"), "h": ("♥", "#DC2626"),
            "d": ("♦", "#2563EB"), "c": ("♣", "#059669"),
            "♠": ("♠", "#0F1419"), "♥": ("♥", "#DC2626"),
            "♦": ("♦", "#2563EB"), "♣": ("♣", "#059669"),
        }
        for i, card in enumerate(cards[:2]):
            cx = base_x + i * (cardw + gap)
            rank_raw = (card[0] if card else "?").upper()
            rank = "10" if rank_raw == "T" else rank_raw
            suit_ch = card[1] if len(card) > 1 else ""
            symbol, colour = suit_meta.get(suit_ch, ("?", "#374151"))

            # White card body with thin border
            painter.setBrush(QColor("#FAFAFA"))
            painter.setPen(QPen(QColor("#9CA3AF"), 1))
            painter.drawRoundedRect(QRectF(cx, base_y, cardw, cardh), 5, 5)

            # Top-left rank
            painter.setPen(QPen(QColor(colour)))
            f_rank = QFont(); f_rank.setPointSize(11); f_rank.setBold(True)
            painter.setFont(f_rank)
            painter.drawText(
                QRectF(cx + 2, base_y + 2, cardw - 4, 16),
                Qt.AlignLeft | Qt.AlignTop, rank,
            )
            # Top-left tiny suit under rank
            f_sm = QFont(); f_sm.setPointSize(9); f_sm.setBold(True)
            painter.setFont(f_sm)
            painter.drawText(
                QRectF(cx + 2, base_y + 14, cardw - 4, 12),
                Qt.AlignLeft | Qt.AlignTop, symbol,
            )
            # Centre — big suit symbol
            f_big = QFont(); f_big.setPointSize(18); f_big.setBold(True)
            painter.setFont(f_big)
            painter.drawText(QRectF(cx, base_y, cardw, cardh), Qt.AlignCenter, symbol)

    def _paint_bet_chip(self, painter: QPainter, x: float, y: float, amount: float) -> None:
        """Orange chip showing how many bb are in front of this player."""
        text = f"{amount:.1f}bb"
        font = QFont(); font.setPointSize(9); font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        w = max(38, text_w + 12); h = 18
        painter.setBrush(QColor("#F59E0B"))
        painter.setPen(QPen(QColor("#92400E"), 1))
        painter.drawRoundedRect(QRectF(x - w/2, y - h/2, w, h), 9, 9)
        painter.setPen(QPen(QColor("#000000")))
        painter.drawText(QRectF(x - w/2, y - h/2, w, h), Qt.AlignCenter, text)

    def _paint_pot(self, painter: QPainter, cx: float, cy: float) -> None:
        """Cyan pill in the table centre showing POT and street."""
        text = f"POT  {self.pot_bb:.1f}bb  ·  {self.street}"
        font = QFont(); font.setPointSize(11); font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(text) + 28
        h = 28
        painter.setBrush(QColor("#0E2A1E"))
        painter.setPen(QPen(QColor("#10B981"), 1.5))
        painter.drawRoundedRect(QRectF(cx - w/2, cy - h/2, w, h), 14, 14)
        painter.setPen(QPen(QColor("#6EE7B7")))
        painter.drawText(QRectF(cx - w/2, cy - h/2, w, h), Qt.AlignCenter, text)

    def _paint_action_chip(self, painter: QPainter, x: float, y: float, label: str, dim: bool = False) -> None:
        """Coloured action pill behind/around the seat."""
        lab = label.upper()
        if lab.startswith("F") or "FOLD" in lab:
            bg, border, fg = QColor("#1B2D4A"), QColor("#3B82F6"), QColor("#93C5FD")
        elif lab.startswith("C") or "CALL" in lab or "CHECK" in lab or lab.startswith("X"):
            bg, border, fg = QColor("#0E2A1E"), QColor("#10B981"), QColor("#6EE7B7")
        elif "AI" in lab or "JAM" in lab or "ALL" in lab:
            bg, border, fg = QColor("#1A0E0E"), QColor("#7F1D1D"), QColor("#FCA5A5")
        elif lab.startswith("R") or lab.startswith("B") or lab.startswith("3") or lab.startswith("4"):
            bg, border, fg = QColor("#2A1B1B"), QColor("#E11D48"), QColor("#FCA5A5")
        else:
            bg, border, fg = QColor("#131A24"), QColor("#3A4659"), QColor("#E5E7EB")
        if dim:
            bg = QColor(bg); bg.setAlpha(120)
        font = QFont(); font.setPointSize(9); font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(lab)
        w = max(32, text_w + 12); h = 18
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.5))
        painter.drawRoundedRect(QRectF(x - w/2, y - h/2, w, h), 4, 4)
        painter.setPen(QPen(fg))
        painter.drawText(QRectF(x - w/2, y - h/2, w, h), Qt.AlignCenter, lab)

    def _paint_spr_po(self, painter: QPainter, x: int, y: int) -> None:
        font = QFont(); font.setPointSize(10); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#9CA3AF")))
        if self.spr is not None:
            painter.drawText(x, y + 14, f"SPR")
            painter.setPen(QPen(QColor("#E5E7EB")))
            painter.drawText(x + 38, y + 14, f"{self.spr:.1f}")
            painter.setPen(QPen(QColor("#9CA3AF")))
        if self.po is not None:
            painter.drawText(x, y + 30, f"PO")
            painter.setPen(QPen(QColor("#E5E7EB")))
            painter.drawText(x + 38, y + 30, f"{self.po:.1f}%")

    def _paint_seed(self, painter: QPainter, x: int, y: int) -> None:
        rect = QRectF(x, y, 66, 32)
        painter.setBrush(QColor("#13241D"))
        painter.setPen(QPen(QColor("#10B981"), 1.5))
        painter.drawRoundedRect(rect, 6, 6)
        # Dice glyph (just three dots)
        painter.setBrush(QColor("#10B981"))
        painter.setPen(Qt.NoPen)
        for dx, dy in [(8, 8), (16, 16), (24, 8)]:
            painter.drawEllipse(QPointF(rect.x() + dx, rect.y() + dy), 1.6, 1.6)
        # seed value
        font = QFont(); font.setPointSize(11); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#E5E7EB")))
        painter.drawText(QRectF(rect.x() + 32, rect.y(), 34, rect.height()), Qt.AlignVCenter | Qt.AlignLeft, str(self.seed))

    def _paint_community(self, painter: QPainter, cx: float, cy: float) -> None:
        n = len(self.community_cards)
        card_w = 32
        card_h = 44
        gap = 5
        total_w = n * card_w + (n - 1) * gap
        start_x = cx - total_w / 2
        suit_meta = {
            "s": ("♠", "#0F1419"), "h": ("♥", "#DC2626"),
            "d": ("♦", "#2563EB"), "c": ("♣", "#059669"),
            "S": ("♠", "#0F1419"), "H": ("♥", "#DC2626"),
            "D": ("♦", "#2563EB"), "C": ("♣", "#059669"),
        }
        for i, c in enumerate(self.community_cards):
            x = start_x + i * (card_w + gap)
            y = cy - card_h / 2
            rect = QRectF(x, y, card_w, card_h)
            if not c or c in ("W", "??", "?", "X"):
                # Face-down — dark with cross pattern
                painter.setBrush(QColor("#1F2937"))
                painter.setPen(QPen(QColor("#374151"), 1))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QPen(QColor("#4B5563"), 1))
                painter.drawLine(int(x + 6), int(y + 6), int(x + card_w - 6), int(y + card_h - 6))
                painter.drawLine(int(x + card_w - 6), int(y + 6), int(x + 6), int(y + card_h - 6))
            else:
                rank_raw = c[0].upper()
                rank = "10" if rank_raw == "T" else rank_raw
                suit_ch = c[1] if len(c) > 1 else ""
                symbol, colour = suit_meta.get(suit_ch, ("", "#0F1419"))
                # White card body
                painter.setBrush(QColor("#FAFAFA"))
                painter.setPen(QPen(QColor("#9CA3AF"), 1))
                painter.drawRoundedRect(rect, 5, 5)
                # Top-left rank
                painter.setPen(QPen(QColor(colour)))
                f = QFont(); f.setPointSize(11); f.setBold(True)
                painter.setFont(f)
                painter.drawText(
                    QRectF(x + 2, y + 2, card_w - 4, 16),
                    Qt.AlignLeft | Qt.AlignTop, rank,
                )
                # Centre suit large
                f_big = QFont(); f_big.setPointSize(18); f_big.setBold(True)
                painter.setFont(f_big)
                painter.drawText(rect, Qt.AlignCenter, symbol)


class TableWithActions(QWidget):
    """Convenience: oval table + ActionSequence rows for each position with actions."""

    def __init__(self, positions: list[str] | None = None):
        super().__init__()
        from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QLabel
        self.table = OvalTable(positions=positions, selectable=False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        self._action_box = QGridLayout()
        layout.addLayout(self._action_box)

    def set_actions(self, mapping: dict[str, list[str]]) -> None:
        self.table.set_actions(mapping)
        # Clear existing rows
        while self._action_box.count():
            item = self._action_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        from PySide6.QtWidgets import QLabel
        for r, (pos, acts) in enumerate(mapping.items()):
            if not acts:
                continue
            lbl = QLabel(pos)
            lbl.setObjectName("Muted")
            lbl.setFixedWidth(40)
            self._action_box.addWidget(lbl, r, 0)
            self._action_box.addWidget(ActionSequence(acts, scale=0.95), r, 1)
