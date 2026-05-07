from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import compare_action, solve_spot
from app.training.trainer_scoring import score_decision, skill_label
from app.ui.components.poker_table import PokerTableView
from app.ui.components.solver_bar import EVLossBadge, SolverFrequencyBar


class SpotTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = generate_spot_drills(120)
        self.index = 0
        self.feedback_layout = QVBoxLayout()
        self.action_layout = QHBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Spot Practice Trainer")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        for mode in ["Quick drill", "Timed mode", "Mistakes-only", "Boss battle"]:
            button = QPushButton(mode)
            button.clicked.connect(lambda checked=False, m=mode: self.coach_message.emit(f"{m} aktif. Feedback demo solver ile üretilecek."))
            header.addWidget(button)
        layout.addLayout(header)

        top = QHBoxLayout()
        self.table = PokerTableView()
        top.addWidget(self.table, 2)
        info = QFrame()
        info.setObjectName("DataPanel")
        info_layout = QVBoxLayout(info)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_meta = QLabel()
        self.spot_meta.setWordWrap(True)
        self.spot_meta.setObjectName("Muted")
        self.action_history = QLabel()
        self.action_history.setWordWrap(True)
        self.action_history.setObjectName("Cyan")
        info_layout.addWidget(self.spot_title)
        info_layout.addWidget(self.spot_meta)
        info_layout.addWidget(self.action_history)
        info_layout.addLayout(self.action_layout)
        top.addWidget(info, 1)
        layout.addLayout(top)

        feedback = QFrame()
        feedback.setObjectName("DataPanel")
        feedback.setLayout(self.feedback_layout)
        layout.addWidget(feedback)
        self.load_spot()

    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_meta.setText(
            f"{spot['format']} | {spot['table']} | {spot['pot_type']} | "
            f"{spot['stack_bb']}bb | {spot['board_texture']} | ICM {spot['icm']}"
        )
        self.action_history.setText(spot["action_history"])
        self.table.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])
        _clear_layout(self.action_layout)
        for action in spot["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self.answer(a))
            self.action_layout.addWidget(button)
        self._show_solver_preview(spot)

    def answer(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        score = score_decision(result["ev_loss"], result["solver_frequency"])
        self.state.record_decision(result["is_correct"], result["ev_loss"], f"{spot['id']} {action}: -{result['ev_loss']:.2f}bb")
        self._show_feedback(spot, result, score)
        self.coach_message.emit(explain_spot(spot, action))
        self.index += 1

    def _show_solver_preview(self, spot: dict) -> None:
        _clear_layout(self.feedback_layout)
        title = QLabel("Solver Baseline Preview")
        title.setObjectName("SectionTitle")
        self.feedback_layout.addWidget(title)
        result = solve_spot(spot)
        grid = QGridLayout()
        for idx, action in enumerate(result.actions):
            grid.addWidget(SolverFrequencyBar(action.action, action.frequency, action.ev, action.sizing), idx // 4, idx % 4)
        self.feedback_layout.addLayout(grid)
        confidence = QLabel(f"Source confidence: {result.source_confidence}")
        confidence.setObjectName("Amber" if "Mock" in result.source_confidence else "Green")
        self.feedback_layout.addWidget(confidence)

    def _show_feedback(self, spot: dict, result: dict, score: int) -> None:
        _clear_layout(self.feedback_layout)
        row = QHBoxLayout()
        row.addWidget(EVLossBadge(result["ev_loss"]))
        verdict = QLabel(
            f"Hero {result['hero_action']} | Best {result['best_action']} | "
            f"Hero EV {result['hero_ev']:+.2f} | Score {score} ({skill_label(score)})"
        )
        verdict.setObjectName("Green" if result["is_correct"] else "Red")
        row.addWidget(verdict, 1)
        next_button = QPushButton("Next Spot")
        next_button.setObjectName("PrimaryButton")
        next_button.clicked.connect(self.load_spot)
        retry_button = QPushButton("Retry Similar 5")
        retry_button.clicked.connect(lambda: self.coach_message.emit("Benzer 5 spot drill pack'e eklendi: aynı street, benzer pot type, farklı blocker."))
        row.addWidget(retry_button)
        row.addWidget(next_button)
        self.feedback_layout.addLayout(row)
        self.feedback_layout.addWidget(QLabel(result["sizing_feedback"]))
        grid = QGridLayout()
        for idx, action in enumerate(result["solver"]["actions"]):
            grid.addWidget(SolverFrequencyBar(action["action"], action["frequency"], action["ev"], action.get("sizing", "")), idx // 4, idx % 4)
        self.feedback_layout.addLayout(grid)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget:
            widget.deleteLater()
        if child_layout:
            _clear_layout(child_layout)

