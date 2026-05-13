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

        Reads:
          - spot.position           → hero seat (gets ★ YOU + cards)
          - spot.hero_cards         → 2-char per card, painted face up at hero
          - spot.stack_bb           → applied to every seat that isn't folded
          - spot.pot_bb             → centre pot
          - spot.name / pot_type    → derives who raised / folded so chips appear
        """
        pos    = (spot.get("position") or "BTN").upper()
        stack  = float(spot.get("stack_bb", 100))
        pot    = float(spot.get("pot_bb", 1.5))
        street = (spot.get("street") or "preflop").title()
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
        # Hero
        self.set_hero(pos)
        # Hero cards
        cards_str = spot.get("hero_cards", "") or ""
        cards = [cards_str[i:i+2] for i in range(0, len(cards_str) - 1, 2)][:2]
        if pos in self.seats:
            self.seats[pos].hero_cards = cards

        # Blinds
        if "SB" in self.seats:
            self.seats["SB"].current_bet = 0.5
            self.seats["SB"].stack_bb = stack - 0.5
            self.seats["SB"].actions = ["SB"]
        if "BB" in self.seats:
            self.seats["BB"].current_bet = 1.0
            self.seats["BB"].stack_bb = stack - 1.0
            self.seats["BB"].actions = ["BB"]

        # Story: 3-bet pot / vs-X defense / open spot
        if "3-BET" in name or pot_t == "3BP":
            opener = vs or "BTN"
            if opener in self.seats:
                self.seats[opener].current_bet = 2.3
                self.seats[opener].stack_bb = stack - 2.3
                self.seats[opener].actions = ["R 2.3"]
            if pos in self.seats:
                self.seats[pos].current_bet = 8.0
                self.seats[pos].stack_bb = stack - 8.0
                self.seats[pos].actions = ["3B 8"]
            for p, seat in self.seats.items():
                if p not in (opener, pos, "SB", "BB"):
                    seat.folded = True
                    seat.actions = ["F"]
        elif vs and pos in ("BB", "SB"):
            # Defense — villain raised, others folded
            if vs in self.seats:
                self.seats[vs].current_bet = 2.3
                self.seats[vs].stack_bb = stack - 2.3
                self.seats[vs].actions = ["R 2.3"]
            for p, seat in self.seats.items():
                if p not in (vs, pos, "SB", "BB"):
                    seat.folded = True
                    seat.actions = ["F"]
            if pos == "BB" and vs != "SB" and "SB" in self.seats:
                self.seats["SB"].folded = True
                self.seats["SB"].actions = ["F"]
        elif (spot.get("street") or "preflop").lower() == "preflop":
            # Open spot — hero RFI, earlier positions fold
            order = list(self.positions)
            try: hero_idx = order.index(pos)
            except ValueError: hero_idx = len(order) - 1
            for p in order:
                if p == pos or p in ("SB", "BB"):
                    continue
                if order.index(p) < hero_idx:
                    self.seats[p].folded = True
                    self.seats[p].actions = ["F"]

        self.set_pot(pot, street)

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

        # Outer oval (subtle felt suggestion, mostly invisible)
        margin_x = 90
        margin_y = 60 if not self.compact else 40
        oval = QRectF(margin_x, margin_y, w - margin_x * 2, h - margin_y * 2)
        painter.setPen(QPen(QColor("#1E2733"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(oval)

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
                halo = QColor("#10B981"); halo.setAlpha(alpha)
                painter.setBrush(halo); painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y), halo_r, halo_r)
        # Circle fill — folded gets dim, hero rich green
        if is_folded:
            painter.setBrush(QColor("#080B10"))
        elif seat.is_hero:
            painter.setBrush(QColor("#0F2A1E"))
        else:
            painter.setBrush(QColor("#0E141C"))
        # Border
        if seat.selected:
            pen = QPen(QColor("#22D3EE"), 3)
        elif seat.is_hero and not is_folded:
            pen = QPen(QColor("#10B981"), 3.5)
        elif is_folded:
            pen = QPen(QColor("#1F2937"), 1)
        else:
            pen = QPen(QColor("#3A4659"), 1.5)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(x, y), r, r)

        # Position label
        font = QFont()
        font.setPointSize(12 if seat.is_hero else 11)
        font.setBold(True)
        painter.setFont(font)
        if is_folded:
            text_color = "#4B5563"
        elif seat.selected:
            text_color = "#22D3EE"
        elif seat.is_hero:
            text_color = "#10B981"
        else:
            text_color = "#E5E7EB"
        painter.setPen(QPen(QColor(text_color)))
        painter.drawText(QRectF(x - r, y - 16, 2 * r, 18), Qt.AlignCenter, seat.position)

        # Stack label INSIDE the seat circle (so you always see chip count)
        if seat.stack_bb > 0:
            stack_font = QFont(); stack_font.setPointSize(10); stack_font.setBold(True)
            painter.setFont(stack_font)
            painter.setPen(QPen(QColor("#4B5563" if is_folded else "#E5E7EB")))
            painter.drawText(QRectF(x - r, y + 2, 2 * r, 16), Qt.AlignCenter,
                              f"{seat.stack_bb:.1f}bb")

        # Hero "★ YOU" badge below position (only when not folded)
        if seat.is_hero and not is_folded:
            badge_font = QFont(); badge_font.setPointSize(8); badge_font.setBold(True)
            painter.setFont(badge_font)
            painter.setPen(QPen(QColor("#6EE7B7")))
            painter.drawText(QRectF(x - r, y - 28, 2 * r, 14), Qt.AlignCenter, "★ YOU")

        # Hero hole cards — painted just OUTSIDE the seat in the direction of centre
        if seat.is_hero and seat.hero_cards and not is_folded:
            self._paint_hero_cards(painter, x, y, theta, seat.hero_cards)

        # Bet chip — painted between seat and table center, showing current_bet
        if seat.current_bet > 0:
            cx_table = self.width() / 2
            cy_table = self.height() / 2
            dir_x = cx_table - x; dir_y = cy_table - y
            dist = max(1.0, (dir_x ** 2 + dir_y ** 2) ** 0.5)
            chip_x = x + dir_x / dist * (r + 22)
            chip_y = y + dir_y / dist * (r + 22)
            self._paint_bet_chip(painter, chip_x, chip_y, seat.current_bet)

        # Action chip — painted on the OUTSIDE of the seat (away from centre)
        if seat.actions:
            action_label = seat.actions[-1]
            cx_table = self.width() / 2
            cy_table = self.height() / 2
            dir_x = x - cx_table; dir_y = y - cy_table
            dist = max(1.0, (dir_x ** 2 + dir_y ** 2) ** 0.5)
            ax = x + dir_x / dist * (r + 22)
            ay = y + dir_y / dist * (r + 22)
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
        """Paint hero's 2 hole cards on the table-facing side of the hero seat."""
        # Position cards just inward of the seat
        cx_t = self.width() / 2; cy_t = self.height() / 2
        dx = cx_t - x; dy = cy_t - y
        dist = max(1.0, (dx**2 + dy**2)**0.5)
        cardw, cardh = 26, 36
        base_x = x + dx / dist * (self._seat_radius + 16) - cardw - 3
        base_y = y + dy / dist * (self._seat_radius + 16) - cardh / 2
        suit_bg = {"s": QColor("#0F1419"), "h": QColor("#7F1D1D"),
                   "d": QColor("#1E3A8A"), "c": QColor("#064E3B"),
                   "♠": QColor("#0F1419"), "♥": QColor("#7F1D1D"),
                   "♦": QColor("#1E3A8A"), "♣": QColor("#064E3B")}
        for i, card in enumerate(cards[:2]):
            cx = base_x + i * (cardw + 4)
            rank = card[0] if card else "?"
            suit_ch = card[1] if len(card) > 1 else ""
            bg = suit_bg.get(suit_ch, QColor("#1F2937"))
            painter.setBrush(bg)
            painter.setPen(QPen(QColor("#E5E7EB"), 1))
            painter.drawRoundedRect(QRectF(cx, base_y, cardw, cardh), 4, 4)
            painter.setPen(QPen(QColor("#FFFFFF")))
            f = QFont(); f.setPointSize(13); f.setBold(True)
            painter.setFont(f)
            painter.drawText(QRectF(cx, base_y, cardw, cardh), Qt.AlignCenter, rank)

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
        card_w = 28
        card_h = 38
        gap = 4
        total_w = n * card_w + (n - 1) * gap
        start_x = cx - total_w / 2
        for i, c in enumerate(self.community_cards):
            x = start_x + i * (card_w + gap)
            y = cy - card_h / 2
            rect = QRectF(x, y, card_w, card_h)
            if c == "W" or not c:
                # Face-down
                painter.setBrush(QColor("#1B2330"))
                painter.setPen(QPen(QColor("#2A3647"), 1))
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QPen(QColor("#4B5563")))
                font = QFont(); font.setPointSize(13); font.setBold(True)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignCenter, "W")
            else:
                painter.setBrush(QColor("#0E141C"))
                painter.setPen(QPen(QColor("#2A3647"), 1))
                painter.drawRoundedRect(rect, 4, 4)
                rank = c[0] if c else "?"
                suit = c[1] if len(c) > 1 else ""
                color = "#22D3EE" if suit in ("h", "H") else "#10B981" if suit in ("s", "S") else "#F59E0B" if suit in ("d", "D") else "#EF4444"
                painter.setPen(QPen(QColor(color)))
                font = QFont(); font.setPointSize(13); font.setBold(True)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignCenter, rank)


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
