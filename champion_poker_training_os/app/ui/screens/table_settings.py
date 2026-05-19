"""Table & RNG settings — collapsible groups (Table Borders / RNG / Betting Buttons / Actions / Table Info).

Mirrors the GTO Wizard table-customisation panel screenshot. Live preview on the right.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, OvalTable


class CollapsibleGroup(QFrame):
    """Sidebar-style collapsible group with on/off toggle + arrow + child container."""

    def __init__(self, title: str, expanded: bool = False, enabled: bool = True):
        super().__init__()
        self.title = title
        self.expanded = expanded
        self.setStyleSheet(
            "QFrame { background: transparent; border: none; }"
        )
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)

        # Header row: pill toggle + title + arrow
        header = QFrame()
        header.setStyleSheet(
            "QFrame { background: #131A24; border-bottom: 1px solid #1E2733; }"
        )
        header.setCursor(Qt.PointingHandCursor)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 10, 12, 10)
        # Pill toggle (green if enabled)
        self.pill = QPushButton("●")
        self.pill.setCheckable(True)
        self.pill.setChecked(enabled)
        self.pill.setFixedSize(32, 18)
        self.pill.setCursor(Qt.PointingHandCursor)
        self.pill.setStyleSheet(
            "QPushButton { background: #1F2937; border: 1px solid #2A3647; border-radius:0; "
            "color: #4B5563; padding: 0; text-align: left; padding-left: 4px; }"
            "QPushButton:checked { background: #10B981; color: #04110D; "
            "padding-left: 16px; border-color: #10B981; }"
        )
        h_layout.addWidget(self.pill)
        h_layout.addSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color: #E5E7EB; font-weight: 700; font-size: 13px;")
        h_layout.addWidget(title_lbl)
        h_layout.addStretch(1)

        self.arrow = QLabel("˅" if expanded else "›")
        self.arrow.setStyleSheet("color: #8B95A7; font-size: 14px; font-weight: 700;")
        h_layout.addWidget(self.arrow)
        self.outer.addWidget(header)

        # Content body
        self.body = QFrame()
        self.body.setStyleSheet(
            "QFrame { background: #0E141C; border-bottom: 1px solid #1E2733; }"
        )
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(14, 12, 14, 14)
        self.body_layout.setSpacing(10)
        self.outer.addWidget(self.body)
        self.body.setVisible(expanded)

        header.mousePressEvent = lambda _e: self._toggle_expand()

    def _toggle_expand(self) -> None:
        self.expanded = not self.expanded
        self.body.setVisible(self.expanded)
        self.arrow.setText("˅" if self.expanded else "›")

    def add(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)


def _row(label: str, *widgets: QWidget) -> QWidget:
    """Helper: label + widget(s) in a horizontal row."""
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    if label:
        l = QLabel(label)
        l.setObjectName("Muted")
        layout.addWidget(l)
    for w in widgets:
        layout.addWidget(w)
    layout.addStretch(1)
    return box


class TableSettingsScreen(QWidget):
    coach_message = Signal(str)

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        title_bar = QFrame()
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(20, 16, 20, 16)
        title = QLabel("Table & RNG Settings")
        title.setObjectName("Title")
        tb_layout.addWidget(title)
        tb_layout.addStretch(1)
        save_btn = QPushButton("✓  SAVE")
        save_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 9px 22px; border-radius:0; border: none; }"
            "QPushButton:hover { background: #34D399; }"
        )
        save_btn.clicked.connect(
            lambda: self.coach_message.emit("Tablo ayarları kaydedildi — preview Spot Trainer'a yansır.")
        )
        tb_layout.addWidget(save_btn)
        layout.addWidget(title_bar)

        # --- Body split: settings sidebar (left) + live preview (right) ---
        split = QHBoxLayout()
        split.setContentsMargins(0, 0, 0, 0)
        split.setSpacing(0)

        # Sidebar of collapsible groups
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(330)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(0)

        # Table Borders
        borders = CollapsibleGroup("Table Borders", expanded=False, enabled=True)
        borders.add(_row("Border colour", self._color_combo(["Cyan", "Green", "Amber", "Off"])))
        borders.add(_row("Width", self._spin(1, 6, 2)))
        sb_layout.addWidget(borders)

        # RNG (expanded by default — main panel from screenshot)
        rng = CollapsibleGroup("RNG", expanded=True, enabled=True)
        rng_label = QLabel("Size")
        rng_label.setObjectName("Muted")
        rng.add(rng_label)
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setRange(0, 3)
        size_slider.setValue(2)
        size_slider.setTickPosition(QSlider.TicksBelow)
        size_slider.valueChanged.connect(self._size_changed)
        self.size_label = QLabel("Large")
        self.size_label.setStyleSheet("color: #22D3EE; font-weight: 700;")
        rng.add(size_slider)
        size_ticks = QHBoxLayout()
        for txt in ["Small", "Med", "Large", "XL"]:
            lab = QLabel(txt)
            lab.setObjectName("Muted")
            size_ticks.addWidget(lab)
            size_ticks.addStretch(1)
        size_ticks_w = QWidget()
        size_ticks_w.setLayout(size_ticks)
        rng.add(size_ticks_w)

        rng.add(QLabel(""))

        range_label = QLabel("Range")
        range_label.setObjectName("Muted")
        rng.add(range_label)
        from_spin = QSpinBox(); from_spin.setRange(0, 100); from_spin.setValue(0)
        to_spin = QSpinBox(); to_spin.setRange(0, 100); to_spin.setValue(100)
        rng.add(_row("", from_spin, QLabel("To"), to_spin))

        rng.add(QLabel(""))
        reroll_label = QLabel("Reroll  ⓘ")
        reroll_label.setObjectName("Muted")
        rng.add(reroll_label)

        reroll_row = QHBoxLayout()
        self.reroll_buttons = QButtonGroup(self)
        self.reroll_buttons.setExclusive(True)
        for i, txt in enumerate(["Off", "My Turn", "Timed"]):
            b = QPushButton(txt)
            b.setCheckable(True)
            if i == 0:
                b.setChecked(True)
            b.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius:0; padding: 6px 14px; color: #8B95A7; font-weight: 700; }"
                "QPushButton:checked { background: #1B2A3D; color: #22D3EE; border-color: #22D3EE; }"
            )
            self.reroll_buttons.addButton(b, i)
            reroll_row.addWidget(b)
        reroll_row.addStretch(1)
        reroll_w = QWidget(); reroll_w.setLayout(reroll_row)
        rng.add(reroll_w)

        # Choose Timed lock-style notice
        timed_notice = QFrame()
        timed_notice.setStyleSheet(
            "QFrame { background: #131A24; border: 1px solid #1E2733; border-radius:0; }"
        )
        tn_layout = QHBoxLayout(timed_notice)
        tn_layout.setContentsMargins(10, 8, 10, 8)
        lock = QLabel("🔒")
        tn_layout.addWidget(lock)
        tn_text = QLabel("CHOOSE TIMED\nTO DEFINE REROLL TIMER")
        tn_text.setStyleSheet("color: #8B95A7; font-weight: 800; font-size: 10px;")
        tn_layout.addWidget(tn_text, 1)
        rng.add(timed_notice)

        rng.add(QLabel(""))
        design_label = QLabel("Design  ⓘ")
        design_label.setObjectName("Muted")
        rng.add(design_label)
        self.design = QComboBox()
        self.design.addItems(["Default", "Minimal", "Classic", "High contrast"])
        rng.add(self.design)
        sb_layout.addWidget(rng)

        # Betting Buttons
        bb_grp = CollapsibleGroup("Betting Buttons", expanded=False, enabled=True)
        bb_grp.add(_row("Sizing presets", self._tag_row(["33%", "50%", "75%", "Pot", "All-in"])))
        bb_grp.add(_row("Show keyboard hints", self._switch(True)))
        sb_layout.addWidget(bb_grp)

        # Actions
        actions_grp = CollapsibleGroup("Actions", expanded=False, enabled=True)
        actions_grp.add(_row("Highlight best action", self._switch(True)))
        actions_grp.add(_row("Auto-advance after answer", self._switch(False)))
        actions_grp.add(_row("Show solver weight on chips", self._switch(True)))
        sb_layout.addWidget(actions_grp)

        # Table Info
        info_grp = CollapsibleGroup("Table Info", expanded=False, enabled=True)
        info_grp.add(_row("Show SPR/PO badge", self._switch(True)))
        info_grp.add(_row("Show RNG seed", self._switch(True)))
        info_grp.add(_row("Show pot size centred", self._switch(True)))
        info_grp.add(_row("Show stacks under positions", self._switch(False)))
        sb_layout.addWidget(info_grp)

        sb_layout.addStretch(1)
        split.addWidget(sidebar)

        # Right: live preview
        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pv_layout = QVBoxLayout(preview_card)
        pv_layout.setContentsMargins(20, 18, 20, 18)
        pv_label = QLabel("Preview")
        pv_label.setObjectName("Muted")
        pv_layout.addWidget(pv_label)
        spr = QLabel("SPR  3.2    PO  45.5%")
        spr.setStyleSheet("color: #E5E7EB; font-weight: 700; font-size: 12px;")
        pv_layout.addWidget(spr)
        self.preview = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=False)
        self.preview.set_dealer("BTN")
        self.preview.set_seed(70)
        self.preview.set_actions({
            "HJ": ["R 2.3", "R 33%", "B 75%", "AI"],
            "LJ": ["F"],
            "CO": ["F"],
            "BTN": ["F"],
            "UTG1": ["F"],
            "UTG": ["F"],
            "BB": ["F"],
            "SB": ["C", "X", "B 25%", "C", "X", "F"],
        })
        self.preview.set_community_cards(["W", "W", "W", "W", "W"])
        pv_layout.addWidget(self.preview, 1)

        # Sizing strip below preview
        size_row = QHBoxLayout()
        size_row.addStretch(1)
        custom = QSpinBox()
        custom.setRange(1, 999)
        custom.setValue(150)
        custom.setSuffix(" %")
        custom.setStyleSheet(
            "QSpinBox { background: #131A24; border: 1px solid #1E2733; border-radius:0; "
            "padding: 6px 8px; color: #E5E7EB; min-width: 90px; }"
        )
        size_row.addWidget(custom)
        size_row.addSpacing(10)
        for s in ["33%", "50%", "75%", "130%"]:
            b = QPushButton(s)
            b.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius:0; padding: 6px 14px; color: #E5E7EB; font-weight: 700; }"
                "QPushButton:hover { border-color: #22D3EE; color: #22D3EE; }"
            )
            size_row.addWidget(b)
        pv_layout.addLayout(size_row)
        split.addWidget(preview_card, 1)

        layout.addLayout(split)

    # --- helpers ---------------------------------------------------------
    def _size_changed(self, val: int) -> None:
        self.size_label.setText(["Small", "Med", "Large", "XL"][val])

    def _color_combo(self, items: list[str]) -> QComboBox:
        cb = QComboBox()
        cb.addItems(items)
        return cb

    def _spin(self, lo: int, hi: int, val: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        return s

    def _switch(self, on: bool) -> QPushButton:
        b = QPushButton("●")
        b.setCheckable(True)
        b.setChecked(on)
        b.setFixedSize(38, 20)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(
            "QPushButton { background: #1F2937; border: 1px solid #2A3647; border-radius:0; "
            "color: #4B5563; text-align: left; padding-left: 5px; }"
            "QPushButton:checked { background: #10B981; color: #04110D; "
            "padding-left: 21px; border-color: #10B981; }"
        )
        return b

    def _tag_row(self, items: list[str]) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for t in items:
            b = QPushButton(t)
            b.setCheckable(True)
            b.setChecked(True)
            b.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius:0; padding: 4px 10px; color: #8B95A7; font-weight: 700; }"
                "QPushButton:checked { background: #1B2A3D; color: #22D3EE; border-color: #22D3EE; }"
            )
            layout.addWidget(b)
        return box
