"""GTO Wizard-style 'Hands' page — sortable table of all played hands with filter tabs."""
from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.repository import get_session_history
from app.db.seed_data import generate_hands
from app.ui.components.mini_card import MiniCardRow


COLUMNS = [
    "", "Tag", "Status", "Date", "Format", "Site", "Position", "Hand", "Board",
    "Pot Type", "Preflop", "Flop", "Turn", "River",
    "Pot (bb)", "Win/Loss (bb)", "EV Loss (bb)",
]

FILTER_TABS = [
    "Filters",
    "Streets Actions",
    "Hands Details",
    "Statistics and Results",
    "Hole Cards",
    "Game Type",
    "Other",
]


class StatusDot(QWidget):
    """Small icon — green check for reviewed, dotted circle for in-review."""

    def __init__(self, status: str = "review"):
        super().__init__()
        self.status = status
        self.setFixedSize(18, 18)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        if self.status == "done":
            painter.setBrush(QColor("#0E2A1E"))
            painter.setPen(QPen(QColor("#10B981"), 1.5))
            painter.drawEllipse(rect)
            painter.setPen(QPen(QColor("#10B981"), 2))
            painter.drawLine(rect.x() + 4, rect.y() + rect.height() // 2,
                             rect.x() + rect.width() // 2 - 1, rect.y() + rect.height() - 4)
            painter.drawLine(rect.x() + rect.width() // 2 - 1, rect.y() + rect.height() - 4,
                             rect.x() + rect.width() - 3, rect.y() + 3)
        else:
            pen = QPen(QColor("#22D3EE"), 1.5)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)
        painter.end()


class FilterChip(QFrame):
    """Active filter pill (e.g. 'Source: PokerArena ✕')."""

    removed = Signal(str)

    def __init__(self, label: str, value: str):
        super().__init__()
        self.key = label
        self.setStyleSheet(
            "QFrame { background: #131A24; border: 1px solid #1E2733; border-radius: 14px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(6)
        l1 = QLabel(label)
        l1.setObjectName("Muted")
        l2 = QLabel(value)
        l2.setStyleSheet("color: #E5E7EB; font-weight: 700;")
        x = QPushButton("✕")
        x.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #8B95A7; font-weight: 700; padding: 0 4px; }"
            "QPushButton:hover { color: #EF4444; }"
        )
        x.setCursor(Qt.PointingHandCursor)
        x.clicked.connect(lambda: self.removed.emit(self.key))
        layout.addWidget(l1)
        layout.addWidget(l2)
        layout.addWidget(x)


def _action_html(text: str) -> str:
    """Render a compact action sequence like 'CRC' or 'BC' with per-letter color."""
    color_map = {
        "F": "#5BA9F0",
        "C": "#3DD37C",
        "X": "#3DD37C",
        "B": "#F87171",
        "R": "#F87171",
    }
    if not text:
        return ""
    parts = []
    for ch in text:
        c = color_map.get(ch.upper(), "#E5E7EB")
        parts.append(f"<span style='color:{c}; font-weight:700;'>{ch}</span>")
    return " ".join(parts)


class _RichLabel(QLabel):
    def __init__(self, html: str):
        super().__init__()
        self.setTextFormat(Qt.RichText)
        self.setText(html)
        self.setContentsMargins(8, 0, 0, 0)


def _seed_demo_hands() -> list[dict[str, Any]]:
    """Generate a small set of demo hands matching the screenshot layout."""
    rng = random.Random(42)
    formats = ["HU SnG", "MTT", "NL50", "NL100", "Spin & Go"]
    sites = ["PokerArena", "GG Poker", "PokerStars"]
    positions = ["SB", "BB", "BTN", "CO", "HJ", "UTG"]
    pot_types = ["Limp", "SRP", "Preflop", "3BP", "4BP"]
    actions_pre = ["CX", "RC", "CRC", "F", "RF", "C", "R"]
    actions_post = ["BC", "BF", "XBR", "XX", "BB", "BC", ""]

    hands: list[dict[str, Any]] = []
    sample_hands = [
        ("T8s", "Q875T2"),
        ("QTo", "T535"),
        ("A9o", "55275"),
        ("J2o", ""),
        ("K6o", ""),
        ("65s", ""),
        ("73o", "8646"),
        ("AKs", "AhKd2c"),
        ("99", "9s5h2d"),
        ("KQo", "KhTc4s"),
        ("88", "Ah8s5d"),
        ("76s", "7c6h2s"),
    ]
    statuses = ["review", "review", "review", "done", "done", "done", "review", "done", "review", "done", "review", "done"]

    for i, ((hand, board), status) in enumerate(zip(sample_hands, statuses)):
        is_preflop_only = not board
        hand_pot = round(rng.uniform(1.5, 30), 2)
        win = round(rng.uniform(-3, 3) * (1 if rng.random() > 0.4 else -1), 2)
        ev_loss = round(max(0.0, rng.uniform(0, 1.0) if rng.random() > 0.5 else 0), 2)
        hands.append({
            "id": f"H{i+1:03d}",
            "tag": "—",
            "status": status,
            "date": "5/8/2026",
            "format": rng.choice(formats),
            "site": rng.choice(sites),
            "position": rng.choice(positions),
            "hand": hand,
            "board": board if not is_preflop_only else "",
            "pot_type": "Preflop" if is_preflop_only else rng.choice(pot_types),
            "preflop": rng.choice(actions_pre),
            "flop": "" if is_preflop_only else rng.choice(actions_post),
            "turn": "" if is_preflop_only or rng.random() < 0.4 else rng.choice(actions_post),
            "river": "" if is_preflop_only or rng.random() < 0.7 else rng.choice(actions_post),
            "pot": hand_pot,
            "win_loss": win,
            "ev_loss": ev_loss,
        })
    return hands


