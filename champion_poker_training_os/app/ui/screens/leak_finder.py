from __future__ import annotations

from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import leaks
from app.ui.components.leak_card import LeakCard


class LeakFinderScreen(QWidget):
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
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Leak Finder")
        title.setObjectName("Title")
        layout.addWidget(title)
        for leak in leaks():
            layout.addWidget(LeakCard(leak))
        layout.addStretch(1)

