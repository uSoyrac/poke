from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import combat_packs
from app.ui.components.drill_card import DrillCard


class CombatTrainerScreen(QWidget):
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
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Combat Trainer")
        title.setObjectName("Title")
        layout.addWidget(title)
        grid = QGridLayout()
        for idx, pack in enumerate(combat_packs()):
            card = DrillCard(pack)
            card.start_requested.connect(lambda p: self.coach_message.emit(f"Combat pack started: {p['name']} | Boss hand {p['boss_hand']} | Reward {p['reward']}"))
            grid.addWidget(card, idx // 2, idx % 2)
        layout.addLayout(grid)

