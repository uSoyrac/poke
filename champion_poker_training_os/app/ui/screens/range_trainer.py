from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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

from app.core.app_state import AppState
from app.ui.components.range_grid import RangeGrid


MODES = [
    ("RFI", "100bb cash"),
    ("BB defend", "BB vs BTN"),
    ("SB strategy", "SB vs BB"),
    ("BTN steal", "Late position open"),
    ("vs RFI", "Call / 3bet decisions"),
    ("vs 3bet", "4bet / call / fold"),
    ("15bb push/fold", "MTT short stack"),
    ("Final table ICM", "Pay jump pressure"),
]


def hand_combos(hand: str) -> int:
    if len(hand) == 2:
        return 6
    if hand.endswith("s"):
        return 4
    return 12


class RangeTrainerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.attempts = 0
        self.best_score = 0

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

        title = QLabel("Preflop Range Trainer")
        title.setObjectName("Title")
        layout.addWidget(title)

        # Mode + workflow controls
        controls = QFrame()
        controls.setObjectName("Card")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 10, 14, 10)
        controls_layout.addWidget(QLabel("Module"))
        self.mode = QComboBox()
        for label, _ in MODES:
            self.mode.addItem(label)
        self.mode.currentTextChanged.connect(self._mode_changed)
        controls_layout.addWidget(self.mode)
        controls_layout.addSpacing(20)

        controls_layout.addWidget(QLabel("Workflow"))
        self.workflow = QComboBox()
        self.workflow.addItems([
            "Quiz: select range (hide solver)",
            "Study: show solver range",
            "Mistakes only (deviations)",
        ])
        self.workflow.currentTextChanged.connect(self._workflow_changed)
        controls_layout.addWidget(self.workflow)
        controls_layout.addStretch(1)

        self.clear_btn = QPushButton("Clear selection")
        self.clear_btn.clicked.connect(self._clear)
        self.submit_btn = QPushButton("Submit answer")
        self.submit_btn.setObjectName("PrimaryButton")
        self.submit_btn.clicked.connect(self._submit)
        controls_layout.addWidget(self.clear_btn)
        controls_layout.addWidget(self.submit_btn)
        layout.addWidget(controls)

        # Grid + side scoreboard
        body_row = QHBoxLayout()
        body_row.setSpacing(14)

        self.grid = RangeGrid(self.mode.currentText(), selectable=True)
        self.grid.selection_changed.connect(self._selection_changed)
        self.grid.set_show_frequencies(False)
        grid_card = QFrame()
        grid_card.setObjectName("Card")
        grid_card_layout = QVBoxLayout(grid_card)
        grid_card_layout.setContentsMargins(14, 14, 14, 14)
        grid_card_layout.addWidget(self.grid)
        body_row.addWidget(grid_card, 3)

        # Side panel: scoreboard + legend
        side = QVBoxLayout()
        side.setSpacing(12)

        self.scoreboard = QFrame()
        self.scoreboard.setObjectName("Card")
        sb_layout = QVBoxLayout(self.scoreboard)
        sb_layout.setContentsMargins(14, 14, 14, 14)
        sb_layout.setSpacing(8)
        sb_title = QLabel("Quiz Scoreboard")
        sb_title.setObjectName("SectionTitle")
        sb_layout.addWidget(sb_title)
        self.metrics = QGridLayout()
        self.metrics.setHorizontalSpacing(20)
        self._metric_labels: dict[str, QLabel] = {}
        rows = [
            ("Selected combos", "0", None),
            ("Solver combos", "0", None),
            ("Match rate", "—", "Cyan"),
            ("False positives", "0", "Red"),
            ("Missed combos", "0", "Amber"),
            ("EV-weighted score", "0", "Green"),
        ]
        for r, (label, val, color) in enumerate(rows):
            name_lbl = QLabel(label)
            name_lbl.setObjectName("Muted")
            value_lbl = QLabel(val)
            if color:
                value_lbl.setObjectName(color)
            self.metrics.addWidget(name_lbl, r, 0)
            self.metrics.addWidget(value_lbl, r, 1)
            self._metric_labels[label] = value_lbl
        sb_layout.addLayout(self.metrics)
        side.addWidget(self.scoreboard)

        self.feedback = QFrame()
        self.feedback.setObjectName("Card")
        fb_layout = QVBoxLayout(self.feedback)
        fb_layout.setContentsMargins(14, 14, 14, 14)
        fb_title = QLabel("Coach Feedback")
        fb_title.setObjectName("SectionTitle")
        fb_layout.addWidget(fb_title)
        self.feedback_text = QLabel(
            "Quiz modunda solver range gizli. Oynarsam dediğin elleri tıkla, "
            "sonra Submit ile karşılaştır. Hatalı seçimler turuncu kenar ile işaretlenir."
        )
        self.feedback_text.setWordWrap(True)
        self.feedback_text.setObjectName("Muted")
        fb_layout.addWidget(self.feedback_text)
        side.addWidget(self.feedback)

        legend = QFrame()
        legend.setObjectName("Card")
        leg_layout = QVBoxLayout(legend)
        leg_layout.setContentsMargins(14, 14, 14, 14)
        leg_title = QLabel("Frequency Legend")
        leg_title.setObjectName("SectionTitle")
        leg_layout.addWidget(leg_title)
        for txt, color in [
            ("Pure raise (≥80%)", "Green"),
            ("Mixed call (50–79%)", "Cyan"),
            ("Mix / bluff (25–49%)", "Cyan"),
            ("Fold (<25%)", "Muted"),
        ]:
            row = QLabel(f"●  {txt}")
            row.setObjectName(color)
            leg_layout.addWidget(row)
        side.addWidget(legend)
        side.addStretch(1)

        side_box = QWidget()
        side_box.setLayout(side)
        side_box.setMinimumWidth(280)
        body_row.addWidget(side_box, 1)

        layout.addLayout(body_row)

        layout.addStretch(1)

    # --- handlers --------------------------------------------------------
    def _mode_changed(self, mode: str) -> None:
        self.grid.set_mode(mode)
        self.grid.clear_selection()
        # Re-apply current workflow visibility
        self._workflow_changed(self.workflow.currentText())
        self._reset_score()
        self.feedback_text.setText(
            f"{mode} moduna geçildi. Soldaki ızgaradan oynayacağın combo'ları tıkla."
        )

    def _workflow_changed(self, label: str) -> None:
        if label.startswith("Study"):
            self.grid.set_show_frequencies(True)
            self.submit_btn.setEnabled(False)
            self.feedback_text.setText(
                "Study modu: solver frekansları görünür. Çalış, kalıbı oturt, sonra Quiz moduna dön."
            )
        else:
            self.grid.set_show_frequencies(False)
            self.submit_btn.setEnabled(True)
            self.feedback_text.setText(
                "Quiz modu: solver gizli. Range'i seç, Submit ile karşılaştır."
            )

    def _selection_changed(self, selection: set[str]) -> None:
        combos = sum(hand_combos(h) for h in selection)
        self._metric_labels["Selected combos"].setText(str(combos))

    def _clear(self) -> None:
        self.grid.clear_selection()
        self._reset_score()

    def _submit(self) -> None:
        solver_range = self.grid.solver_range(threshold=50)
        user_range = self.grid.selection()

        true_pos = user_range & solver_range
        false_pos = user_range - solver_range
        missed = solver_range - user_range

        user_combos = sum(hand_combos(h) for h in user_range)
        solver_combos = sum(hand_combos(h) for h in solver_range)
        match_combos = sum(hand_combos(h) for h in true_pos)
        fp_combos = sum(hand_combos(h) for h in false_pos)
        miss_combos = sum(hand_combos(h) for h in missed)

        match_rate = (match_combos / solver_combos * 100) if solver_combos else 0
        ev_score = max(0, match_combos - int(0.6 * fp_combos) - int(0.4 * miss_combos))

        self._metric_labels["Selected combos"].setText(str(user_combos))
        self._metric_labels["Solver combos"].setText(str(solver_combos))
        self._metric_labels["Match rate"].setText(f"{match_rate:.0f}%")
        self._metric_labels["False positives"].setText(str(fp_combos))
        self._metric_labels["Missed combos"].setText(str(miss_combos))
        self._metric_labels["EV-weighted score"].setText(str(ev_score))

        self.attempts += 1
        if ev_score > self.best_score:
            self.best_score = ev_score
        self.state.completed_drills += 1
        self.state.accuracy = match_rate

        # Reveal solver range so user sees deviations
        self.grid.set_show_frequencies(True)

        verdict = (
            f"Match {match_rate:.0f}% | EV-weighted skor {ev_score} | "
            f"FP {fp_combos} combo, kaçırılan {miss_combos} combo. "
        )
        if missed:
            sample = ", ".join(sorted(missed)[:6])
            verdict += f"Kaçan örnekler: {sample}. "
        if false_pos:
            sample = ", ".join(sorted(false_pos)[:6])
            verdict += f"Fazla seçilen: {sample}."
        self.feedback_text.setText(verdict)
        self.coach_message.emit(
            "Range Coach: " + verdict +
            " Bu sapmaları drill paketine alıp 3 günde tekrar ölçeceğiz."
        )

    def _reset_score(self) -> None:
        for key in ["Selected combos", "Solver combos", "False positives", "Missed combos", "EV-weighted score"]:
            self._metric_labels[key].setText("0")
        self._metric_labels["Match rate"].setText("—")