def _hand_to_cards(hand: str) -> list[str]:
    """'T8s' -> ['Th','8s'] (suits picked deterministically); 'AhKd' -> ['Ah','Kd']."""
    if not hand:
        return []
    if len(hand) >= 4 and all(c.isalnum() for c in hand[:4]):
        # already in 'AhKd' form
        return [hand[i:i+2] for i in range(0, len(hand) - len(hand) % 2, 2)]
    if len(hand) == 2:
        return [hand[0] + "h", hand[1] + "d"]
    if len(hand) == 3:
        suited = hand.endswith("s")
        return [hand[0] + "h", hand[1] + ("h" if suited else "d")]
    return []


def _board_to_cards(board: str) -> list[str]:
    if not board:
        return []
    if any(c.isalpha() and c.lower() in "hdsc" for c in board[1::2]):
        # already with suits
        return [board[i:i+2] for i in range(0, len(board) - len(board) % 2, 2)]
    # Just ranks like 'Q875T2'  -> assign suits round-robin
    suits = ["h", "d", "s", "c", "h"]
    return [r + suits[i % 4] for i, r in enumerate(board)]


class HandsListScreen(QWidget):
    """Comprehensive 'Hands' table view with filter tabs and rich row rendering."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.active_filters: dict[str, str] = {"Source": "PokerArena"}
        self.all_hands = self._load_hands()

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

        # --- Title row ---
        title_row = QHBoxLayout()
        title = QLabel("Hands")
        title.setObjectName("Title")
        title_row.addWidget(title)

        site_btn = QPushButton("⚔  PokerArena")
        site_btn.setStyleSheet(
            "QPushButton { background: #131A24; border: 1px solid #2A3647; border-radius: 7px; "
            "color: #E5E7EB; padding: 8px 14px; font-weight: 700; }"
        )
        all_reports = QPushButton("☰  All Reports")
        new_report = QPushButton("📄  New Report")
        save_report = QPushButton("Save Report")
        for b in (all_reports, new_report, save_report):
            b.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; border-radius: 7px; "
                "color: #8B95A7; padding: 8px 14px; }"
            )
        title_row.addSpacing(10)
        title_row.addWidget(site_btn)
        title_row.addWidget(all_reports)
        title_row.addWidget(new_report)
        title_row.addWidget(save_report)
        title_row.addStretch(1)

        # Date range pickers
        date_from = QDateEdit()
        date_from.setDisplayFormat("dd/MM/yyyy")
        date_from.setCalendarPopup(True)
        date_to = QDateEdit()
        date_to.setDisplayFormat("dd/MM/yyyy")
        date_to.setCalendarPopup(True)
        for d in (date_from, date_to):
            d.setStyleSheet(
                "QDateEdit { background: #0E141C; border: 1px solid #1E2733; border-radius: 7px; "
                "color: #8B95A7; padding: 6px 10px; min-width: 130px; }"
            )
        title_row.addWidget(QLabel("📅"))
        title_row.addWidget(date_from)
        sep = QLabel("—")
        sep.setObjectName("Muted")
        title_row.addWidget(sep)
        title_row.addWidget(date_to)
        layout.addLayout(title_row)

        # --- Filter tabs ---
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)
        self.tab_buttons = QButtonGroup(self)
        self.tab_buttons.setExclusive(True)
        for i, name in enumerate(FILTER_TABS):
            label = name + (" 2" if name == "Other" else "")
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; padding: 8px 14px; "
                "color: #8B95A7; font-weight: 600; border-bottom: 2px solid transparent; }"
                "QPushButton:hover { color: #E5E7EB; }"
                "QPushButton:checked { color: #E5E7EB; font-weight: 800; border-bottom: 2px solid transparent; "
                "background: #1B2330; border-radius: 7px; }"
            )
            if i == 1:
                btn.setChecked(True)
            self.tab_buttons.addButton(btn, i)
            tabs_row.addWidget(btn)
        tabs_row.addStretch(1)
        search_btn = QPushButton("🔍")
        search_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #8B95A7; padding: 8px; }"
            "QPushButton:hover { color: #E5E7EB; }"
        )
        tabs_row.addWidget(search_btn)
        layout.addLayout(tabs_row)

        # --- Active filters ---
        self.active_filter_row = QHBoxLayout()
        self.active_filter_row.setSpacing(8)
        af_label = QLabel("Active Filters")
        af_label.setObjectName("Muted")
        self.active_filter_row.addWidget(af_label)
        self._active_filter_widgets: list[QWidget] = []
        self._render_active_filters()
        clear_all = QPushButton("✕")
        clear_all.setStyleSheet(
            "QPushButton { background: #131A24; border: 1px solid #1E2733; border-radius: 12px; "
            "color: #8B95A7; min-width: 24px; min-height: 24px; }"
            "QPushButton:hover { color: #EF4444; border-color: #EF4444; }"
        )
        clear_all.clicked.connect(self._clear_filters)
        self.active_filter_row.addStretch(1)
        self.active_filter_row.addWidget(clear_all)
        layout.addLayout(self.active_filter_row)

        # --- Table ---
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setStyleSheet(
            "QTableWidget { background: #0B0F14; border: none; gridline-color: transparent; }"
            "QTableWidget::item { padding: 6px 4px; border-bottom: 1px solid #131A24; }"
            "QTableWidget::item:selected { background: #1B2A3D; color: #E5E7EB; }"
            "QHeaderView::section { background: #0B0F14; color: #8B95A7; "
            "border: none; border-bottom: 1px solid #1E2733; padding: 10px 6px; "
            "font-weight: 700; font-size: 12px; }"
        )
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setStretchLastSection(False)
        self.table.cellClicked.connect(self._on_row_clicked)
        layout.addWidget(self.table, 1)

        # --- Footer summary ---
        footer = QFrame()
        footer.setStyleSheet(
            "QFrame { background: #131A24; border-top: 1px solid #1E2733; }"
        )
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_count = QLabel("0 hands")
        self.lbl_count.setObjectName("Muted")
        self.lbl_count.setStyleSheet("font-weight: 700;")
        f_layout.addWidget(self.lbl_count)
        f_layout.addStretch(1)
        self.lbl_pot_total = QLabel("0.00")
        self.lbl_pot_total.setStyleSheet("color: #E5E7EB; font-weight: 700; padding-right: 24px;")
        self.lbl_win_total = QLabel("0.00")
        self.lbl_win_total.setObjectName("Green")
        self.lbl_ev_total = QLabel("0.00")
        self.lbl_ev_total.setObjectName("Amber")
        f_layout.addWidget(self.lbl_pot_total)
        f_layout.addSpacing(40)
        f_layout.addWidget(self.lbl_win_total)
        f_layout.addSpacing(40)
        f_layout.addWidget(self.lbl_ev_total)
        layout.addWidget(footer)

        self._populate()

    # --- data ------------------------------------------------------------
    def _load_hands(self) -> list[dict[str, Any]]:
        """Try DB first, fall back to demo seed data."""
        hands: list[dict[str, Any]] = []
        try:
            for h in get_session_history(50):
                hands.append({
                    "id": f"H{h.get('hand_id', '?')}",
                    "tag": "—",
                    "status": "done" if h.get("hero_won") else "review",
                    "date": str(h.get("played_at", "today"))[:10] or "—",
                    "format": h.get("format", "Cash 6-max"),
                    "site": "Champion OS",
                    "position": h.get("hero_position", "—"),
                    "hand": (h.get("hero_cards", "??") or "").replace(" ", "")[:6],
                    "board": (h.get("community", "") or "").replace(" ", "")[:10],
                    "pot_type": "SRP",
                    "preflop": "RC",
                    "flop": "BC" if h.get("streets_seen", 0) >= 2 else "",
                    "turn": "BC" if h.get("streets_seen", 0) >= 3 else "",
                    "river": "BF" if h.get("streets_seen", 0) >= 4 else "",
                    "pot": float(h.get("pot", 0)),
                    "win_loss": float(h.get("hero_profit", 0)),
                    "ev_loss": 0.0,
                })
        except Exception:
            pass
        if not hands:
            hands = _seed_demo_hands()
        return hands

    def _filtered(self) -> list[dict[str, Any]]:
        out = list(self.all_hands)
        for k, v in self.active_filters.items():
            if k == "Source":
                # No-op for demo data; would filter by site in real data
                pass
        return out

    def _populate(self) -> None:
        rows = self._filtered()
        self.table.setRowCount(len(rows))
        self.table.setProperty("rows", rows)
        for r, hand in enumerate(rows):
            self.table.setRowHeight(r, 40)
            # Checkbox col 0 — empty placeholder
            self.table.setItem(r, 0, QTableWidgetItem("☐"))
            # Tag
            tag_item = QTableWidgetItem(hand["tag"])
            tag_item.setForeground(QColor("#8B95A7"))
            self.table.setItem(r, 1, tag_item)
            # Status
            self.table.setCellWidget(r, 2, _wrap_center(StatusDot(hand["status"])))
            # Date
            self.table.setItem(r, 3, _muted_item(hand["date"]))
            # Format
            self.table.setItem(r, 4, _plain_item(hand["format"]))
            # Site (icon-ish)
            self.table.setCellWidget(r, 5, _wrap_left(QLabel("⚔  " + hand["site"])))
            # Position
            self.table.setItem(r, 6, _plain_item(hand["position"]))
            # Hand cards
            self.table.setCellWidget(r, 7, MiniCardRow(_hand_to_cards(hand["hand"]), size=22))
            # Board cards
            board_cards = _board_to_cards(hand["board"])
            if board_cards:
                self.table.setCellWidget(r, 8, MiniCardRow(board_cards, size=22))
            else:
                self.table.setItem(r, 8, _muted_item(""))
            # Pot type
            self.table.setItem(r, 9, _plain_item(hand["pot_type"]))
            # Preflop / Flop / Turn / River — coloured action codes
            for col, key in [(10, "preflop"), (11, "flop"), (12, "turn"), (13, "river")]:
                if hand[key]:
                    self.table.setCellWidget(r, col, _RichLabel(_action_html(hand[key])))
                else:
                    self.table.setItem(r, col, _muted_item(""))
            # Pot
            self.table.setItem(r, 14, _num_item(hand["pot"], "#E5E7EB"))
            # Win/Loss
            color = "#10B981" if hand["win_loss"] >= 0 else "#EF4444"
            self.table.setItem(r, 15, _num_item(hand["win_loss"], color, signed=True))
            # EV Loss
            self.table.setItem(r, 16, _num_item(hand["ev_loss"], "#F59E0B" if hand["ev_loss"] > 0 else "#10B981"))

        self._update_footer(rows)

    def _update_footer(self, rows: list[dict[str, Any]]) -> None:
        n = len(rows)
        pot_sum = sum(h["pot"] for h in rows)
        win_sum = sum(h["win_loss"] for h in rows)
        ev_sum = sum(h["ev_loss"] for h in rows)
        self.lbl_count.setText(f"{n} hand" + ("" if n == 1 else "s"))
        self.lbl_pot_total.setText(f"{pot_sum:.2f}")
        self.lbl_win_total.setText(f"{win_sum:+.2f}")
        self.lbl_win_total.setObjectName("Green" if win_sum >= 0 else "Red")
        self.lbl_ev_total.setText(f"{ev_sum:.2f}")

    def _on_row_clicked(self, row: int, _col: int) -> None:
        rows = self.table.property("rows") or []
        if row >= len(rows):
            return
        hand = rows[row]
        self.coach_message.emit(
            f"Selected {hand['id']}: {hand['hand']} {hand['position']} {hand['format']} | "
            f"Pot {hand['pot']:.2f}bb | Win/Loss {hand['win_loss']:+.2f}bb | "
            f"EV loss {hand['ev_loss']:.2f}bb. Detaylı analiz için Hand History Analyzer'a geç."
        )

    # --- filters ---------------------------------------------------------
    def _render_active_filters(self) -> None:
        for w in self._active_filter_widgets:
            self.active_filter_row.removeWidget(w)
            w.deleteLater()
        self._active_filter_widgets.clear()
        # Insert each chip after the "Active Filters" label (index 0)
        for i, (key, value) in enumerate(self.active_filters.items()):
            chip = FilterChip(key, value)
            chip.removed.connect(self._remove_filter)
            self.active_filter_row.insertWidget(1 + i, chip)
            self._active_filter_widgets.append(chip)

    def _remove_filter(self, key: str) -> None:
        self.active_filters.pop(key, None)
        self._render_active_filters()
        self._populate()

    def _clear_filters(self) -> None:
        self.active_filters.clear()
        self._render_active_filters()
        self._populate()


def _plain_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QColor("#E5E7EB"))
    return item


def _muted_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setForeground(QColor("#8B95A7"))
    return item


def _num_item(value: float, color: str, signed: bool = False) -> QTableWidgetItem:
    text = (f"{value:+.2f}" if signed else f"{value:.2f}")
    item = QTableWidgetItem(text)
    item.setForeground(QColor(color))
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return item


def _wrap_center(widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch(1)
    layout.addWidget(widget)
    layout.addStretch(1)
    return box


def _wrap_left(widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(6, 0, 0, 0)
    layout.addWidget(widget)
    layout.addStretch(1)
    return box
