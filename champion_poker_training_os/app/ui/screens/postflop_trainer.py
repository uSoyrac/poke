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


FLOP_MODULES = [
    "BTN vs BB SRP", "CO vs BB SRP", "SB vs BB SRP",
    "3bet pot IP", "3bet pot OOP",
    "Low connected", "A-high dry", "K-high dynamic",
    "Paired", "Monotone", "Two-tone", "Multiway",
]

TURN_MODULES = [
    "Brick turn", "Overcard turn", "Flush-completing turn",
    "Straight-completing turn", "Paired turn", "Double barrel",
    "Probe", "Delayed cbet", "Turn overbet", "Showdown value",
]

CONCEPT_QUESTIONS = [
    "Who has range advantage?",
    "Who has nut advantage?",
    "Which hands are value?",
    "Which hands are bluff?",
    "Which blocker matters?",
    "What sizing is best?",
    "How should villain defend?",
    "What is our bet/check frequency?",
]


class PostflopTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.setObjectName('PostflopTrainerScreenRoot')
        from app.ui.theme import poke_tokens as _pt_bg
        from PySide6.QtCore import Qt as _Qt_bg
        self.setAttribute(_Qt_bg.WA_StyledBackground, True)
        self.setStyleSheet(f"#PostflopTrainerScreenRoot {{ background: {_pt_bg.BG}; }}")
        self.state = state
        self.all_drills = generate_spot_drills(120)
        self.drills = [d for d in self.all_drills if d["street"] in {"flop", "turn"}]
        self.index = 0
        self.correct = 0
        self.total = 0

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
        title = QLabel("Postflop Trainer")
        title.setObjectName("Title")
        layout.addWidget(title)

        # Controls
        controls = QHBoxLayout()
        self.street_filter = QComboBox()
        self.street_filter.addItems(["Both", "Flop Only", "Turn Only"])
        self.street_filter.currentTextChanged.connect(self._filter_changed)
        self.module = QComboBox()
        self.module.addItems(FLOP_MODULES[:6])
        controls.addWidget(QLabel("Street"))
        controls.addWidget(self.street_filter)
        controls.addWidget(QLabel("Module"))
        controls.addWidget(self.module)
        controls.addStretch(1)
        layout.addLayout(controls)

        # Stats
        stats_row = QGridLayout()
        self.stat_accuracy = MetricCard("Accuracy", "—", "postflop decisions")
        self.stat_ev = MetricCard("Avg EV Loss", "—", "per decision", "Amber")
        self.stat_streak = MetricCard("Streak", "0", "correct in a row", "Green")
        stats_row.addWidget(self.stat_accuracy, 0, 0)
        stats_row.addWidget(self.stat_ev, 0, 1)
        stats_row.addWidget(self.stat_streak, 0, 2)
        layout.addLayout(stats_row)

        # Main: Table + Info panel
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

        # Action buttons
        self.action_layout = QHBoxLayout()
        panel_layout.addWidget(self.spot_title)
        panel_layout.addWidget(self.spot_meta)
        panel_layout.addWidget(self.spot_history)
        panel_layout.addLayout(self.action_layout)
        main.addWidget(panel, 1)
        layout.addLayout(main)

        # Concept questions row
        concept_frame = QFrame()
        concept_frame.setObjectName("Card")
        concept_layout = QVBoxLayout(concept_frame)
        concept_label = QLabel("Concept Questions — Think before you act:")
        concept_label.setObjectName("SectionTitle")
        concept_layout.addWidget(concept_label)
        concept_btns = QGridLayout()
        for idx, q in enumerate(CONCEPT_QUESTIONS):
            btn = QPushButton(q)
            btn.clicked.connect(lambda checked=False, question=q: self._answer_concept(question))
            concept_btns.addWidget(btn, idx // 4, idx % 4)
        concept_layout.addLayout(concept_btns)
        layout.addWidget(concept_frame)

        # Feedback area
        feedback_frame = QFrame()
        feedback_frame.setObjectName("DataPanel")
        self.feedback_layout = QVBoxLayout(feedback_frame)
        self.feedback_text = QLabel("Select an action or answer a concept question.")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setObjectName("Muted")
        self.feedback_layout.addWidget(self.feedback_text)
        layout.addWidget(feedback_frame)

        self._load_spot()

    def _filter_changed(self) -> None:
        street_filter = self.street_filter.currentText()
        if street_filter == "Flop Only":
            self.drills = [d for d in self.all_drills if d["street"] == "flop"]
        elif street_filter == "Turn Only":
            self.drills = [d for d in self.all_drills if d["street"] == "turn"]
        else:
            self.drills = [d for d in self.all_drills if d["street"] in {"flop", "turn"}]
        self.index = 0
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

        _clear_layout(self.action_layout)
        from app.ui.components.action_buttons import GtoActionButton, action_display
        pot_bb = float(spot.get("pot_bb", 10.0))
        stack_bb = float(spot.get("stack_bb", 40.0))
        for action in spot["options"]:
            button = GtoActionButton(action_display(action, pot_bb, stack_bb), action)
            button.clicked.connect(lambda checked=False, a=action: self._play_action(a))
            self.action_layout.addWidget(button)

    def _play_action(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        self.total += 1
        if result["is_correct"]:
            self.correct += 1
        else:
            # Persist wrong postflop decisions to global My Mistakes queue
            try:
                from datetime import datetime
                from app.db.mistakes_queue import (
                    MistakeEntry as MqEntry, add_mistake, new_id as new_mistake_id,
                )
                add_mistake(MqEntry(
                    id           = new_mistake_id(),
                    logged_at    = datetime.now().isoformat(timespec="seconds"),
                    context      = "postflop_trainer",
                    spot_id      = spot.get("id", ""),
                    position     = (spot.get("position") or "").upper(),
                    stack_bb     = float(spot.get("stack_bb", 40)),
                    pot_type     = (spot.get("pot_type") or "SRP").upper(),
                    hero_cards   = spot.get("hero_cards", ""),
                    hero_action  = action.lower(),
                    gto_action   = result["best_action"].lower(),
                    ev_loss      = round(float(result["ev_loss"]), 2),
                    why          = result.get("sizing_feedback", "")[:240],
                ))
                # Toast feedback — non-blocking
                try:
                    from app.ui.components.toast import Toast
                    Toast.show_warning(
                        self.window(),
                        f"❌ Hata kaydedildi  ·  My Mistakes'e eklendi (−{result['ev_loss']:.2f}bb)"
                    )
                except Exception:
                    pass
            except Exception:
                pass

        accuracy = f"{100 * self.correct / self.total:.0f}%" if self.total > 0 else "—"
        self.stat_accuracy = _update_card(self.stat_accuracy, accuracy, f"{self.total} decisions")

        # Show detailed feedback — Türkçe + learning-friendly
        _clear_layout(self.feedback_layout)
        is_ok = result["is_correct"]
        color = "Green" if is_ok else "Red"
        if is_ok:
            verdict = QLabel(
                f"✅  Doğru karar — {action.upper()}  ·  EV kayıp: {result['ev_loss']:.2f}bb"
            )
        else:
            verdict = QLabel(
                f"❌  Daha iyisi var — Sen {action.upper()} dedin, GTO "
                f"{result['best_action'].upper()}  ·  EV kayıp: {result['ev_loss']:.2f}bb"
            )
        verdict.setObjectName(color)
        verdict.setWordWrap(True)
        self.feedback_layout.addWidget(verdict)

        # Sizing feedback as a separate hint (the solver's reasoning)
        sizing_lbl = QLabel(f"💡 {result.get('sizing_feedback', '')}")
        sizing_lbl.setWordWrap(True)
        sizing_lbl.setStyleSheet(
            "QLabel{background:#0C1117;color:#E5E7EB;font-size:12px;"
            "padding:8px 12px;border-radius:0;border-left:3px solid #F59E0B;}"
        )
        self.feedback_layout.addWidget(sizing_lbl)

        # 100-hand leak projection — concrete cost of repeating the mistake
        if not is_ok:
            leak_lbl = QLabel(
                f"💸 100 elde tekrarlanırsa ~{result['ev_loss']*100:.0f}bb leak"
            )
            leak_lbl.setStyleSheet(
                "QLabel{color:#F87171;font-size:11px;padding:4px 12px;font-weight:600;}"
            )
            self.feedback_layout.addWidget(leak_lbl)

        # Solver bars
        solver_grid = QGridLayout()
        for idx, act in enumerate(result["solver"]["actions"]):
            solver_grid.addWidget(
                SolverFrequencyBar(act["action"], act["frequency"], act["ev"], act.get("sizing", "")),
                idx // 4, idx % 4,
            )
        self.feedback_layout.addLayout(solver_grid)

        # Next button
        next_btn = QPushButton("Sonraki Spot →")
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(self._next)
        self.feedback_layout.addWidget(next_btn)

        self.coach_message.emit(explain_spot(spot, action))

    def _answer_concept(self, question: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        answers = {
            "Who has range advantage?": spot["range_advantage"],
            "Who has nut advantage?": spot["nut_advantage"],
            "Which hands are value?": f"Top pair+, overpairs on {spot['board_texture']} board",
            "Which hands are bluff?": f"Missed draws, backdoor equity on {spot['board_texture']}",
            "Which blocker matters?": f"Key blockers depend on {spot['board_texture']} texture",
            "What sizing is best?": f"Solver baseline: {spot['best_action']} with {spot['source_confidence']}",
            "How should villain defend?": f"MDF-based defense, tighter on {spot['board_texture']}",
            "What is our bet/check frequency?": f"Mixed strategy on {spot['board_texture']}: see solver frequencies",
        }
        answer = answers.get(question, "Think about range vs nut advantage first.")

        self.feedback_text = QLabel(f"{question}\n→ {answer}")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setObjectName("Cyan")
        _clear_layout(self.feedback_layout)
        self.feedback_layout.addWidget(self.feedback_text)

        self.coach_message.emit(
            f"Postflop koç: {question} → {answer}. "
            f"Board: {spot['board']}, Texture: {spot['board_texture']}. "
            "Range avantajı → sizing; nut avantajı → polarizasyon."
        )

    def _next(self) -> None:
        self.index += 1
        self._load_spot()
        _clear_layout(self.feedback_layout)
        self.feedback_text = QLabel("Select an action or answer a concept question.")
        self.feedback_text.setObjectName("Muted")
        self.feedback_layout.addWidget(self.feedback_text)


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
