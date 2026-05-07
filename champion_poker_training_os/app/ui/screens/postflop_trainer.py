from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.ui.screens.spot_trainer import SpotTrainerScreen


class PostflopTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = [d for d in generate_spot_drills(120) if d["street"] in {"flop", "turn"}]
        self.index = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Postflop Trainer")
        title.setObjectName("Title")
        controls = QHBoxLayout()
        self.module = QComboBox()
        self.module.addItems(["BTN vs BB SRP", "CO vs BB SRP", "3bet pot IP", "3bet pot OOP", "Low connected", "A-high dry", "Paired", "Monotone"])
        ask = QPushButton("Ask Range/Nut Advantage")
        ask.clicked.connect(self.ask)
        controls.addWidget(self.module)
        controls.addWidget(ask)
        controls.addStretch(1)
        self.prompt = QLabel()
        self.prompt.setWordWrap(True)
        self.prompt.setObjectName("SectionTitle")
        self.feedback = QLabel("Choose a concept question below; this screen focuses on range advantage, nut advantage and sizing.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Muted")
        buttons = QHBoxLayout()
        for text in ["Range advantage?", "Nut advantage?", "Value hands?", "Bluff hands?", "Best sizing?"]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, t=text: self.answer(t))
            buttons.addWidget(button)
        layout.addWidget(title)
        layout.addLayout(controls)
        layout.addWidget(self.prompt)
        layout.addLayout(buttons)
        layout.addWidget(self.feedback)
        self.load()

    def load(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.prompt.setText(f"{spot['id']} | {spot['board_texture']} | {spot['action_history']} | Hero {spot['hero_cards']} on {spot['board']}")

    def answer(self, question: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.feedback.setObjectName("Green")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(
            f"{question} -> {spot['range_advantage']}; {spot['nut_advantage']}. "
            f"Solver baseline action is {spot['best_action']} with {spot['source_confidence']}."
        )
        self.index += 1
        self.load()

    def ask(self) -> None:
        self.coach_message.emit("Postflop koç: önce range advantage, sonra nut advantage, sonra blocker ve sizing ilişkisini oku.")

