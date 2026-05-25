"""Spot Practice Trainer — real LivePokerTable, full seat rendering."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QVBoxLayout, QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import compare_action, solve_spot
from app.training.trainer_scoring import score_decision, skill_label
from app.ui.components.poker_table import LivePokerTable
from app.ui.components.spot_table import render_spot_on_table
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

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header
        header_frame = QFrame()
        header_frame.setObjectName("TopBar")
        header_row = QHBoxLayout(header_frame)
        header_row.setContentsMargins(18, 10, 18, 10)
        title = QLabel("Spot Practice Trainer")
        title.setObjectName("Title")
        header_row.addWidget(title)
        header_row.addStretch(1)
        for mode in ["Quick drill", "Timed mode", "Mistakes-only", "Boss battle"]:
            btn = QPushButton(mode)
            btn.clicked.connect(
                lambda checked=False, m=mode:
                self.coach_message.emit(f"{m} aktif. Feedback demo solver ile üretilecek.")
            )
            header_row.addWidget(btn)
        root.addWidget(header_frame)

        # ── Content row
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root.addWidget(content, 1)

        # Left: real poker table
        self.table = LivePokerTable()
        content_layout.addWidget(self.table, 3)

        # Right: spot info + actions + solver
        right = QFrame()
        right.setObjectName("DataPanel")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(12)

        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_title.setWordWrap(True)

        self.spot_meta = QLabel()
        self.spot_meta.setWordWrap(True)
        self.spot_meta.setObjectName("Muted")

        self.action_history = QLabel()
        self.action_history.setWordWrap(True)
        self.action_history.setObjectName("Cyan")

        right_layout.addWidget(self.spot_title)
        right_layout.addWidget(self.spot_meta)
        right_layout.addWidget(self.action_history)
        right_layout.addLayout(self.action_layout)

        feedback_frame = QFrame()
        feedback_frame.setObjectName("DataPanel")
        feedback_frame.setLayout(self.feedback_layout)
        right_layout.addWidget(feedback_frame, 1)

        content_layout.addWidget(right, 2)

        self.load_spot()

    # ── Drill logic ──────────────────────────────────────────────────────────

    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot

        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_meta.setText(
            f"{spot['format']} | {spot['table']} | {spot['pot_type']} | "
            f"{spot['stack_bb']}bb | {spot['board_texture']} | ICM {spot['icm']}"
        )
        self.action_history.setText(spot["action_history"])

        render_spot_on_table(self.table, spot)

        _clear_layout(self.action_layout)
        for action in spot["options"]:
            btn = QPushButton(action)
            btn.clicked.connect(lambda checked=False, a=action: self.answer(a))
            self.action_layout.addWidget(btn)

        self._show_solver_preview(spot)

    def answer(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        score = score_decision(result["ev_loss"], result["solver_frequency"])
        self.state.record_decision(
            result["is_correct"], result["ev_loss"],
            f"{spot['id']} {action}: -{result['ev_loss']:.2f}bb"
        )
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
            grid.addWidget(
                SolverFrequencyBar(action.action, action.frequency, action.ev, action.sizing),
                idx // 4, idx % 4
            )
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
        retry_btn = QPushButton("Retry Similar 5")
        retry_btn.clicked.connect(
            lambda: self.coach_message.emit(
                "Benzer 5 spot drill pack'e eklendi: aynı street, benzer pot type, farklı blocker."
            )
        )
        next_btn = QPushButton("Next Spot")
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(self.load_spot)
        row.addWidget(retry_btn)
        row.addWidget(next_btn)
        self.feedback_layout.addLayout(row)
        self.feedback_layout.addWidget(QLabel(result["sizing_feedback"]))
        grid = QGridLayout()
        for idx, action in enumerate(result["solver"]["actions"]):
            grid.addWidget(
                SolverFrequencyBar(
                    action["action"], action["frequency"],
                    action["ev"], action.get("sizing", "")
                ),
                idx // 4, idx % 4
            )
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
