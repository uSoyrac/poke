"""GTO Wizard-style drill builder: pick positions on an oval table, choose solutions and starting spot, then START TRAINING."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
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
        self.drill_list.addItems([
            "Untitled drill 1",
        ])
        self.drill_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; color: #E5E7EB; }"
            "QListWidget::item { padding: 8px 6px; }"
            "QListWidget::item:selected { background: #1B2A3D; color: #22D3EE; border-radius: 4px; }"
        )
        side_layout.addWidget(self.drill_list, 1)
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

        layout.addWidget(right, 1)
        self._update_badge()
        self._on_selection_changed(set())

    # --- helpers ---------------------------------------------------------
    def _switch_tab(self, which: str) -> None:
        self.tab_my.setChecked(which == "my")
        self.tab_gto.setChecked(which == "gto")
        self.drill_list.clear()
        if which == "my":
            self.drill_list.addItems(["Untitled drill 1"])
        else:
            self.drill_list.addItems([
                "BTN vs BB SRP — Wet boards",
                "BB Defense vs CO 2.5x",
                "SB Opening — 100bb",
                "EP vs IP 3Bet — NL50",
                "PKO 25bb jam/fold",
                "Final table ICM",
            ])

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
