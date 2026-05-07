"""Range Viewer — Strategy / Range tabs, SB & BB ranges side-by-side, equity line chart underneath.

Mirrors the GTO Wizard 'compare two ranges' panel from the screenshots.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.poker.ranges import demo_frequency, range_matrix
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, OvalTable


class RangeMosaic(QWidget):
    """Compact orange/colored heat-mosaic representation of a range, like the screenshot.

    Renders a 13×13 grid as small filled cells whose intensity reflects frequency,
    with a wave-like top edge by skipping low-frequency hands.
    """

    def __init__(self, mode: str = "BTN RFI", color: str = "#F59E0B"):
        super().__init__()
        self.mode = mode
        self.color = QColor(color)
        self.setMinimumSize(220, 150)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        cols = 13
        rows = 13
        cell_w = (w - 14) / cols
        cell_h = (h - 14) / rows
        # Draw a light grid background
        painter.setPen(QPen(QColor("#1E2733"), 1))
        for i in range(rows + 1):
            y = 7 + i * cell_h
            painter.drawLine(7, int(y), w - 7, int(y))
        for j in range(cols + 1):
            x = 7 + j * cell_w
            painter.drawLine(int(x), 7, int(x), h - 7)
        # Fill cells per frequency
        matrix = range_matrix()
        for r, row_hands in enumerate(matrix):
            for c, hand in enumerate(row_hands):
                freq = demo_frequency(hand, self.mode)
                if freq < 15:
                    continue
                x = 7 + c * cell_w
                y = 7 + r * cell_h
                color = QColor(self.color)
                color.setAlpha(int(60 + 195 * (freq / 100)))
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(int(x + 1), int(y + 1), int(cell_w - 2), int(cell_h - 2), 1, 1)
        painter.end()


class EquityChart(QWidget):
    """Hand-by-hand equity chart for two players (SB blue / BB green) like the screenshot."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(140)
        rng = random.Random(11)
        # Generate two cumulative-equity-style series that diverge then converge
        self.sb = self._series(rng, drift=0.04)
        self.bb = self._series(rng, drift=0.03, offset=-2)
        self.marker_x = int(len(self.sb) * 0.65)

    @staticmethod
    def _series(rng: random.Random, drift: float = 0.0, offset: float = 0.0, n: int = 110) -> list[float]:
        out: list[float] = []
        v = offset
        for _ in range(n):
            v += rng.gauss(drift, 0.4)
            out.append(v)
        return out

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin = 18
        chart_w = w - margin * 2
        chart_h = h - margin * 2
        all_vals = self.sb + self.bb
        lo = min(all_vals) - 1
        hi = max(all_vals) + 1
        rng = max(hi - lo, 1)

        def to_xy(series: list[float]) -> list[QPointF]:
            return [
                QPointF(margin + chart_w * i / (len(series) - 1),
                        margin + chart_h * (1 - (v - lo) / rng))
                for i, v in enumerate(series)
            ]

        # Grid
        painter.setPen(QPen(QColor("#1E2733"), 1))
        for frac in (0.25, 0.5, 0.75):
            y = margin + chart_h * frac
            painter.drawLine(margin, int(y), w - margin, int(y))

        # Lines
        sb_pts = to_xy(self.sb)
        bb_pts = to_xy(self.bb)
        painter.setPen(QPen(QColor("#5BA9F0"), 2))
        for i in range(len(sb_pts) - 1):
            painter.drawLine(sb_pts[i], sb_pts[i + 1])
        painter.setPen(QPen(QColor("#10B981"), 2))
        for i in range(len(bb_pts) - 1):
            painter.drawLine(bb_pts[i], bb_pts[i + 1])

        # Marker dot at current hand
        idx = self.marker_x
        if 0 <= idx < len(sb_pts):
            painter.setBrush(QColor("#F59E0B"))
            painter.setPen(QPen(QColor("#0B0F14"), 2))
            painter.drawEllipse(sb_pts[idx], 5, 5)

        # Legend
        painter.setPen(QPen(QColor("#5BA9F0")))
        font = QFont(); font.setPointSize(10); font.setBold(True)
        painter.setFont(font)
        painter.drawText(margin, margin - 4, "● SB")
        painter.setPen(QPen(QColor("#10B981")))
        painter.drawText(margin + 60, margin - 4, "● BB")
        painter.end()


class RangeViewerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # --- Title ---
        title_row = QHBoxLayout()
        title = QLabel("Range Viewer — SB vs BB")
        title.setObjectName("Title")
        title_row.addWidget(title)
        title_row.addStretch(1)
        # Strategy / Range tabs
        self.tabs = QButtonGroup(self)
        self.tabs.setExclusive(True)
        for i, name in enumerate(["Strategy", "Range"]):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius: 7px; padding: 8px 18px; color: #8B95A7; font-weight: 700; }"
                "QPushButton:checked { background: #1B2A3D; color: #22D3EE; border-color: #2A4257; }"
            )
            self.tabs.addButton(btn, i)
            title_row.addWidget(btn)
            if i == 1:  # default to Range
                btn.setChecked(True)
        layout.addLayout(title_row)

        # --- Main: left panel (ranges + chart) + right panel (oval table preview) ---
        main = QHBoxLayout()
        main.setSpacing(14)

        # Left: ranges + equity chart card
        left_card = QFrame()
        left_card.setObjectName("Card")
        lc_layout = QVBoxLayout(left_card)
        lc_layout.setContentsMargins(14, 14, 14, 14)

        # Range labels row (SB / BB) with eye-toggles
        lbl_row = QHBoxLayout()
        sb_box = QVBoxLayout()
        bb_box = QVBoxLayout()
        sb_lbl = QHBoxLayout()
        sb_lbl.addWidget(QLabel("SB"))
        sb_lbl.addStretch(1)
        sb_eye = QLabel("👁")
        sb_eye.setObjectName("Muted")
        sb_lbl.addWidget(sb_eye)
        sb_box.addLayout(sb_lbl)

        bb_lbl = QHBoxLayout()
        bb_lbl.addWidget(QLabel("BB"))
        bb_lbl.addStretch(1)
        bb_eye = QLabel("👁")
        bb_eye.setObjectName("Muted")
        bb_lbl.addWidget(bb_eye)
        bb_box.addLayout(bb_lbl)

        sb_box.addWidget(RangeMosaic("SB strategy", color="#F59E0B"))
        bb_box.addWidget(RangeMosaic("BB defend", color="#F59E0B"))

        lbl_row.addLayout(sb_box)
        lbl_row.addLayout(bb_box)
        lc_layout.addLayout(lbl_row)

        # Equity chart label + widget
        eq_row = QHBoxLayout()
        eq_lbl = QLabel("Equity chart")
        eq_lbl.setObjectName("SectionTitle")
        eq_row.addWidget(eq_lbl)
        eq_row.addStretch(1)
        eq_eye = QLabel("👁")
        eq_eye.setObjectName("Muted")
        eq_row.addWidget(eq_eye)
        lc_layout.addLayout(eq_row)
        lc_layout.addWidget(EquityChart())
        main.addWidget(left_card, 5)

        # Right: oval table preview (mirrors the screenshot's small table on the right)
        right_card = QFrame()
        right_card.setObjectName("Card")
        rc_layout = QVBoxLayout(right_card)
        rc_layout.setContentsMargins(14, 14, 14, 14)
        right_title = QLabel("Spot preview")
        right_title.setObjectName("Muted")
        rc_layout.addWidget(right_title)
        oval = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=False)
        oval.set_dealer("BTN")
        oval.set_hero("SB")
        # Show stack labels by mapping position labels in seats; we reuse seats names
        oval.set_actions({
            "SB": ["100"],
            "BB": ["100"],
            "UTG": ["100"],
            "CO": ["100"],
            "BTN": ["100"],
        })
        oval.set_community_cards(["W", "W", "W"])
        rc_layout.addWidget(oval, 1)
        main.addWidget(right_card, 4)

        layout.addLayout(main)

        # --- Bottom controls: position + stack selectors ---
        controls = QFrame()
        controls.setObjectName("Card")
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.addWidget(QLabel("Hero pos"))
        self.hero_pos = QComboBox()
        self.hero_pos.addItems(["SB", "BB", "BTN", "CO", "HJ", "LJ", "UTG"])
        c_layout.addWidget(self.hero_pos)
        c_layout.addSpacing(20)
        c_layout.addWidget(QLabel("Stack"))
        self.stack = QComboBox()
        self.stack.addItems(["10bb", "15bb", "20bb", "25bb", "40bb", "60bb", "100bb", "200bb"])
        self.stack.setCurrentText("100bb")
        c_layout.addWidget(self.stack)
        c_layout.addSpacing(20)
        c_layout.addWidget(QLabel("Action"))
        self.action = QComboBox()
        self.action.addItems(["RFI", "vs RFI", "vs 3bet", "4bet", "Squeeze"])
        c_layout.addWidget(self.action)
        c_layout.addStretch(1)
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(
            lambda: self.coach_message.emit(
                f"Range güncellendi: {self.hero_pos.currentText()} {self.stack.currentText()} {self.action.currentText()}. "
                "Solver verisi mock; gerçek import için Settings > Solver Library kullan."
            )
        )
        practice_btn = QPushButton("▶  Practice this spot")
        practice_btn.setObjectName("PrimaryButton")
        practice_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 8px 18px; border-radius: 7px; border: none; }"
            "QPushButton:hover { background: #34D399; }"
        )
        practice_btn.clicked.connect(self._launch_practice)
        c_layout.addWidget(update_btn)
        c_layout.addWidget(practice_btn)
        layout.addWidget(controls)

    def _launch_practice(self) -> None:
        """Hand off the current Range Viewer selection to the Spot Trainer."""
        pos = self.hero_pos.currentText()
        stack = self.stack.currentText()
        action = self.action.currentText()
        # Map Action selector to Drill Builder's preflop pills
        action_map = {
            "RFI": "SRP",
            "vs RFI": "SRP",
            "vs 3bet": "3-bet",
            "4bet": "4-bet",
            "Squeeze": "Squeeze",
        }
        self.state.drill_filters = {
            "positions": [pos],
            "solution": "MTT • ChipEV",
            "starting_spot": "Preflop",
            "preflop_action": action_map.get(action, "Any"),
        }
        self.coach_message.emit(
            f"Practice modu başladı — {pos} {stack} {action}. Spot Trainer ilgili spotları yükleyecek."
        )
        self.navigate_requested.emit("Spot Practice Trainer")
