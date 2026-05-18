"""GTO Study Library — GTO Wizard-style spot browser.

Layout:
  ┌──────────────────────────────────────────────────────────────┐
  │ [All] [Tournaments 8-Max] [Cash Games 8-Max] [ICM] [Explo]  │
  │ [All] [Preflop] [Postflop]                                   │
  ├──────────────────┬───────────────────────────────────────────┤
  │  Name            │  Type   │  Hands  │  EV                  │  ← header
  │  ─ category ─    │                                           │
  │  25bb LJ RFI … │  MTT    │   43    │  -147.8               │
  └──────────────────┴───────────────────────────────────────────┘
       selected spot detail panel on right
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills, get_spot_categories
from app.solver.mock_solver import solve_spot
from app.solver.preflop_charts import chart_for_spot, hand_169_from_cards
from app.ui.components.range_grid import RangeGrid
from app.ui.components.range_matrix import RangeMatrix
from app.ui.components.solver_bar import SolverFrequencyBar

# colours
_C_BG     = "#0C1117"
_C_CARD   = "#131A24"
_C_BORDER = "#1E2733"
_C_MUTED  = "#6B7280"
_C_TEXT   = "#E5E7EB"
_C_CYAN   = "#22D3EE"
_C_GREEN  = "#10B981"
_C_RED    = "#EF4444"
_C_AMBER  = "#F59E0B"

FORMAT_TAGS = [
    ("All",               "All"),
    ("Tournaments 8-Max", "Tournaments 8-Max"),
    ("Cash Games 8-Max",  "Cash Games 8-Max"),
    ("Tournaments ICM",   "Tournaments ICM"),
    ("Tournaments Explo", "Tournaments Explo"),
    ("Cash Games Explo",  "Cash Games Explo"),
    ("Cash Games 6-Max",  "Cash Games 6-Max"),
]

RANGE_MODE_BY_POSITION = {
    "UTG": "RFI", "LJ": "RFI", "HJ": "RFI",
    "CO": "RFI",  "BTN": "BTN steal",
    "SB": "SB strategy", "BB": "BB defend",
}


def _tab_style(active: bool, small: bool = False) -> str:
    h = "26px" if small else "30px"
    pad = "4px 12px" if small else "5px 16px"
    fs = "11px" if small else "12px"
    if active:
        return (
            f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:7px;"
            f"font-weight:700;font-size:{fs};padding:{pad};border:none;}}"
        )
    return (
        f"QPushButton{{background:{_C_CARD};color:{_C_MUTED};border-radius:7px;"
        f"font-weight:500;font-size:{fs};padding:{pad};"
        f"border:1px solid {_C_BORDER};}}"
        f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_TEXT};}}"
    )


class StudyLibraryScreen(QWidget):
    coach_message    = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state   = state
        self.spots   = generate_spot_drills(120)
        self.current = self.spots[0]
        self._fmt_filter    = "All"
        self._street_filter = "All"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top filter bar ───────────────────────────────────────────────
        top_bar = QFrame()
        top_bar.setStyleSheet(f"background:{_C_CARD};border-bottom:1px solid {_C_BORDER};")
        top_vbox = QVBoxLayout(top_bar)
        top_vbox.setContentsMargins(12, 8, 12, 8)
        top_vbox.setSpacing(6)

        # Row 1: format tabs
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(6)
        self._fmt_btns: dict[str, QPushButton] = {}
        for label, tag in FORMAT_TAGS:
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.setCheckable(True)
            b.setChecked(tag == "All")
            b.clicked.connect(lambda _, t=tag: self._set_fmt(t))
            b.setStyleSheet(_tab_style(tag == "All"))
            self._fmt_btns[tag] = b
            fmt_row.addWidget(b)
        fmt_row.addStretch(1)
        top_vbox.addLayout(fmt_row)

        # Row 2: street tabs
        street_row = QHBoxLayout()
        street_row.setSpacing(6)
        self._street_btns: dict[str, QPushButton] = {}
        for tag in ["All", "Preflop", "Postflop"]:
            b = QPushButton(tag)
            b.setFixedHeight(26)
            b.setCheckable(True)
            b.setChecked(tag == "All")
            b.clicked.connect(lambda _, t=tag: self._set_street(t))
            b.setStyleSheet(_tab_style(tag == "All", small=True))
            self._street_btns[tag] = b
            street_row.addWidget(b)
        street_row.addStretch(1)
        top_vbox.addLayout(street_row)

        root.addWidget(top_bar)

        # ── Splitter: list | detail ──────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle{background:#1E2733;}")

        # ── LEFT: spot list ──────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(340)
        left_v = QVBoxLayout(left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(0)

        # Column header
        col_hdr = QFrame()
        col_hdr.setFixedHeight(32)
        col_hdr.setStyleSheet(f"background:#0C1117;border-bottom:1px solid {_C_BORDER};")
        ch = QHBoxLayout(col_hdr)
        ch.setContentsMargins(12, 0, 12, 0)
        for txt, stretch in [("Name", 4), ("Type", 1), ("Hands", 1), ("EV", 1)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(f"color:{_C_MUTED};font-size:11px;font-weight:700;")
            if stretch > 1:
                lbl.setSizePolicy(lbl.sizePolicy().horizontalPolicy(), lbl.sizePolicy().verticalPolicy())
            ch.addWidget(lbl, stretch)
        left_v.addWidget(col_hdr)

        # Scroll list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{_C_BG};}}"
            "QScrollBar:vertical{width:6px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:3px;}"
        )
        self._list_container = QWidget()
        self._list_container.setStyleSheet(f"background:{_C_BG};")
        self._list_vbox = QVBoxLayout(self._list_container)
        self._list_vbox.setContentsMargins(0, 0, 0, 0)
        self._list_vbox.setSpacing(0)
        scroll.setWidget(self._list_container)
        left_v.addWidget(scroll, 1)
        splitter.addWidget(left)

        # ── RIGHT: detail panel ──────────────────────────────────────────
        right = QWidget()
        right_v = QVBoxLayout(right)
        right_v.setContentsMargins(20, 20, 20, 20)
        right_v.setSpacing(12)

        self.node_title = QLabel()
        self.node_title.setObjectName("SectionTitle")
        self.node_title.setWordWrap(True)

        self.node_meta = QLabel()
        self.node_meta.setWordWrap(True)
        self.node_meta.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")

        self.solver_frame = QFrame()
        self.solver_layout = QGridLayout(self.solver_frame)
        self.solver_layout.setSpacing(6)

        # Action buttons
        btn_row = QHBoxLayout()
        for label, action in [
            ("▶ Practice this spot", "practice"),
            ("💬 Ask coach why",      "coach"),
            ("📋 Add to drill pack",  "pack"),
            ("🔍 Compare my hands",   "compare"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(36)
            if action == "practice":
                b.setStyleSheet(
                    f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:8px;"
                    "font-weight:700;font-size:13px;padding:4px 16px;border:none;}"
                    f"QPushButton:hover{{background:#06B6D4;}}"
                )
                b.clicked.connect(self._launch_practice)
            elif action == "coach":
                b.setStyleSheet(
                    f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
                    "border-radius:8px;font-size:13px;padding:4px 14px;}"
                    f"QPushButton:hover{{border-color:{_C_CYAN};}}"
                )
                b.clicked.connect(lambda: self.coach_message.emit(explain_spot(self.current)))
            else:
                b.setStyleSheet(
                    f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
                    "border-radius:8px;font-size:13px;padding:4px 14px;}"
                    f"QPushButton:hover{{border-color:{_C_CYAN};}}"
                )
                if action == "compare":
                    b.clicked.connect(lambda: self.navigate_requested.emit("Hand History Analyzer"))
                else:
                    b.clicked.connect(lambda: self.coach_message.emit("Drill pack'e eklendi."))
            btn_row.addWidget(b)

        # Range matrix — real 13x13 grid driven by pre-solved chart
        self.range_matrix = RangeMatrix()

        right_v.addWidget(self.node_title)
        right_v.addWidget(self.node_meta)
        right_v.addWidget(self.solver_frame)
        right_v.addLayout(btn_row)
        right_v.addWidget(QLabel("GTO Range"))
        right_v.addWidget(self.range_matrix, 1)
        splitter.addWidget(right)

        splitter.setSizes([420, 700])
        root.addWidget(splitter, 1)

        self._rebuild_list()
        self.render_current()

    # ── filter handlers ──────────────────────────────────────────────────
    def _set_fmt(self, tag: str) -> None:
        self._fmt_filter = tag
        for t, b in self._fmt_btns.items():
            b.setChecked(t == tag)
            b.setStyleSheet(_tab_style(t == tag))
        self._rebuild_list()

    def _set_street(self, tag: str) -> None:
        self._street_filter = tag
        for t, b in self._street_btns.items():
            b.setChecked(t == tag)
            b.setStyleSheet(_tab_style(t == tag, small=True))
        self._rebuild_list()

    def _filtered_spots(self) -> list[dict]:
        result = self.spots
        if self._fmt_filter != "All":
            ft = self._fmt_filter
            result = [s for s in result if s.get("format_tag") == ft]
        if self._street_filter == "Preflop":
            result = [s for s in result if s.get("street") == "preflop"]
        elif self._street_filter == "Postflop":
            result = [s for s in result if s.get("street") != "preflop"]
        return result

    # ── list rebuild ─────────────────────────────────────────────────────
    def _rebuild_list(self) -> None:
        _clear_layout(self._list_vbox)
        spots = self._filtered_spots()

        # Group by category
        cats: dict[str, list[dict]] = {}
        for s in spots:
            cat = s.get("category", "General Spots")
            cats.setdefault(cat, []).append(s)

        current_id = self.current.get("id") if self.current else None
        for cat, items in cats.items():
            # Category header row
            hdr = QLabel(cat)
            hdr.setFixedHeight(28)
            hdr.setStyleSheet(
                f"QLabel{{background:#0C1117;color:{_C_MUTED};font-size:11px;font-weight:700;"
                "padding:4px 12px;border-bottom:1px solid #1E2733;}"
            )
            self._list_vbox.addWidget(hdr)
            for spot in items:
                is_active = (spot.get("id") == current_id)
                row = _SpotRow(spot, is_active=is_active)
                row.clicked.connect(lambda s=spot: self._pick(s))
                self._list_vbox.addWidget(row)

        self._list_vbox.addStretch(1)

    def _pick(self, spot: dict) -> None:
        self.current = spot
        self.state.selected_spot = spot
        self._rebuild_list()
        self.render_current()

    # ── detail panel ─────────────────────────────────────────────────────
    def render_current(self) -> None:
        spot = self.current
        self.state.selected_spot = spot
        name  = spot.get("name") or spot.get("title", spot.get("id", ""))
        stack = spot.get("stack_bb", 40)
        fmt   = spot.get("format", "MTT")
        table = spot.get("table", "8-max")
        pos   = spot.get("position", "BTN")
        pt    = spot.get("pot_type", "SRP")
        street= spot.get("street", "preflop")
        tex   = spot.get("board_texture", "")
        icm   = spot.get("icm", "off")

        self.node_title.setText(name)
        self.node_meta.setText(
            f"{fmt}  ·  {table}  ·  {stack}bb effective  ·  {pos}  ·  {pt}  ·  {street}"
            + (f"  ·  {tex}" if tex and street != "preflop" else "")
            + (f"  ·  ICM: {icm}" if icm and icm != "off" else "")
        )

        # Solver bars
        _clear_layout(self.solver_layout)
        sol = solve_spot(spot)
        for idx, act in enumerate(sol.actions):
            bar = SolverFrequencyBar(act.action, act.frequency, act.ev, act.sizing)
            self.solver_layout.addWidget(bar, idx // 2, idx % 2)

        # Range matrix — updates per selected spot
        chart = chart_for_spot(spot)
        self.range_matrix.set_strategy(chart)
        h169 = hand_169_from_cards(spot.get("hero_cards", ""))
        if h169:
            self.range_matrix.highlight_hand(h169)

    def _launch_practice(self) -> None:
        spot = self.current
        self.state.drill_filters = {
            "positions":     [spot.get("position", "BTN")],
            "solution":      "MTT • ChipEV",
            "starting_spot": spot.get("street", "Flop").title(),
            "preflop_action":spot.get("pot_type", "Any"),
        }
        self.navigate_requested.emit("Spot Practice Trainer")

    def select_first_match(self) -> None:
        matches = self._filtered_spots()
        if matches:
            self.current = matches[0]
            self.state.selected_spot = self.current
            self._rebuild_list()
            self.render_current()


# ── spot row widget ───────────────────────────────────────────────────────

class _SpotRow(QFrame):
    clicked = Signal()

    def __init__(self, spot: dict, is_active: bool = False):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(0)

        name = spot.get("name") or spot.get("title", spot.get("id", ""))
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{'#E5E7EB' if is_active else '#C9D1DC'};"
            f"font-size:13px;font-weight:{'700' if is_active else '400'};"
        )
        h.addWidget(name_lbl, 4)

        # Type chip
        fmt_tag = spot.get("format_tag", spot.get("format", "MTT"))
        short   = "MTT" if "Tourn" in fmt_tag else "Cash"
        type_lbl = QLabel(short)
        type_lbl.setAlignment(Qt.AlignCenter)
        type_lbl.setFixedWidth(44)
        type_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        h.addWidget(type_lbl, 0)

        played = spot.get("hands_played", 0)
        ev     = spot.get("ev_delta", 0.0)

        if played:
            p_lbl = QLabel(str(played))
            p_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            p_lbl.setFixedWidth(44)
            p_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
            h.addWidget(p_lbl, 0)

            color = _C_GREEN if ev >= 0 else _C_RED
            sign  = "+" if ev >= 0 else ""
            ev_lbl = QLabel(f"{sign}{ev:.1f}")
            ev_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ev_lbl.setFixedWidth(60)
            ev_lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:700;")
            h.addWidget(ev_lbl, 0)
        else:
            dash = QLabel("—")
            dash.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            dash.setFixedWidth(104)
            dash.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
            h.addWidget(dash, 0)

        if is_active:
            self.setStyleSheet(
                f"QFrame{{background:#1B2D4A;border-left:3px solid {_C_CYAN};}}"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{background:transparent;border-left:3px solid transparent;}}"
                f"QFrame:hover{{background:#131A24;border-left:3px solid {_C_BORDER};}}"
            )

    def mousePressEvent(self, event):  # type: ignore[override]
        self.clicked.emit()
        super().mousePressEvent(event)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w  = item.widget()
        cl = item.layout()
        if w:  w.deleteLater()
        if cl: _clear_layout(cl)
