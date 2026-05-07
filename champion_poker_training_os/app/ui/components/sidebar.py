from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QLabel, QPushButton, QVBoxLayout


class SidebarNav(QFrame):
    navigation_requested = Signal(str)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.buttons: dict[str, QPushButton] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(7)

        brand = QLabel("Champion\nPoker Training OS")
        brand.setObjectName("SectionTitle")
        layout.addWidget(brand)
        subtitle = QLabel("Offline solver lab")
        subtitle.setObjectName("Cyan")
        layout.addWidget(subtitle)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for item in items:
            button = QPushButton(item)
            button.setCheckable(True)
            button.setObjectName("NavButton")
            button.clicked.connect(lambda checked=False, name=item: self.navigation_requested.emit(name))
            group.addButton(button)
            self.buttons[item] = button
            layout.addWidget(button)
        layout.addStretch(1)
        self.set_active(items[0])

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)

