"""GTO Wizard-style drill builder: pick positions on an oval table, choose solutions and starting spot, then START TRAINING."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QColor

from app.core.app_state import AppState
from app.db.repository import delete_drill_pack, list_drill_packs, save_drill_pack
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, OvalTable


SOLUTIONS = [
    ("MTT • ChipEV", 21),
    ("MTT • ICM", 18),
    ("Cash 100bb", 14),
    ("Cash 200bb deep", 9),
    ("Spin & Go 25bb", 7),
    ("HU SnG", 12),
    ("PKO bounty", 11),
]

PREFLOP_ACTIONS = ["Any", "SRP", "3-bet", "4-bet", "5-bet", "Squeeze", "Limp", "Iso"]
STARTING_SPOTS = ["Preflop", "Flop", "Turn", "River", "Custom"]

TRAINING_PACKS = [
    {"name": "Bread & Butter MTT Spots (Common)", "type": "MTT", "street": "All", "hands": None, "elo": None, "group": True},
    {"name": "25bb LJ RFI vs BB", "type": "MTT", "street": "Preflop", "hands": None, "elo": None},
    {"name": "25bb BTN vs LJ RFI", "type": "MTT", "street": "Preflop", "hands": 46, "elo": -23.7},
    {"name": "25bb LJ RFI vs BTN", "type": "MTT", "street": "Preflop", "hands": 43, "elo": -147.8},
    {"name": "40bb BTN vs LJ RFI", "type": "MTT", "street": "Preflop", "hands": 218, "elo": 297.0},
    {"name": "40bb LJ RFI vs BTN", "type": "MTT", "street": "Preflop", "hands": 57, "elo": -15.2},
    {"name": "40bb BB vs LJ RFI", "type": "MTT", "street": "Preflop", "hands": 7, "elo": -13.5},
    {"name": "40bb LJ RFI vs BB", "type": "MTT", "street": "Preflop", "hands": 297, "elo": -80.8},
    {"name": "Board Specific Training MTT", "type": "MTT", "street": "Postflop", "hands": None, "elo": None, "group": True},
    {"name": "Playing Dry Boards", "type": "MTT", "street": "Postflop", "hands": 104, "elo": -116.7},
    {"name": "Playing Connected Boards", "type": "MTT", "street": "Postflop", "hands": 19, "elo": 114.1},
    {"name": "3Bet Pot OOP Survival", "type": "Cash 6-Max", "street": "Postflop", "hands": 88, "elo": -44.0},
    {"name": "Cash 100bb BTN vs BB SRP", "type": "Cash 6-Max", "street": "Postflop", "hands": 162, "elo": 61.4},
    {"name": "Tournament Bubble Call/Fold", "type": "Tournament ICM", "street": "Preflop", "hands": 73, "elo": -92.5},
    {"name": "PKO Bounty Jam/Call", "type": "Tournament Explo", "street": "Preflop", "hands": 55, "elo": 18.6},
    {"name": "River Bluffcatch MDF", "type": "Cash Games Explo", "street": "Postflop", "hands": 91, "elo": -64.2},
]


def _positions_from_pack(name: str) -> list[str]:
    """Infer seat filters from a pack title like '40bb BTN vs LJ RFI'."""
    aliases = {
        "UTG+1": "UTG1",
        "UTG1": "UTG1",
        "UTG": "UTG",
        "LJ": "LJ",
        "HJ": "HJ",
        "CO": "CO",
        "BTN": "BTN",
        "BU": "BTN",
        "SB": "SB",
        "BB": "BB",
    }
    positions: list[str] = []
    for token in name.replace("-", " ").replace("/", " ").split():
        normalized = aliases.get(token.upper())
        if normalized and normalized not in positions:
            positions.append(normalized)
    return positions or ["BTN", "BB"]


def _starting_spot_from_pack_street(street: str) -> str:
    if street == "Postflop":
        return "Flop"
    if street in STARTING_SPOTS:
        return street
    return "Preflop"


class PillToggleButton(QPushButton):
    """Pill-shaped toggle button used for action filters and starting spots."""

    def __init__(self, text: str, active: bool = False):
        super().__init__(text)
        self.setCheckable(True)
        self.setChecked(active)
        self.setCursor(Qt.PointingHandCursor)
        self._refresh()
        self.toggled.connect(lambda _: self._refresh())

    def _refresh(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                "QPushButton { background: #1B2A3D; border: 1px solid #22D3EE; "
                "border-radius: 14px; padding: 6px 14px; color: #22D3EE; font-weight: 700; }"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius: 14px; padding: 6px 14px; color: #8B95A7; font-weight: 600; }"
                "QPushButton:hover { color: #E5E7EB; border-color: #2A3647; }"
            )


class DrillBuilderScreen(QWidget):
    """Compose a drill set by picking positions, solution flavour, starting spot, and preflop action."""

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

        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left sidebar: My Drills / GTO Wizard Drills tabs + saved drill packs
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(14, 18, 14, 14)
        side_layout.setSpacing(10)

        title_row = QHBoxLayout()
        crosshair = QLabel("◎")
        crosshair.setStyleSheet("color: #8B95A7; font-size: 16px;")
        sb_title = QLabel("Drills")
        sb_title.setObjectName("SectionTitle")
        title_row.addWidget(crosshair)
        title_row.addWidget(sb_title)
        title_row.addStretch(1)
        side_layout.addLayout(title_row)

        tabs = QHBoxLayout()
        self.tab_my = QPushButton("My Drills")
        self.tab_gto = QPushButton("GTO Wizard Drills")
        for btn in (self.tab_my, self.tab_gto):
            btn.setCheckable(True)
            btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; padding: 6px 8px; "
                "color: #8B95A7; font-weight: 600; }"
                "QPushButton:checked { color: #E5E7EB; border-bottom: 2px solid #22D3EE; }"
            )
        self.tab_my.setChecked(True)
        self.tab_my.clicked.connect(lambda: self._switch_tab("my"))
        self.tab_gto.clicked.connect(lambda: self._switch_tab("gto"))
        tabs.addWidget(self.tab_my)
        tabs.addWidget(self.tab_gto)
        tabs.addStretch(1)
        side_layout.addLayout(tabs)

        self.drill_list = QListWidget()
        self.drill_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; color: #E5E7EB; }"
            "QListWidget::item { padding: 8px 6px; }"
            "QListWidget::item:selected { background: #1B2A3D; color: #22D3EE; border-radius: 4px; }"
        )
        self.drill_list.itemClicked.connect(self._on_pack_picked)
        side_layout.addWidget(self.drill_list, 1)

        # Save / delete buttons under the list (only visible on My Drills)
        sidebar_actions = QHBoxLayout()
        self.save_pack_btn = QPushButton("💾 Save")
        self.save_pack_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 700; "
            "padding: 6px 10px; border-radius: 6px; border: none; }"
            "QPushButton:hover { background: #34D399; }"
        )
        self.save_pack_btn.clicked.connect(self._save_pack)
        self.delete_pack_btn = QPushButton("🗑")
        self.delete_pack_btn.setStyleSheet(
            "QPushButton { background: #131A24; border: 1px solid #1E2733; "
            "color: #EF4444; padding: 6px 10px; border-radius: 6px; }"
            "QPushButton:hover { border-color: #EF4444; }"
        )
        self.delete_pack_btn.clicked.connect(self._delete_pack)
        sidebar_actions.addWidget(self.save_pack_btn, 1)
        sidebar_actions.addWidget(self.delete_pack_btn)
        side_layout.addLayout(sidebar_actions)
        layout.addWidget(side)

        # Right side: oval table + controls + start button
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(28, 22, 28, 22)
        right_layout.setSpacing(18)

        # Oval table with selectable positions
        self.table = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=True)
        self.table.set_dealer("BTN")
        self.table.set_community_cards(["W", "W", "W", "W", "W"])
        self.table.selection_changed.connect(self._on_selection_changed)
        right_layout.addWidget(self.table, 1)

        # Solutions dropdown
        sol_row = QVBoxLayout()
        sol_row.setAlignment(Qt.AlignCenter)
        sol_label = QLabel("Solutions")
        sol_label.setObjectName("Muted")
        sol_label.setAlignment(Qt.AlignCenter)
        sol_row.addWidget(sol_label)

        sol_inline = QHBoxLayout()
        sol_inline.setAlignment(Qt.AlignCenter)
        self.solution = QComboBox()
        for label, count in SOLUTIONS:
            self.solution.addItem(label, count)
        self.solution.setMinimumWidth(220)
        self.badge = QLabel("21")
        self.badge.setStyleSheet(
            "background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 3px 9px; border-radius: 11px;"
        )
        gear = QLabel("⚙")
        gear.setStyleSheet("color: #8B95A7; font-size: 16px;")
        sol_inline.addStretch(1)
        sol_inline.addWidget(self.solution)
        sol_inline.addWidget(self.badge)
        sol_inline.addWidget(gear)
        sol_inline.addStretch(1)
        sol_row.addLayout(sol_inline)
        self.solution.currentIndexChanged.connect(self._update_badge)
        right_layout.addLayout(sol_row)

        # Starting spot toggle
        ss_label = QLabel("Starting spot")
        ss_label.setObjectName("Muted")
        ss_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(ss_label)
        self.starting_buttons = QButtonGroup(self)
        self.starting_buttons.setExclusive(True)
        ss_row = QHBoxLayout()
        ss_row.setAlignment(Qt.AlignCenter)
        for i, label in enumerate(STARTING_SPOTS):
            btn = PillToggleButton(label, active=(label == "Flop"))
            self.starting_buttons.addButton(btn, i)
            ss_row.addWidget(btn)
        right_layout.addLayout(ss_row)

        # Preflop action filter
        pa_label = QLabel("Preflop action")
        pa_label.setObjectName("Muted")
        pa_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(pa_label)
        self.preflop_buttons = QButtonGroup(self)
        self.preflop_buttons.setExclusive(True)
        pa_row = QHBoxLayout()
        pa_row.setAlignment(Qt.AlignCenter)
        for i, label in enumerate(PREFLOP_ACTIONS):
            btn = PillToggleButton(label, active=(label == "Any"))
            self.preflop_buttons.addButton(btn, i)
            pa_row.addWidget(btn)
        right_layout.addLayout(pa_row)

        # Action row: ALL SETTINGS + START TRAINING
        actions = QHBoxLayout()
        actions.setAlignment(Qt.AlignCenter)
        actions.setSpacing(20)
        all_settings = QPushButton("⚙  ALL SETTINGS")
        all_settings.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #10B981; "
            "font-weight: 700; padding: 10px 14px; }"
            "QPushButton:hover { color: #34D399; }"
        )
        all_settings.clicked.connect(
            lambda: self.coach_message.emit(
                "Tüm ayarlar paneli — RNG, sizing, board filter ve solver çapı yakında bu modülde."
            )
        )
        self.start_btn = QPushButton("▶  START TRAINING")
        self.start_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 12px 26px; border-radius: 8px; border: none; letter-spacing: 0.4px; }"
            "QPushButton:hover { background: #34D399; }"
            "QPushButton:disabled { background: #1F3D24; color: #4B5563; }"
        )
        self.start_btn.clicked.connect(self._start_training)
        actions.addWidget(all_settings)
        actions.addWidget(self.start_btn)
        right_layout.addLayout(actions)

        self.summary = QLabel("Tıklayarak çalışacağın pozisyonları seç. En az 1 pozisyon seçili olmalı.")
        self.summary.setObjectName("Muted")
        self.summary.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.summary)

        library = QFrame()
        library.setObjectName("Card")
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(16, 14, 16, 16)
        library_layout.setSpacing(10)

        library_header = QHBoxLayout()
        library_title = QLabel("Training Pack Library")
        library_title.setObjectName("SectionTitle")
        library_header.addWidget(library_title)
        library_header.addStretch(1)

        # Format filter
        self.pack_format_filter = QComboBox()
        self.pack_format_filter.addItems([
            "All",
            "Tournaments 8-Max",
            "Cash Games 8-Max",
            "Tournaments ICM",
            "Tournaments Explo",
            "Cash Games Explo",
            "Cash Games 6-Max",
        ])
        library_header.addWidget(QLabel("Type:"))
        library_header.addWidget(self.pack_format_filter)

        # Street filter
        self.pack_street_filter = QComboBox()
        self.pack_street_filter.addItems(["All", "Preflop", "Postflop"])
        library_header.addWidget(QLabel("Street:"))
        library_header.addWidget(self.pack_street_filter)

        # Elo filter
        self.pack_elo_filter = QComboBox()
        self.pack_elo_filter.addItems(["All", "Positive Elo", "Negative Elo", "High Impact (>50)", "Low Impact (<-50)"])
        library_header.addWidget(QLabel("Elo:"))
        library_header.addWidget(self.pack_elo_filter)

        # Hands filter
        self.pack_hands_filter = QComboBox()
        self.pack_hands_filter.addItems(["All", "50+ hands", "100+ hands", "200+ hands"])
        library_header.addWidget(QLabel("Hands:"))
        library_header.addWidget(self.pack_hands_filter)

        library_layout.addLayout(library_header)

        self.training_library = QTableWidget(0, 4)
        self.training_library.setHorizontalHeaderLabels(["Name", "Type", "Hands", "Elo"])
        self.training_library.verticalHeader().setVisible(False)
        self.training_library.setShowGrid(False)
        self.training_library.setAlternatingRowColors(True)
        self.training_library.setSelectionBehavior(QTableWidget.SelectRows)
        self.training_library.setEditTriggers(QTableWidget.NoEditTriggers)
        self.training_library.setMinimumHeight(260)
        self.training_library.setColumnWidth(0, 420)
        self.training_library.setColumnWidth(1, 140)
        self.training_library.setColumnWidth(2, 80)
        self.training_library.setColumnWidth(3, 80)
        self.training_library.setStyleSheet(
            "QTableWidget { background: #111827; border: 1px solid #2D3748; border-radius: 8px; "
            "color: #E5E7EB; alternate-background-color: #0F151D; }"
            "QHeaderView::section { background: #1F2937; color: #E5E7EB; border: none; "
            "padding: 8px; font-weight: 800; }"
            "QTableWidget::item { padding: 7px; border-bottom: 1px solid #2D3748; }"
            "QTableWidget::item:selected { background: #1B2A3D; color: #22D3EE; }"
        )
        self.training_library.cellClicked.connect(self._on_training_pack_selected)
        self.training_library.cellDoubleClicked.connect(self._start_training_from_pack)
        library_layout.addWidget(self.training_library)

        hint = QLabel("Tek tık: pack filtrelerini yükler. Çift tık: Spot Practice Trainer'da başlatır.")
        hint.setObjectName("Muted")
        library_layout.addWidget(hint)
        right_layout.addWidget(library)

        layout.addWidget(right, 1)
        self._update_badge()
        self._on_selection_changed(set())
        self._populate_my_drills()
        self.pack_format_filter.currentTextChanged.connect(self._populate_training_library)
        self.pack_street_filter.currentTextChanged.connect(self._populate_training_library)
        self.pack_elo_filter.currentTextChanged.connect(self._populate_training_library)
        self.pack_hands_filter.currentTextChanged.connect(self._populate_training_library)
        self._populate_training_library()

    # --- helpers ---------------------------------------------------------
    def _switch_tab(self, which: str) -> None:
        self.tab_my.setChecked(which == "my")
        self.tab_gto.setChecked(which == "gto")
        self.drill_list.clear()
        if which == "my":
            self.save_pack_btn.setVisible(True)
            self.delete_pack_btn.setVisible(True)
            self._populate_my_drills()
        else:
            self.save_pack_btn.setVisible(False)
            self.delete_pack_btn.setVisible(False)
            for name in [
                "BTN vs BB SRP — Wet boards",
                "BB Defense vs CO 2.5x",
                "SB Opening — 100bb",
                "EP vs IP 3Bet — NL50",
                "PKO 25bb jam/fold",
                "Final table ICM",
            ]:
                item = QListWidgetItem(name)
                self.drill_list.addItem(item)

    def _populate_my_drills(self) -> None:
        """Load saved drill packs from DB into the sidebar list."""
        self.drill_list.clear()
        try:
            packs = list_drill_packs()
        except Exception:
            packs = []
        if not packs:
            placeholder = QListWidgetItem("(no saved drills — click 💾 Save to add one)")
            placeholder.setData(Qt.UserRole, None)
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsSelectable)
            self.drill_list.addItem(placeholder)
            return
        for pack in packs:
            label = pack.get("name") or f"Pack #{pack['id']}"
            n_pos = len(pack.get("positions", []))
            item = QListWidgetItem(f"{label}  ·  {n_pos} pos  ·  {pack.get('starting_spot', '')}")
            item.setData(Qt.UserRole, pack)
            self.drill_list.addItem(item)

    def _on_pack_picked(self, item: QListWidgetItem) -> None:
        pack = item.data(Qt.UserRole)
        if not isinstance(pack, dict):
            return
        # Restore the GUI to this pack's filter state
        self._apply_positions_to_table(pack.get("positions", []))
        # Update solution combo
        sol_text = pack.get("solution", "")
        idx = self.solution.findText(sol_text)
        if idx >= 0:
            self.solution.setCurrentIndex(idx)
        # Starting spot pill
        target_ss = (pack.get("starting_spot", "") or "").title() or "Flop"
        for btn in self.starting_buttons.buttons():
            btn.setChecked(btn.text() == target_ss)
        # Preflop action pill
        target_pa = pack.get("preflop_action", "") or "Any"
        for btn in self.preflop_buttons.buttons():
            btn.setChecked(btn.text() == target_pa)
        self.coach_message.emit(
            f"Drill pack '{pack.get('name', '?')}' yüklendi. ▶ START TRAINING ile çalışmaya başlayabilirsin."
        )

    def _apply_positions_to_table(self, positions: list[str]) -> None:
        selected = set(positions)
        for pos, seat in self.table.seats.items():
            seat.selected = pos in selected
        self.table.update()
        self.table.selection_changed.emit(self.table.selection())

    def _filtered_training_packs(self) -> list[dict]:
        format_filter = self.pack_format_filter.currentText()
        street_filter = self.pack_street_filter.currentText()
        elo_filter = self.pack_elo_filter.currentText()
        hands_filter = self.pack_hands_filter.currentText()

        def matches_format(pack: dict) -> bool:
            if format_filter == "All":
                return True
            pack_type = pack.get("type", "")
            if format_filter == "Tournaments 8-Max":
                return pack_type == "MTT"
            if format_filter == "Cash Games 8-Max":
                return pack_type.startswith("Cash")
            if format_filter == "Tournaments ICM":
                return pack_type == "Tournament ICM"
            if format_filter == "Tournaments Explo":
                return pack_type == "Tournament Explo"
            if format_filter == "Cash Games Explo":
                return pack_type == "Cash Games Explo"
            if format_filter == "Cash Games 6-Max":
                return pack_type == "Cash 6-Max"
            return True

        def matches_street(pack: dict) -> bool:
            return street_filter == "All" or pack.get("street") in {street_filter, "All"}

        def matches_elo(pack: dict) -> bool:
            if elo_filter == "All":
                return True
            elo = pack.get("elo")
            if elo is None:
                return False
            if elo_filter == "Positive Elo":
                return elo >= 0
            if elo_filter == "Negative Elo":
                return elo < 0
            if elo_filter == "High Impact (>50)":
                return elo > 50
            if elo_filter == "Low Impact (<-50)":
                return elo < -50
            return True

        def matches_hands(pack: dict) -> bool:
            if hands_filter == "All":
                return True
            hands = pack.get("hands")
            if hands is None:
                return False
            if hands_filter == "50+ hands":
                return hands >= 50
            if hands_filter == "100+ hands":
                return hands >= 100
            if hands_filter == "200+ hands":
                return hands >= 200
            return True

        return [pack for pack in TRAINING_PACKS
                if matches_format(pack) and matches_street(pack) and matches_elo(pack) and matches_hands(pack)]

    def _populate_training_library(self) -> None:
        packs = self._filtered_training_packs()
        self.training_library.setRowCount(0)
        for pack in packs:
            row = self.training_library.rowCount()
            self.training_library.insertRow(row)
            if pack.get("group"):
                item = QTableWidgetItem(pack["name"])
                item.setData(Qt.UserRole, pack)
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                item.setForeground(QColor("#C7CED8"))
                item.setBackground(QColor("#2B3037"))
                self.training_library.setItem(row, 0, item)
                self.training_library.setSpan(row, 0, 1, 4)
                self.training_library.setRowHeight(row, 34)
                continue

            values = [
                pack["name"],
                pack.get("type", "-"),
                "-" if pack.get("hands") is None else str(pack["hands"]),
                "-" if pack.get("elo") is None else f"{pack['elo']:+.1f}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, pack)
                if column in {2, 3}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column == 3 and pack.get("elo") is not None:
                    item.setForeground(QColor("#10B981" if pack["elo"] >= 0 else "#EF4444"))
                elif column == 0:
                    item.setForeground(QColor("#E5E7EB"))
                else:
                    item.setForeground(QColor("#9CA3AF"))
                self.training_library.setItem(row, column, item)

    def _pack_at_row(self, row: int) -> dict | None:
        item = self.training_library.item(row, 0)
        if item is None:
            return None
        pack = item.data(Qt.UserRole)
        return pack if isinstance(pack, dict) and not pack.get("group") else None

    def _on_training_pack_selected(self, row: int, column: int) -> None:
        pack = self._pack_at_row(row)
        if pack is None:
            return
        positions = _positions_from_pack(pack["name"])
        starting_spot = _starting_spot_from_pack_street(pack.get("street", "Preflop"))
        self._apply_positions_to_table(positions)
        self._set_button_group(self.starting_buttons, starting_spot)
        self._set_button_group(self.preflop_buttons, "Any")
        self.state.drill_filters = {
            "pack_name": pack["name"],
            "positions": positions,
            "solution": pack.get("type", "MTT"),
            "starting_spot": starting_spot,
            "preflop_action": "Any",
        }
        self.coach_message.emit(
            f"{pack['name']} yüklendi — {pack.get('hands') or 0} el, Elo {pack.get('elo', '-')}. "
            "Çift tıkla doğrudan trainer'a geçebilirsin."
        )

    def _start_training_from_pack(self, row: int, column: int) -> None:
        self._on_training_pack_selected(row, column)
        if self._pack_at_row(row) is not None:
            self.navigate_requested.emit("Spot Practice Trainer")

    def _set_button_group(self, group: QButtonGroup, label: str) -> None:
        fallback = "Preflop" if group is self.starting_buttons else "Any"
        target = label if label != "All" else fallback
        for btn in group.buttons():
            btn.setChecked(btn.text() == target)

    def _save_pack(self) -> None:
        positions = sorted(self.table.selection())
        if not positions:
            QMessageBox.warning(self, "Save drill pack",
                                "Önce en az 1 pozisyon seç, sonra kaydet.")
            return
        starting = next(
            (b.text() for b in self.starting_buttons.buttons() if b.isChecked()),
            "Flop",
        )
        preflop = next(
            (b.text() for b in self.preflop_buttons.buttons() if b.isChecked()),
            "Any",
        )
        default_name = f"{', '.join(positions)} · {starting}"
        name, ok = QInputDialog.getText(
            self, "Save drill pack", "Pack name:", text=default_name,
        )
        if not ok or not name.strip():
            return
        new_id = save_drill_pack({
            "name": name.strip(),
            "positions": positions,
            "solution": self.solution.currentText(),
            "starting_spot": starting,
            "preflop_action": preflop,
        })
        if new_id:
            self._populate_my_drills()
            self.coach_message.emit(f"Drill pack '{name.strip()}' kaydedildi (#{new_id}).")
        else:
            QMessageBox.critical(self, "Save failed",
                                 "DB write failed. Check disk permissions.")

    def _delete_pack(self) -> None:
        item = self.drill_list.currentItem()
        if item is None:
            return
        pack = item.data(Qt.UserRole)
        if not isinstance(pack, dict):
            return
        confirm = QMessageBox.question(
            self, "Delete drill pack",
            f"Delete '{pack.get('name', '?')}'? Bu geri alınamaz.",
        )
        if confirm != QMessageBox.Yes:
            return
        if delete_drill_pack(pack["id"]):
            self._populate_my_drills()
            self.coach_message.emit(f"Drill pack '{pack.get('name', '?')}' silindi.")

    def _update_badge(self) -> None:
        count = self.solution.currentData()
        if count is not None:
            self.badge.setText(str(count))

    def _on_selection_changed(self, selection: set) -> None:
        n = len(selection)
        if n == 0:
            self.summary.setText("Tıklayarak çalışacağın pozisyonları seç. En az 1 pozisyon seçili olmalı.")
            self.start_btn.setEnabled(False)
        else:
            positions = ", ".join(sorted(selection))
            self.summary.setText(f"Seçili pozisyonlar: {positions}  ·  Solution: {self.solution.currentText()}")
            self.start_btn.setEnabled(True)

    def _start_training(self) -> None:
        positions = self.table.selection()
        if not positions:
            return
        starting = next(
            (b.text() for b in self.starting_buttons.buttons() if b.isChecked()),
            "Flop",
        )
        preflop = next(
            (b.text() for b in self.preflop_buttons.buttons() if b.isChecked()),
            "Any",
        )
        # Persist filters into AppState so Spot Trainer can pick them up
        self.state.drill_filters = {
            "positions": sorted(positions),
            "solution": self.solution.currentText(),
            "starting_spot": starting,
            "preflop_action": preflop,
        }
        self.coach_message.emit(
            f"Drill başlatıldı — {len(positions)} pozisyon, {starting} starting spot, "
            f"{preflop} preflop. Spot Practice Trainer'a yönlendiriliyorsun."
        )
        self.navigate_requested.emit("Spot Practice Trainer")
