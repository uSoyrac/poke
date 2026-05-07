from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import compare_action


class RiverTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = [d for d in generate_spot_drills(120) if d["street"] == "river"]
        self.index = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("River Decision Trainer")
        title.setObjectName("Title")
        self.prompt = QLabel()
        self.prompt.setWordWrap(True)
        self.prompt.setObjectName("SectionTitle")
        self.feedback = QLabel("Train bluff-catch, blockers, MDF, thin value and overbet response.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Muted")
        self.actions = QHBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.prompt)
        layout.addLayout(self.actions)
        layout.addWidget(self.feedback)
        self.load()

    def load(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.prompt.setText(f"{spot['id']} | {spot['board']} | {spot['action_history']} | Hero {spot['hero_cards']}")
        while self.actions.count():
            item = self.actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for action in spot["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self.answer(a))
            self.actions.addWidget(button)

    def answer(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        self.feedback.setObjectName("Green" if result["is_correct"] else "Red")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(
            f"Hero {action}; baseline {result['best_action']}; EV loss {result['ev_loss']:.2f}bb. "
            "MDF is a baseline, blockers decide close calls."
        )
        self.coach_message.emit(f"River koç: {result['sizing_feedback']} Kaynak: {result['solver']['source_confidence']}.")
        self.index += 1
        self.load()

