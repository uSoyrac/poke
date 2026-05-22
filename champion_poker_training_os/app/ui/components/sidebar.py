from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


# Logical grouping for the brutalist sidebar
NAV_GROUPS = [
    ("MAIN", [
        "Dashboard",
        "Play Session",
        "Tournament Simulator",
    ]),
    ("TRAINING", [
        "GTO Study Library",
        "Spot Practice Trainer",
        "Preflop Range Trainer",
        "Postflop Trainer",
        "River Decision Trainer",
        "Combat Trainer",
        "Math Lab",
    ]),
    ("ANALYSIS", [
        "Hand History Analyzer",
        "Fast Play Simulator",
        "ICM / PKO Trainer",
        "Leak Finder",
        "AI Poker Coach",
        "Reports",
    ]),
    ("LIBRARY", [
        "Knowledge Base",
        "Study Planner",
        "Settings / Compliance Guard",
    ]),
]


class SidebarNav(QFrame):
    navigation_requested = Signal(str)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)
        self.buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Brand block
        brand_box = QFrame()
        brand_box.setStyleSheet("border-bottom: 1px solid #23271f;")
        brand_l = QVBoxLayout(brand_box)
        brand_l.setContentsMargins(20, 16, 20, 16)
        brand_l.setSpacing(2)
        brand_row = QFrame()
        brand_row_l = QVBoxLayout(brand_row)
        brand_row_l.setContentsMargins(0, 0, 0, 0)
        brand_row_l.setSpacing(2)
        brand = QLabel("POKE.")
        brand.setObjectName("BrandMark")
        tag = QLabel("CHAMPION OS / v2.0")
        tag.setObjectName("BrandTag")
        brand_row_l.addWidget(brand)
        brand_row_l.addWidget(tag)
        brand_l.addWidget(brand_row)
        root.addWidget(brand_box)

        # Scrollable nav body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(0, 10, 0, 14)
        body_l.setSpacing(0)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        items_set = set(items)
        used = set()
        for group_name, group_items in NAV_GROUPS:
            valid = [i for i in group_items if i in items_set]
            if not valid:
                continue
            label = QLabel(group_name)
            label.setObjectName("NavGroupLabel")
            body_l.addSpacing(8)
            body_l.addWidget(label)
            for item in valid:
                used.add(item)
                btn = self._make_button(item)
                body_l.addWidget(btn)

        # Anything not categorized
        leftover = [i for i in items if i not in used]
        if leftover:
            label = QLabel("OTHER")
            label.setObjectName("NavGroupLabel")
            body_l.addSpacing(8)
            body_l.addWidget(label)
            for item in leftover:
                btn = self._make_button(item)
                body_l.addWidget(btn)

        body_l.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer / user
        footer = QFrame()
        footer.setStyleSheet("border-top: 1px solid #23271f;")
        f_l = QVBoxLayout(footer)
        f_l.setContentsMargins(20, 10, 20, 12)
        f_l.setSpacing(1)
        user = QLabel("UYGAR")
        user.setObjectName("SectionTitle")
        meta = QLabel("ONLINE · GTO MODE")
        meta.setObjectName("BrandTag")
        meta.setStyleSheet("color: #5ad17a;")
        f_l.addWidget(user)
        f_l.addWidget(meta)
        root.addWidget(footer)

        if items:
            self.set_active(items[0])

    def _make_button(self, item: str) -> QPushButton:
        btn = QPushButton(item)
        btn.setCheckable(True)
        btn.setObjectName("NavButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, name=item: self.navigation_requested.emit(name))
        self.group.addButton(btn)
        self.buttons[item] = btn
        return btn

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)
