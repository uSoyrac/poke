"""GTO Wizard 'Aggregated Reports' screen — strategy/EV bars per board class, sortable Flops table."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState


REPORT_TABS = ["Strategy + EV", "Ranges", "Breakdown", "Reports: Flops"]
TOP_TOGGLES = [
    ("Strategy:", ["OOP", "IP"]),
    ("EV:", ["OOP", "IP"]),
    ("Equity:", ["OOP", "IP"]),
    ("EQR:", ["OOP", "IP"]),
]


@dataclass
class FlopRow:
    flop: str            # e.g. "A A A" or "A A K"
    used_pct: float      # how often this exact pattern shows up in solve set
    check: float
    bet_66: float
    allin_333: float
    oop_ev: float
    ip_ev: float
    oop_eq: float
    ip_eq: float


def _gen_flops(n: int = 60, seed: int = 1) -> list[FlopRow]:
    """Synthetic but realistic-feeling flop distribution for the Reports table."""
    ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
    rng = random.Random(seed)
    rows: list[FlopRow] = []
    seen = set()
    # Always start with the iconic AAA / AAK / AAQ etc.
    seeded = ["A A A", "A A K", "A A K", "A A Q", "A A Q", "A A J", "A A T", "A K K", "A K Q"]
    for s in seeded:
        rows.append(_make_row(s, rng))
        seen.add(s)
    while len(rows) < n:
        a, b, c = sorted([rng.choice(ranks), rng.choice(ranks), rng.choice(ranks)],
                         key=lambda r: ranks.index(r))
        flop = f"{a} {b} {c}"
        rows.append(_make_row(flop, rng))
    return rows


def _make_row(flop: str, rng: random.Random) -> FlopRow:
    check = round(rng.uniform(0.45, 0.65), 3)
    bet_66 = round(1 - check, 3)
    allin = round(rng.uniform(0, 0.04), 3)
    oop_ev = round(rng.uniform(0.42, 0.58), 3)
    ip_ev = round(1 - oop_ev, 3)
    eq_oop = round(rng.uniform(0.40, 0.60) * 100, 1)
    eq_ip = round(100 - eq_oop, 1)
    used = round(rng.uniform(0.001, 0.04), 4)
    return FlopRow(flop, used, check, bet_66, allin, oop_ev, ip_ev, eq_oop, eq_ip)


class StrategyBars(QWidget):
    """Wide horizontal/vertical bar chart visualising strategy frequency per flop bucket."""

    def __init__(self, rows: list[FlopRow]):
        super().__init__()
        self.rows = rows
        self.setMinimumHeight(220)

    def set_rows(self, rows: list[FlopRow]) -> None:
        self.rows = rows
        self.update()

    def paintEvent(self, event) -> None:
        if not self.rows:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin_x = 18
        margin_y = 24
        chart_w = w - margin_x * 2
        chart_h = h - margin_y * 2
        n = min(len(self.rows), 60)
        if n == 0:
            return
        bar_w = max(2.0, chart_w / n - 2)
        gap = 2

        # Baseline grid
        painter.setPen(QPen(QColor("#1E2733"), 1))
        for frac in (0.25, 0.5, 0.75):
            y = margin_y + chart_h * (1 - frac)
            painter.drawLine(margin_x, int(y), w - margin_x, int(y))

        # Bars
        for i, row in enumerate(self.rows[:n]):
            x = margin_x + i * (bar_w + gap)
            # Use bet_66 as the "strategy frequency" being plotted
            value = row.bet_66
            bar_h = chart_h * value
            y = margin_y + (chart_h - bar_h)
            # Color gradient: green (>=0.6), cyan (>=0.4), amber (>=0.2), red (<0.2)
            if value >= 0.6:
                color = QColor("#10B981")
            elif value >= 0.4:
                color = QColor("#F59E0B")
            elif value >= 0.2:
                color = QColor("#EF4444")
            else:
                color = QColor("#7F1D1D")
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(int(x), int(y), int(bar_w), int(bar_h), 1, 1)

        # Axis labels
        painter.setPen(QPen(QColor("#9CA3AF")))
        font = QFont(); font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(2, margin_y + 6, "100%")
        painter.drawText(2, margin_y + chart_h, "0")
        painter.drawText(margin_x, h - 4, "Flops sorted by strategy frequency")
        painter.end()


class HBar(QWidget):
    """Inline horizontal split bar for a single row's check vs bet ratio."""

    def __init__(self, left: float, right: float, allin: float = 0.0):
        super().__init__()
        self.left = left
        self.right = right
        self.allin = allin
        self.setFixedHeight(16)
        self.setMinimumWidth(80)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        rect_left = int(w * self.left)
        rect_mid = int(w * self.right)
        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(0, 2, w, h - 4, 3, 3)
        # Left (check / call) — green
        painter.setBrush(QColor("#10B981"))
        painter.drawRoundedRect(0, 2, rect_left, h - 4, 3, 3)
        # Right (bet / raise) — red
        painter.setBrush(QColor("#EF4444"))
        painter.drawRoundedRect(rect_left, 2, rect_mid, h - 4, 3, 3)
        if self.allin > 0:
            allin_w = int(w * self.allin)
            painter.setBrush(QColor("#7F1D1D"))
            painter.drawRoundedRect(rect_left + rect_mid, 2, allin_w, h - 4, 3, 3)
        painter.end()


