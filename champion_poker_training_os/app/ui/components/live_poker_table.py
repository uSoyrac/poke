"""LivePokerTable — visual oval table for active poker hands (2-11 seats).

Shows every seat with:
  - Position label (SB / BB / UTG / ... / BTN)
  - Stack and current bet
  - Hole card backs (or face-up for hero)
  - Acted/folded/all-in state
  - Dealer button marker
  - Active-to-act ring
  - Per-action chip (latest action: F/X/C/B/R/AI)

The widget consumes a HandState snapshot via update_state(hand). Pure paint —
no signals back to the engine.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


# Action -> short code + color (mirrors ActionChip palette)
ACTION_VISUALS = {
    "fold": ("F", "#5BA9F0", "#1B3A5C"),
    "check": ("X", "#3DD37C", "#1F3D24"),
    "call": ("C", "#3DD37C", "#1F3D24"),
    "bet": ("B", "#F87171", "#5C1F22"),
    "raise": ("R", "#F87171", "#5C1F22"),
    "all_in": ("AI", "#FCA5A5", "#3D0E10"),
    "all-in": ("AI", "#FCA5A5", "#3D0E10"),
    "post": ("$", "#9CA3AF", "#2A2F3A"),
}


class LivePokerTable(QWidget):
    """2-11 seat oval table renderer."""

    def __init__(self):
        super().__init__()
        self.num_players = 0
        self.dealer_idx = 0
        self.hero_idx = 0
        self.active_idx: Optional[int] = None
        self.players_data: list[dict] = []
        self.community_cards: list[str] = []
        self.pot_bb: float = 0.0
        self.street: str = "Preflop"
        self.setMinimumHeight(420)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # --- public update API ----------------------------------------------
    def update_state(self, hand) -> None:
        """Snapshot a HandState into this widget. Tolerant of None / partial state."""
        if hand is None:
            self.num_players = 0
            self.players_data = []
            self.community_cards = []
            self.pot_bb = 0.0
            self.update()
            return
        self.num_players = len(hand.players)
        self.dealer_idx = hand.dealer_idx
        self.hero_idx = getattr(hand, "hero_idx", 0)
        self.active_idx = getattr(hand, "active_player_idx", None)
        self.community_cards = [c.display for c in (hand.community or [])]
        self.pot_bb = float(getattr(hand, "pot", 0.0))
        self.street = getattr(hand, "street_name", "Preflop")

        bb = max(1.0, getattr(hand, "big_blind", 1.0))
        self.players_data = []
        last_actions = self._latest_actions(hand)
        for i, p in enumerate(hand.players):
            self.players_data.append({
                "name": p.name,
                "position": p.position or "",
                "stack_bb": p.stack / bb,
                "current_bet_bb": p.current_bet / bb,
                "hole_cards": [c.display for c in (p.hole_cards or [])] if p.is_hero else None,
                "is_hero": p.is_hero,
                "is_folded": p.is_folded,
                "is_all_in": p.is_all_in,
                "last_action": last_actions.get(i),
            })
        self.update()

    @staticmethod
    def _latest_actions(hand) -> dict[int, str]:
        """Walk hand.actions (if available) and return seat_idx -> last action verb."""
        out: dict[int, str] = {}
        actions = getattr(hand, "actions", None) or []
        for a in actions:
            seat = getattr(a, "player_idx", None) or getattr(a, "seat_idx", None)
            verb = None
            atype = getattr(a, "action_type", None)
            if atype is not None:
                verb = getattr(atype, "value", str(atype))
            if seat is not None and verb:
                out[seat] = verb
        return out

    # --- paint -----------------------------------------------------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Felt: subtle dark oval
        margin_x = 100
        margin_y = 70
        oval = QRectF(margin_x, margin_y, w - margin_x * 2, h - margin_y * 2)
        painter.setPen(QPen(QColor("#1E2733"), 2))
        painter.setBrush(QColor("#0E1B17"))
        painter.drawEllipse(oval)

        # Pot + street center
        cx = oval.center().x()
        cy = oval.center().y()
        if self.community_cards:
            self._paint_community(painter, cx, cy - 10)
        self._paint_pot(painter, cx, cy + 32)

        if self.num_players == 0:
            painter.setPen(QColor("#9CA3AF"))
            font = QFont(); font.setPointSize(13); painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignCenter, "No active hand. Click 'Deal' to start.")
            painter.end()
            return

        # Place seats around the oval
        rx = oval.width() / 2 + 30
        ry = oval.height() / 2 + 35
        for seat_idx, data in enumerate(self.players_data):
            # Hero is always at the bottom (180°). Other seats fan around.
            seat_offset = (seat_idx - self.hero_idx) % self.num_players
            theta = math.pi / 2 + 2 * math.pi * seat_offset / self.num_players
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)
            self._paint_seat(painter, x, y, data, seat_idx == self.dealer_idx,
                              seat_idx == self.active_idx)

        painter.end()

    def _paint_seat(self, painter: QPainter, x: float, y: float, data: dict,
                    is_dealer: bool, is_active: bool) -> None:
        """Render a single seat — circle + position + stack + current bet + last action chip."""
        r = 32
        seat_rect = QRectF(x - r, y - r, r * 2, r * 2)

        # Outer halo for active player
        if is_active:
            halo = QRectF(x - r - 5, y - r - 5, (r + 5) * 2, (r + 5) * 2)
            painter.setPen(QPen(QColor("#22D3EE"), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(halo)

        # Seat circle
        if data["is_folded"]:
            painter.setBrush(QColor("#0E141C"))
        elif data["is_all_in"]:
            painter.setBrush(QColor("#3D0E10"))
        elif data["is_hero"]:
            painter.setBrush(QColor("#0E2A1E"))
        else:
            painter.setBrush(QColor("#1B2330"))
        if data["is_hero"]:
            pen = QPen(QColor("#10B981"), 2)
        elif is_active:
            pen = QPen(QColor("#22D3EE"), 2)
        else:
            pen = QPen(QColor("#3A4659"), 1.5)
        painter.setPen(pen)
        painter.drawEllipse(seat_rect)

        # Position label centered
        label_color = "#4B5563" if data["is_folded"] else ("#10B981" if data["is_hero"] else "#E5E7EB")
        font = QFont(); font.setPointSize(11); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(label_color)))
        painter.drawText(seat_rect, Qt.AlignCenter, data["position"] or "?")

        # Stack + current bet below seat
        font_small = QFont(); font_small.setPointSize(9); font_small.setBold(True)
        painter.setFont(font_small)
        painter.setPen(QPen(QColor("#9CA3AF" if data["is_folded"] else "#E5E7EB")))
        info = f"{data['stack_bb']:.1f}bb"
        painter.drawText(QRectF(x - 50, y + r + 4, 100, 16), Qt.AlignCenter, info)

        if data["current_bet_bb"] > 0 and not data["is_folded"]:
            bet_rect = QRectF(x - 32, y + r + 22, 64, 18)
            painter.setBrush(QColor("#F59E0B"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bet_rect, 9, 9)
            painter.setPen(QPen(QColor("#0B0F14")))
            painter.drawText(bet_rect, Qt.AlignCenter, f"{data['current_bet_bb']:.1f}bb")

        # Hole cards: facedown for opponents (folded shown as 'X'), face-up for hero
        if data["is_hero"] and data.get("hole_cards"):
            self._paint_hole_cards(painter, x, y - r - 20, data["hole_cards"], face_up=True)
        elif not data["is_folded"] and not data["is_hero"]:
            # Facedown opponent cards
            self._paint_hole_cards(painter, x, y - r - 20, ["??", "??"], face_up=False)

        # Dealer button
        if is_dealer:
            d_off_x = r * 0.85
            d_off_y = -r * 0.85
            painter.setBrush(QColor("#F3F4F6"))
            painter.setPen(QPen(QColor("#0B0F14"), 1.5))
            painter.drawEllipse(QPointF(x + d_off_x, y + d_off_y), 11, 11)
            painter.setPen(QPen(QColor("#0B0F14")))
            font_d = QFont(); font_d.setPointSize(9); font_d.setBold(True)
            painter.setFont(font_d)
            painter.drawText(QRectF(x + d_off_x - 11, y + d_off_y - 11, 22, 22),
                             Qt.AlignCenter, "D")

        # Last action chip (right of seat)
        action = data.get("last_action")
        if action and action.lower() in ACTION_VISUALS:
            code, fg, bg = ACTION_VISUALS[action.lower()]
            chip_w = 38 if len(code) > 1 else 26
            chip_rect = QRectF(x + r + 6, y - 11, chip_w, 22)
            painter.setBrush(QColor(bg))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(chip_rect, 5, 5)
            painter.setPen(QPen(QColor(fg)))
            font_chip = QFont(); font_chip.setPointSize(10); font_chip.setBold(True)
            painter.setFont(font_chip)
            painter.drawText(chip_rect, Qt.AlignCenter, code)

    def _paint_hole_cards(self, painter: QPainter, cx: float, cy: float,
                          cards: list[str], face_up: bool) -> None:
        card_w, card_h = 28, 38
        gap = 2
        total = len(cards) * card_w + (len(cards) - 1) * gap
        start_x = cx - total / 2
        for i, c in enumerate(cards):
            x = start_x + i * (card_w + gap)
            rect = QRectF(x, cy - card_h / 2, card_w, card_h)
            if face_up:
                suit = c[1].lower() if len(c) > 1 else "?"
                bg = {"h": "#5C1F22", "d": "#1E3A5C", "s": "#0E2A1E", "c": "#2A2F3A"}.get(suit, "#1B2330")
                fg = {"h": "#EF4444", "d": "#3B82F6", "s": "#10B981", "c": "#9CA3AF"}.get(suit, "#E5E7EB")
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(bg))
                painter.drawRoundedRect(rect, 4, 4)
                painter.setPen(QPen(QColor(fg)))
                font = QFont(); font.setPointSize(13); font.setBold(True)
                painter.setFont(font)
                painter.drawText(rect, Qt.AlignCenter, c[0] if c else "?")
            else:
                painter.setPen(QPen(QColor("#3A4659"), 1))
                painter.setBrush(QColor("#1B2330"))
                painter.drawRoundedRect(rect, 4, 4)
                # Faint pattern
                painter.setPen(QPen(QColor("#2A3647"), 1))
                for dy in range(-card_h // 2 + 6, int(card_h / 2 - 4), 6):
                    painter.drawLine(int(rect.x() + 4), int(rect.center().y() + dy),
                                     int(rect.x() + card_w - 4), int(rect.center().y() + dy))

    def _paint_community(self, painter: QPainter, cx: float, cy: float) -> None:
        n = len(self.community_cards)
        card_w, card_h = 38, 50
        gap = 4
        total_w = n * card_w + (n - 1) * gap
        start_x = cx - total_w / 2
        for i, c in enumerate(self.community_cards):
            rect = QRectF(start_x + i * (card_w + gap), cy - card_h / 2, card_w, card_h)
            suit = c[1].lower() if len(c) > 1 else "?"
            bg = {"h": "#5C1F22", "d": "#1E3A5C", "s": "#0E2A1E", "c": "#2A2F3A"}.get(suit, "#1B2330")
            fg = {"h": "#EF4444", "d": "#3B82F6", "s": "#10B981", "c": "#9CA3AF"}.get(suit, "#E5E7EB")
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(bg))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QPen(QColor(fg)))
            font = QFont(); font.setPointSize(15); font.setBold(True)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, c[0] if c else "?")

    def _paint_pot(self, painter: QPainter, cx: float, cy: float) -> None:
        text = f"Pot: {self.pot_bb:.1f}bb  ·  {self.street}"
        font = QFont(); font.setPointSize(12); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#22D3EE")))
        painter.drawText(QRectF(cx - 200, cy, 400, 30), Qt.AlignCenter, text)
