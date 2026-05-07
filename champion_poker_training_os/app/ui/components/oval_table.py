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
        # Circle
        painter.setBrush(QColor("#0E141C"))
        if seat.selected:
            pen = QPen(QColor("#22D3EE"), 2.5)
        elif seat.is_hero:
            pen = QPen(QColor("#10B981"), 2.5)
        else:
            pen = QPen(QColor("#3A4659"), 1.5)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(x, y), r, r)

        # Position label
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#E5E7EB" if not seat.selected else "#22D3EE")))
        painter.drawText(QRectF(x - r, y - 10, 2 * r, 20), Qt.AlignCenter, seat.position)

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
