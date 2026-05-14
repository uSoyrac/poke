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
    """2-11 seat oval table renderer — APT-style name+stack pills."""

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
        # Tournament overlay state — populated externally via update_field_status
        self.field_status: dict = {}     # {players_left, total, avg_stack, leader}
        self.placeholder_text: str = "Üst sağdan ▶ New Tournament butonuna bas → başla"
        self.setMinimumHeight(420)
        self.setMinimumWidth(600)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def update_field_status(self, players_left: int, total: int,
                            avg_stack: float, leader_name: str = "",
                            leader_stack: float = 0.0) -> None:
        """Set the tournament-context overlay shown at top of the table."""
        self.field_status = {
            "players_left": players_left,
            "total":        total,
            "avg_stack":    avg_stack,
            "leader":       leader_name,
            "leader_stack": leader_stack,
        }
        self.update()

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
        bb = max(1.0, getattr(hand, "big_blind", 1.0))
        # Pot in BB, not raw chips — the label says 'bb' so it must be in bb
        self.pot_bb = float(getattr(hand, "pot", 0.0)) / bb
        self.street = getattr(hand, "street_name", "Preflop")
        self.players_data = []
        last_actions = self._latest_actions(hand)
        for i, p in enumerate(hand.players):
            # Live HandState provides actions via hand.actions; SpotSnapshot puts
            # the chip info directly on each seat as .last_action — support both.
            chip = last_actions.get(i) or getattr(p, "last_action", "") or None
            self.players_data.append({
                "name": p.name,
                "position": p.position or "",
                "stack_bb": p.stack / bb,
                "current_bet_bb": p.current_bet / bb,
                "hole_cards": [c.display for c in (p.hole_cards or [])] if p.is_hero else None,
                "is_hero": p.is_hero,
                "is_folded": p.is_folded,
                "is_all_in": p.is_all_in,
                "last_action": chip,
            })
        self.update()

    @staticmethod
    def _initials(name: str) -> str:
        """Extract up to 2 initial letters from a name. 'Jim Spears' → 'JS'."""
        parts = (name or "").split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

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

        # Felt: subtle dark oval — leave room at top for status banner
        # and at bottom for hero name pill below seat
        margin_x = 100
        margin_y_top = 84
        margin_y_bot = 130    # generous space for hero name+stack pill
        oval = QRectF(margin_x, margin_y_top, w - margin_x * 2,
                       max(120, h - margin_y_top - margin_y_bot))
        margin_y = margin_y_top  # keep local var for compat below
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
            # Helpful instructions instead of misleading "Click Deal"
            painter.setPen(QColor("#9CA3AF"))
            font = QFont(); font.setPointSize(14); font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRectF(0, h * 0.40, w, 28), Qt.AlignCenter,
                              "🎰  Henüz aktif el yok")
            painter.setPen(QColor("#6B7280"))
            font.setBold(False); font.setPointSize(12); painter.setFont(font)
            painter.drawText(QRectF(0, h * 0.46, w, 24), Qt.AlignCenter,
                              "Üst sağdaki ▶ New Tournament butonuna bas → ilk el otomatik dağıtılır")
            painter.end()
            return

        # Tournament status overlay (top-center)
        if self.field_status:
            self._paint_field_status(painter, w, h)

        # Place seats around the oval (close to the rim, slightly inside)
        rx = oval.width() / 2 + 20
        ry = oval.height() / 2 + 18
        for seat_idx, data in enumerate(self.players_data):
            # Hero is always at the bottom (180°). Other seats fan around.
            seat_offset = (seat_idx - self.hero_idx) % self.num_players
            theta = math.pi / 2 + 2 * math.pi * seat_offset / self.num_players
            x = cx + rx * math.cos(theta)
            y = cy + ry * math.sin(theta)
            self._paint_seat(painter, x, y, data, seat_idx == self.dealer_idx,
                              seat_idx == self.active_idx)

        painter.end()

    def _paint_field_status(self, painter: QPainter, w: int, h: int) -> None:
        """APT-style 'Players remaining / Avg stack' banner at top of table."""
        fs = self.field_status
        text = (
            f"PLAYERS REMAINING: {fs.get('players_left', 0):,} / {fs.get('total', 0):,}    "
            f"AVG STACK: {fs.get('avg_stack', 0):,.0f}"
        )
        leader = fs.get("leader")
        if leader:
            text += f"    CHIP LEADER: {leader} ({fs.get('leader_stack', 0):,.0f})"
        # Background pill
        font = QFont(); font.setPointSize(11); font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 28
        rect = QRectF((w - tw) / 2, 8, tw, 26)
        painter.setBrush(QColor("#0E2018"))
        painter.setPen(QPen(QColor("#10B981"), 1.5))
        painter.drawRoundedRect(rect, 13, 13)
        painter.setPen(QPen(QColor("#6EE7B7")))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _paint_seat(self, painter: QPainter, x: float, y: float, data: dict,
                    is_dealer: bool, is_active: bool) -> None:
        """Render a single seat — APT-style avatar circle + name & stack pill below."""
        r = 28
        seat_rect = QRectF(x - r, y - r, r * 2, r * 2)

        # Outer halo for active player
        if is_active:
            halo = QRectF(x - r - 5, y - r - 5, (r + 5) * 2, (r + 5) * 2)
            painter.setPen(QPen(QColor("#22D3EE"), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(halo)

        # Avatar circle — colored by archetype/skill
        name_for_seed = data.get("name") or data.get("position") or "?"
        if data["is_folded"]:
            avatar_bg = QColor("#0E141C"); avatar_fg = QColor("#4B5563")
        elif data["is_all_in"]:
            avatar_bg = QColor("#3D0E10"); avatar_fg = QColor("#FCA5A5")
        elif data["is_hero"]:
            avatar_bg = QColor("#0E2A1E"); avatar_fg = QColor("#6EE7B7")
        else:
            # Hash name → soft color (deterministic, no flicker)
            hue_seed = sum(ord(c) for c in name_for_seed) % 6
            avatar_palette = ["#1E3A5C", "#5C1F22", "#2A4A2C", "#3D2A4A",
                              "#4A3D1F", "#3A4659"]
            avatar_bg = QColor(avatar_palette[hue_seed])
            avatar_fg = QColor("#E5E7EB")
        if data["is_hero"]:
            pen = QPen(QColor("#10B981"), 2.5)
        elif is_active:
            pen = QPen(QColor("#22D3EE"), 2)
        else:
            pen = QPen(QColor("#3A4659"), 1.5)
        painter.setBrush(avatar_bg)
        painter.setPen(pen)
        painter.drawEllipse(seat_rect)

        # Avatar — initials (or YOU for hero) inside circle
        initials = self._initials(data.get("name") or "?")
        if data["is_hero"]:
            initials = "YOU"
        font = QFont(); font.setPointSize(11 if len(initials) > 2 else 13); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(avatar_fg))
        painter.drawText(seat_rect, Qt.AlignCenter, initials)

        # ── Name + Stack pill BELOW the avatar (APT style) ────────────
        pill_w = 110
        pill_h = 38
        pill = QRectF(x - pill_w / 2, y + r + 4, pill_w, pill_h)
        painter.setBrush(QColor("#0E1620"))
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawRoundedRect(pill, 6, 6)
        # Position + name on first line
        pos_label = data.get("position") or "?"
        display_name = data.get("name") or "Bot"
        if data["is_hero"]:
            display_name = "uygar"
        # Truncate name if too long
        if len(display_name) > 12:
            display_name = display_name[:11] + "…"
        line1 = f"{pos_label}  ·  {display_name}"
        font_name = QFont(); font_name.setPointSize(9); font_name.setBold(True)
        painter.setFont(font_name)
        text_color = "#6B7280" if data["is_folded"] else ("#10B981" if data["is_hero"] else "#E5E7EB")
        painter.setPen(QPen(QColor(text_color)))
        painter.drawText(QRectF(pill.x(), pill.y() + 2, pill.width(), 16),
                          Qt.AlignCenter, line1)
        # Stack on second line, in green if healthy
        stack_bb = data.get("stack_bb", 0.0)
        if data["is_folded"]:
            stack_color = "#4B5563"
        elif stack_bb < 15:
            stack_color = "#F87171"   # red — short stack
        elif stack_bb < 30:
            stack_color = "#F59E0B"   # amber
        else:
            stack_color = "#34D399"   # green — healthy
        font_stack = QFont(); font_stack.setPointSize(10); font_stack.setBold(True)
        painter.setFont(font_stack)
        painter.setPen(QPen(QColor(stack_color)))
        painter.drawText(QRectF(pill.x(), pill.y() + 18, pill.width(), 18),
                          Qt.AlignCenter, f"{stack_bb:.1f} bb")

        # Current bet chip — between seat and pot center
        if data["current_bet_bb"] > 0 and not data["is_folded"]:
            cx_t, cy_t = self.width() / 2, self.height() / 2
            dx = cx_t - x; dy = cy_t - y
            dist = max(1.0, (dx**2 + dy**2)**0.5)
            chip_x = x + dx / dist * (r + 26)
            chip_y = y + dy / dist * (r + 26)
            bet_rect = QRectF(chip_x - 30, chip_y - 10, 60, 20)
            painter.setBrush(QColor("#F59E0B"))
            painter.setPen(QPen(QColor("#92400E"), 1))
            painter.drawRoundedRect(bet_rect, 10, 10)
            painter.setPen(QPen(QColor("#0B0F14")))
            font = QFont(); font.setPointSize(9); font.setBold(True)
            painter.setFont(font)
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
