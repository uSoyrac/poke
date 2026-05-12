from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
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
from app.ui.components.poker_table import PokerTableView
from app.ui.components.solver_bar import EVLossBadge, SolverFrequencyBar
from app.ui.components.metric_card import MetricCard

RIVER_CONCEPTS = [
    "Bluff-catch",
    "Blockers",
    "Unblockers",
    "MDF",
    "Value/bluff ratio",
    "Thin value",
    "Missed draw bluff",
    "Overbet response",
    "Block bet",
    "Jam/fold/call",
    "River raise bluff",
]


class RiverTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.all_drills = [d for d in generate_spot_drills(120) if d["street"] == "river"]
        self.drills = list(self.all_drills)
        self.index = 0
        self.correct = 0
        self.total = 0
        self.streak = 0

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

        # Header
        title = QLabel("River Decision Trainer")
        title.setObjectName("Title")
        layout.addWidget(title)

        # Controls
        controls = QHBoxLayout()
        self.concept_filter = QComboBox()
        self.concept_filter.addItems(["All Concepts"] + RIVER_CONCEPTS[:6])
        controls.addWidget(QLabel("Focus"))
        controls.addWidget(self.concept_filter)
        controls.addStretch(1)
        layout.addLayout(controls)

        # Stats
        stats = QGridLayout()
        self.stat_accuracy = MetricCard("River Accuracy", "—", "decisions")
        self.stat_ev = MetricCard("Avg EV Loss", "—", "per river decision", "Amber")
        self.stat_streak = MetricCard("Streak", "0", "correct in a row", "Green")
        self.stat_mdf = MetricCard("MDF Awareness", "—", "defense quality", "Cyan")
        stats.addWidget(self.stat_accuracy, 0, 0)
        stats.addWidget(self.stat_ev, 0, 1)
        stats.addWidget(self.stat_streak, 0, 2)
        stats.addWidget(self.stat_mdf, 0, 3)
        layout.addLayout(stats)

        # Main: table + info
        main = QHBoxLayout()
        self.table_view = PokerTableView()
        main.addWidget(self.table_view, 2)

        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_meta = QLabel()
        self.spot_meta.setWordWrap(True)
        self.spot_meta.setObjectName("Muted")
        self.spot_history = QLabel()
        self.spot_history.setObjectName("Cyan")

        # River-specific info
        self.river_info = QLabel()
        self.river_info.setWordWrap(True)
        self.river_info.setObjectName("Amber")

        self.action_layout = QHBoxLayout()
        panel_layout.addWidget(self.spot_title)
        panel_layout.addWidget(self.spot_meta)
        panel_layout.addWidget(self.spot_history)
        panel_layout.addWidget(self.river_info)
        panel_layout.addLayout(self.action_layout)
        main.addWidget(panel, 1)
        layout.addLayout(main)

        # Feedback
        feedback_frame = QFrame()
        feedback_frame.setObjectName("DataPanel")
        self.feedback_layout = QVBoxLayout(feedback_frame)
        self.feedback_text = QLabel("Train bluff-catch, blockers, MDF, thin value and overbet response. River is where the biggest EV leaks live.")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setObjectName("Muted")
        self.feedback_layout.addWidget(self.feedback_text)
        layout.addWidget(feedback_frame)

        self._load_spot()

    def _load_spot(self) -> None:
        if not self.drills:
            return
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.table_view.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_meta.setText(
            f"{spot['format']} | {spot['table']} | {spot['pot_type']} | "
            f"{spot['stack_bb']}bb | Board: {spot['board']} | {spot['board_texture']}"
        )
        self.spot_history.setText(spot["action_history"])

        # River-specific analysis hints
        hero = spot["hero_cards"]
        board = spot["board"] or ""
        blocker_hint = _blocker_analysis(hero, board)
        self.river_info.setText(
            f"Blocker analysis: {blocker_hint} | "
            f"MDF baseline: defend ~{100 - int(spot['pot_bb'] / (spot['pot_bb'] + spot['stack_bb'] * 0.66) * 100)}% of range | "
            f"River concept: {RIVER_CONCEPTS[self.index % len(RIVER_CONCEPTS)]}"
        )

        _clear_layout(self.action_layout)
        from app.ui.components.action_buttons import GtoActionButton, action_display
        pot_bb = float(spot.get("pot_bb", 10.0))
        stack_bb = float(spot.get("stack_bb", 40.0))
        for action in spot["options"]:
            button = GtoActionButton(action_display(action, pot_bb, stack_bb), action)
            button.clicked.connect(lambda checked=False, a=action: self._answer(a))
            self.action_layout.addWidget(button)

    def _answer(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        self.total += 1

        if result["is_correct"]:
            self.correct += 1
            self.streak += 1
        else:
            self.streak = 0

        accuracy = f"{100 * self.correct / self.total:.0f}%" if self.total > 0 else "—"
        _update_card(self.stat_accuracy, accuracy, f"{self.total} river decisions")
        _update_card(self.stat_streak, str(self.streak), "correct in a row")

        # Detailed feedback
        _clear_layout(self.feedback_layout)
        color = "Green" if result["is_correct"] else "Red"

        verdict = QLabel(
            f"Hero {action} | Best: {result['best_action']} | EV loss: {result['ev_loss']:.2f}bb | "
            f"{'✓ Correct' if result['is_correct'] else '✗ Mistake'} | {result['sizing_feedback']}"
        )
        verdict.setObjectName(color)
        verdict.setWordWrap(True)
        self.feedback_layout.addWidget(verdict)

        # MDF note
        mdf_note = QLabel(
            "Remember: MDF is a baseline, not a command. Blockers decide close river calls. "
            "Check if your hand blocks villain's bluffs (bad) or value (good for calling)."
        )
        mdf_note.setObjectName("Muted")
        mdf_note.setWordWrap(True)
        self.feedback_layout.addWidget(mdf_note)

        # Solver frequencies
        solver_grid = QGridLayout()
        for idx, act in enumerate(result["solver"]["actions"]):
            solver_grid.addWidget(
                SolverFrequencyBar(act["action"], act["frequency"], act["ev"], act.get("sizing", "")),
                idx // 4, idx % 4,
            )
        self.feedback_layout.addLayout(solver_grid)

        # Next button
        next_btn = QPushButton("Next River Spot →")
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(self._next)
        self.feedback_layout.addWidget(next_btn)

        self.coach_message.emit(
            f"River koç: {result['sizing_feedback']} Kaynak: {result['solver']['source_confidence']}. "
            f"Blocker analizi: {_blocker_analysis(spot['hero_cards'], spot['board'] or '')}."
        )

    def _next(self) -> None:
        self.index += 1
        self._load_spot()
        _clear_layout(self.feedback_layout)
        self.feedback_text = QLabel("Choose your river action.")
        self.feedback_text.setObjectName("Muted")
        self.feedback_layout.addWidget(self.feedback_text)


def _blocker_analysis(hero: str, board: str) -> str:
    """Simple blocker hint based on hero cards and board."""
    if not hero or len(hero) < 4:
        return "No blocker info"
    rank1, rank2 = hero[0].upper(), hero[2].upper()
    board_upper = board.upper()

    notes = []
    if rank1 == "A" or rank2 == "A":
        notes.append("Hero blocks top pair / nut flush draws")
    if rank1 in ("K", "Q") or rank2 in ("K", "Q"):
        notes.append("Hero blocks strong top pairs")
    if board_upper and rank1 in board_upper:
        notes.append(f"Hero connects with board ({rank1})")
    if board_upper and rank2 in board_upper:
        notes.append(f"Hero connects with board ({rank2})")

    if hero[1].lower() == hero[3].lower():
        notes.append("Suited — blocks flush combos")

    return "; ".join(notes) if notes else "Neutral blockers — decision based on range defense"


def _update_card(card: MetricCard, value: str, detail: str) -> MetricCard:
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
        elif child.objectName() in ("Cyan", "Green", "Amber", "Red"):
            child.setText(detail)
    return card


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget:
            widget.deleteLater()
        if child:
            _clear_layout(child)