class _MiniFlop(QWidget):
    """Tiny inline rendering of three flop cards by rank."""

    def __init__(self, flop: str):
        super().__init__()
        self.cards = [c for c in flop.split() if c]
        self.setFixedSize(62, 22)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        x = 0
        suit_colors = ["#5C1F22", "#1E3A5C", "#0E2A1E"]
        for i, c in enumerate(self.cards[:3]):
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(suit_colors[i % len(suit_colors)]))
            painter.drawRoundedRect(x, 2, 18, 18, 3, 3)
            painter.setPen(QPen(QColor("#F3F4F6")))
            font = QFont(); font.setPointSize(10); font.setBold(True)
            painter.setFont(font)
            painter.drawText(x, 2, 18, 18, Qt.AlignCenter, c)
            x += 20
        painter.end()


class AggregatedReportsScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.setObjectName('AggregatedReportsScreenRoot')
        from app.ui.theme import poke_tokens as _pt_bg
        from PySide6.QtCore import Qt as _Qt_bg
        self.setAttribute(_Qt_bg.WA_StyledBackground, True)
        self.setStyleSheet(f"#AggregatedReportsScreenRoot {{ background: {_pt_bg.BG}; }}")
        self.state = state
        self.rows = sorted(_gen_flops(60), key=lambda r: -r.bet_66)

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
        title = QLabel("Aggregated Reports")
        title.setObjectName("Title")
        layout.addWidget(title)

        # --- Tabs ---
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)
        self.tab_buttons = QButtonGroup(self)
        self.tab_buttons.setExclusive(True)
        for i, name in enumerate(REPORT_TABS):
            btn = QPushButton(name + (" ▼" if "+" in name or "Flops" in name else ""))
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius:0; color: #8B95A7; padding: 8px 16px; font-weight: 600; }"
                "QPushButton:hover { color: #E5E7EB; }"
                "QPushButton:checked { background: #1B2A3D; color: #22D3EE; border-color: #2A4257; }"
            )
            self.tab_buttons.addButton(btn, i)
            tabs_row.addWidget(btn)
            if i == 0:
                btn.setChecked(True)
        tabs_row.addStretch(1)
        layout.addLayout(tabs_row)

        # --- Top toggles row (Strategy / EV / Equity / EQR | OOP IP) ---
        toggles_row = QHBoxLayout()
        toggles_row.setSpacing(20)
        for label_text, options in TOP_TOGGLES:
            grp = QHBoxLayout()
            grp.setSpacing(6)
            label = QLabel(label_text)
            label.setObjectName("Muted")
            grp.addWidget(label)
            for opt in options:
                pill = QPushButton(opt)
                pill.setCheckable(True)
                pill.setChecked(opt == "OOP")
                pill.setStyleSheet(
                    "QPushButton { background: #0E141C; border: 1px solid #1E2733; "
                    "border-radius:0; padding: 4px 10px; color: #8B95A7; font-weight: 700; }"
                    "QPushButton:checked { background: #1B2A3D; color: #22D3EE; border-color: #2A4257; }"
                )
                grp.addWidget(pill)
            container = QWidget()
            container.setLayout(grp)
            toggles_row.addWidget(container)
        toggles_row.addStretch(1)
        layout.addLayout(toggles_row)

        # --- Main split: bars on left, table on right ---
        split = QHBoxLayout()
        split.setSpacing(14)

        # Left: bar chart card
        bars_card = QFrame()
        bars_card.setObjectName("Card")
        bars_layout = QVBoxLayout(bars_card)
        bars_layout.setContentsMargins(14, 14, 14, 14)
        bars_title = QLabel("Strategy + EV")
        bars_title.setObjectName("SectionTitle")
        bars_layout.addWidget(bars_title)
        self.bars = StrategyBars(self.rows)
        bars_layout.addWidget(self.bars, 1)
        # Legend
        legend = QHBoxLayout()
        for color, text in [("#10B981", "≥60% bet"), ("#F59E0B", "40-60%"),
                            ("#EF4444", "20-40%"), ("#7F1D1D", "<20%")]:
            sw = QLabel("●  " + text)
            sw.setStyleSheet(f"color: {color}; font-weight: 700;")
            legend.addWidget(sw)
        legend.addStretch(1)
        bars_layout.addLayout(legend)
        split.addWidget(bars_card, 3)

        # Right: detailed Flops table
        table_card = QFrame()
        table_card.setObjectName("Card")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setContentsMargins(14, 14, 14, 14)
        head_row = QHBoxLayout()
        head_label = QLabel("Reports: Flops")
        head_label.setObjectName("SectionTitle")
        head_row.addWidget(head_label)
        head_row.addStretch(1)
        sort_combo = QComboBox()
        sort_combo.addItems(["Bet 66%", "Check %", "OOP EV", "IP EV", "OOP EQ"])
        sort_combo.currentTextChanged.connect(self._sort_changed)
        head_row.addWidget(QLabel("Sort by"))
        head_row.addWidget(sort_combo)
        tc_layout.addLayout(head_row)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["Flop", "Used by", "Check / Bet", "Bet 66%", "Allin 333%", "OOP EV", "IP EV", "OOP EQ", "IP EQ"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet(
            "QTableWidget { background: transparent; border: none; gridline-color: transparent; }"
            "QTableWidget::item { padding: 6px 4px; border-bottom: 1px solid #131A24; }"
            "QTableWidget::item:selected { background: #1B2A3D; color: #E5E7EB; }"
            "QHeaderView::section { background: transparent; color: #8B95A7; "
            "border: none; border-bottom: 1px solid #1E2733; padding: 8px 6px; "
            "font-weight: 700; font-size: 11px; }"
        )
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        tc_layout.addWidget(self.table, 1)
        split.addWidget(table_card, 4)

        layout.addLayout(split)

        # --- Footer summary ---
        footer = QHBoxLayout()
        for title_text, value, color in [
            ("Avg bet 66%", f"{sum(r.bet_66 for r in self.rows) / len(self.rows) * 100:.1f}%", "Cyan"),
            ("Avg check", f"{sum(r.check for r in self.rows) / len(self.rows) * 100:.1f}%", "Green"),
            ("OOP avg EV", f"{sum(r.oop_ev for r in self.rows) / len(self.rows):.2f}", "Amber"),
            ("OOP avg EQ", f"{sum(r.oop_eq for r in self.rows) / len(self.rows):.1f}%", "Purple"),
        ]:
            card = QFrame()
            card.setObjectName("Card")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            l1 = QLabel(title_text)
            l1.setObjectName("Muted")
            l2 = QLabel(value)
            l2.setObjectName(color)
            l2.setStyleSheet("font-size: 18px; font-weight: 800;")
            cl.addWidget(l1)
            cl.addWidget(l2)
            footer.addWidget(card)
        layout.addLayout(footer)

        self._populate_table()

    def _sort_changed(self, label: str) -> None:
        key_map = {
            "Bet 66%": lambda r: -r.bet_66,
            "Check %": lambda r: -r.check,
            "OOP EV": lambda r: -r.oop_ev,
            "IP EV": lambda r: -r.ip_ev,
            "OOP EQ": lambda r: -r.oop_eq,
        }
        self.rows.sort(key=key_map.get(label, lambda r: -r.bet_66))
        self.bars.set_rows(self.rows)
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            self.table.setRowHeight(r, 30)
            # Flop chips
            self.table.setCellWidget(r, 0, _MiniFlop(row.flop))
            # Used by
            it = QTableWidgetItem(f"{row.used_pct * 100:.2f}%")
            it.setForeground(QColor("#9CA3AF"))
            self.table.setItem(r, 1, it)
            # Check/Bet inline split
            self.table.setCellWidget(r, 2, HBar(row.check, row.bet_66, row.allin_333))
            # Numeric cols
            for col, val, color in [
                (3, f"{row.bet_66 * 100:.1f}%", "#F87171"),
                (4, (f"{row.allin_333 * 100:.1f}%" if row.allin_333 > 0 else "—"), "#7F1D1D"),
                (5, f"{row.oop_ev:.2f}", "#22D3EE"),
                (6, f"{row.ip_ev:.2f}", "#22D3EE"),
                (7, f"{row.oop_eq:.1f}%", "#10B981"),
                (8, f"{row.ip_eq:.1f}%", "#10B981"),
            ]:
                cell = QTableWidgetItem(val)
                cell.setForeground(QColor(color))
                cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, col, cell)
