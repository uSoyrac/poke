from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import combat_packs, generate_spot_drills
from app.solver.mock_solver import compare_action
from app.ui.components.drill_card import DrillCard
from app.ui.components.poker_table import LivePokerTable
from app.ui.components.spot_table import render_spot_on_table
from app.ui.components.solver_bar import EVLossBadge, SolverFrequencyBar


class CombatTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.packs = combat_packs()
        self.active_pack = None
        self.pack_drills = []
        self.pack_index = 0
        self.pack_correct = 0
        self.pack_ev_loss = 0.0

        self.stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.stack)

        # Page 1: Pack selection
        self.select_page = self._build_select_page()
        self.stack.addWidget(self.select_page)

        # Page 2: Combat drill
        self.drill_page = self._build_drill_page()
        self.stack.addWidget(self.drill_page)

        # Page 3: Results
        self.results_page = self._build_results_page()
        self.stack.addWidget(self.results_page)

        self.stack.setCurrentWidget(self.select_page)

    def _build_select_page(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Combat Trainer")
        title.setObjectName("Title")
        subtitle = QLabel("Select a combat pack to start solving spots. Complete the pack to unlock the boss hand.")
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        for idx, pack in enumerate(self.packs):
            card = _CombatPackCard(pack)
            card.start_clicked.connect(self._start_pack)
            grid.addWidget(card, idx // 2, idx % 2)
        layout.addLayout(grid)

        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    def _build_drill_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Top bar with pack info and progress
        top_bar = QHBoxLayout()
        self.pack_title = QLabel("Combat Pack")
        self.pack_title.setObjectName("SectionTitle")
        self.progress_label = QLabel("0 / 20")
        self.progress_label.setObjectName("Cyan")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        back_btn = QPushButton("← Back to Packs")
        back_btn.clicked.connect(self._back_to_select)
        top_bar.addWidget(self.pack_title)
        top_bar.addWidget(self.progress_label)
        top_bar.addWidget(self.progress_bar, 1)
        top_bar.addWidget(back_btn)
        layout.addLayout(top_bar)

        # Table + spot info
        main = QHBoxLayout()
        self.table = LivePokerTable()
        main.addWidget(self.table, 2)

        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.spot_label = QLabel()
        self.spot_label.setObjectName("SectionTitle")
        self.spot_meta = QLabel()
        self.spot_meta.setWordWrap(True)
        self.spot_meta.setObjectName("Muted")
        self.spot_history = QLabel()
        self.spot_history.setObjectName("Cyan")
        self.action_layout = QHBoxLayout()
        panel_layout.addWidget(self.spot_label)
        panel_layout.addWidget(self.spot_meta)
        panel_layout.addWidget(self.spot_history)
        panel_layout.addLayout(self.action_layout)
        main.addWidget(panel, 1)
        layout.addLayout(main)

        # Feedback area
        feedback_frame = QFrame()
        feedback_frame.setObjectName("DataPanel")
        self.feedback_layout = QVBoxLayout(feedback_frame)
        self.feedback_text = QLabel("Choose an action to begin combat training.")
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setObjectName("Green")
        self.feedback_layout.addWidget(self.feedback_text)
        layout.addWidget(feedback_frame)

        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        self.result_title = QLabel("Combat Pack Complete!")
        self.result_title.setObjectName("Title")
        self.result_summary = QLabel()
        self.result_summary.setWordWrap(True)
        self.result_summary.setObjectName("SectionTitle")
        self.result_detail = QLabel()
        self.result_detail.setWordWrap(True)
        self.result_detail.setObjectName("Cyan")
        self.result_grade = QLabel()
        self.result_grade.setObjectName("Green")

        retry_btn = QPushButton("Retry Pack")
        retry_btn.setObjectName("PrimaryButton")
        retry_btn.clicked.connect(self._retry_pack)
        back_btn = QPushButton("Back to Packs")
        back_btn.clicked.connect(self._back_to_select)

        layout.addWidget(self.result_title)
        layout.addWidget(self.result_summary)
        layout.addWidget(self.result_detail)
        layout.addWidget(self.result_grade)
        btn_row = QHBoxLayout()
        btn_row.addWidget(retry_btn)
        btn_row.addWidget(back_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return page

    def _start_pack(self, pack: dict) -> None:
        self.active_pack = pack
        total = min(pack["spots"], 20)  # Cap at 20 per session
        all_drills = generate_spot_drills(120)

        # Filter drills relevant to the pack theme
        name_lower = pack["name"].lower()
        if "bb" in name_lower or "defend" in name_lower:
            filtered = [d for d in all_drills if d["position"] == "BB"]
        elif "river" in name_lower or "blocker" in name_lower:
            filtered = [d for d in all_drills if d["street"] == "river"]
        elif "station" in name_lower:
            filtered = [d for d in all_drills if "station" in d["title"]]
        elif "bubble" in name_lower or "icm" in name_lower:
            filtered = [d for d in all_drills if d["icm"] in ("bubble", "final table")]
        elif "maniac" in name_lower:
            filtered = [d for d in all_drills if "maniac" in d["title"]]
        elif "value" in name_lower:
            filtered = [d for d in all_drills if d["street"] in ("turn", "river")]
        elif "boss" in name_lower or "final" in name_lower:
            filtered = [d for d in all_drills if d["icm"] == "final table"]
        else:
            filtered = all_drills

        if len(filtered) < total:
            filtered = all_drills
        self.pack_drills = filtered[:total]
        self.pack_index = 0
        self.pack_correct = 0
        self.pack_ev_loss = 0.0
        self.pack_title.setText(f"Combat: {pack['name']} | {pack['difficulty']}")
        self.stack.setCurrentWidget(self.drill_page)
        self._load_combat_spot()

    def _load_combat_spot(self) -> None:
        if self.pack_index >= len(self.pack_drills):
            self._show_results()
            return

        spot = self.pack_drills[self.pack_index]
        self.state.selected_spot = spot
        total = len(self.pack_drills)
        pct = int(100 * self.pack_index / total) if total > 0 else 0
        self.progress_label.setText(f"{self.pack_index + 1} / {total}")
        self.progress_bar.setValue(pct)

        render_spot_on_table(self.table, spot)
        is_boss = self.pack_index == total - 1
        boss_tag = " 🏆 BOSS HAND" if is_boss else ""
        self.spot_label.setText(f"{spot['id']}{boss_tag} | {spot['title']}")
        self.spot_meta.setText(
            f"{spot['format']} | {spot['table']} | {spot['pot_type']} | "
            f"{spot['stack_bb']}bb | {spot['board_texture']} | ICM {spot['icm']}"
        )
        self.spot_history.setText(spot["action_history"])

        _clear_layout(self.action_layout)
        for action in spot["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self._answer(a))
            self.action_layout.addWidget(button)

        self.feedback_text.setText(f"Spot {self.pack_index + 1}/{total} — choose wisely.")
        self.feedback_text.setObjectName("Muted")
        self.feedback_text.style().unpolish(self.feedback_text)
        self.feedback_text.style().polish(self.feedback_text)

    def _answer(self, action: str) -> None:
        spot = self.pack_drills[self.pack_index]
        result = compare_action(spot, action)
        self.pack_ev_loss += result["ev_loss"]

        if result["is_correct"]:
            self.pack_correct += 1

        is_boss = self.pack_index == len(self.pack_drills) - 1
        color = "Green" if result["is_correct"] else "Red"
        self.feedback_text.setObjectName(color)
        self.feedback_text.style().unpolish(self.feedback_text)
        self.feedback_text.style().polish(self.feedback_text)

        boss_msg = " 🏆 Boss hand complete!" if is_boss else ""
        self.feedback_text.setText(
            f"Hero {action} | Best: {result['best_action']} | EV loss: {result['ev_loss']:.2f}bb | "
            f"{'✓ Correct' if result['is_correct'] else '✗ Mistake'}{boss_msg}"
        )
        self.coach_message.emit(explain_spot(spot, action))
        self.pack_index += 1

        # Auto-advance after short delay conceptually (immediate for MVP)
        if self.pack_index < len(self.pack_drills):
            # Add a "Next" button
            _clear_layout(self.action_layout)
            next_btn = QPushButton("Next Spot →")
            next_btn.setObjectName("PrimaryButton")
            next_btn.clicked.connect(self._load_combat_spot)
            self.action_layout.addWidget(next_btn)
        else:
            _clear_layout(self.action_layout)
            finish_btn = QPushButton("See Results →")
            finish_btn.setObjectName("SuccessButton")
            finish_btn.clicked.connect(self._show_results)
            self.action_layout.addWidget(finish_btn)

    def _show_results(self) -> None:
        total = len(self.pack_drills)
        accuracy = 100 * self.pack_correct / total if total > 0 else 0
        avg_ev = self.pack_ev_loss / total if total > 0 else 0
        pack_name = self.active_pack["name"] if self.active_pack else "Combat Pack"
        difficulty = self.active_pack["difficulty"] if self.active_pack else "—"

        if accuracy >= 85:
            grade = "🏆 ELITE — Pack mastered!"
            grade_color = "Green"
        elif accuracy >= 70:
            grade = "⭐ SOLID — Good performance, minor leaks remain."
            grade_color = "Cyan"
        elif accuracy >= 50:
            grade = "⚠ DEVELOPING — Review mistakes and retry."
            grade_color = "Amber"
        else:
            grade = "❌ NEEDS WORK — Focus drills on this weakness."
            grade_color = "Red"

        self.result_title.setText(f"Combat Pack Complete: {pack_name}")
        self.result_summary.setText(
            f"Difficulty: {difficulty}\n"
            f"Spots completed: {total}\n"
            f"Correct: {self.pack_correct} / {total} ({accuracy:.0f}%)\n"
            f"Total EV loss: {self.pack_ev_loss:.2f}bb\n"
            f"Average EV loss: {avg_ev:.2f}bb per decision"
        )
        self.result_detail.setText(
            f"Boss hand: {'✓ Conquered' if self.pack_correct > total * 0.7 else '✗ Not yet'}\n"
            f"Reward: {self.active_pack['reward'] if self.active_pack else 'XP +100'}"
        )
        self.result_grade.setText(grade)
        self.result_grade.setObjectName(grade_color)
        self.result_grade.style().unpolish(self.result_grade)
        self.result_grade.style().polish(self.result_grade)

        self.stack.setCurrentWidget(self.results_page)

    def _retry_pack(self) -> None:
        if self.active_pack:
            self._start_pack(self.active_pack)

    def _back_to_select(self) -> None:
        self.stack.setCurrentWidget(self.select_page)


class _CombatPackCard(QFrame):
    start_clicked = Signal(dict)

    def __init__(self, pack: dict):
        super().__init__()
        self.pack = pack
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)

        title = QLabel(pack["name"])
        title.setObjectName("SectionTitle")
        meta = QLabel(
            f"{pack['spots']} spots | {pack['difficulty']} | "
            f"Score target: {pack['skill_score']} | Boss: {pack['boss_hand']}"
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        reward = QLabel(f"Reward: {pack['reward']}")
        reward.setObjectName("Cyan")
        start = QPushButton("Start Combat")
        start.setObjectName("PrimaryButton")
        start.clicked.connect(lambda: self.start_clicked.emit(self.pack))

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(reward)
        layout.addWidget(start)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget:
            widget.deleteLater()
        if child:
            _clear_layout(child)
