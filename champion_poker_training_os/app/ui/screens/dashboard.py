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

from app.core.app_state import AppState
from app.db.seed_data import dashboard_metrics, leaks, study_plan
from app.ui.components.leak_card import LeakCard
from app.ui.components.metric_card import MetricCard


class DashboardScreen(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        metrics = dashboard_metrics()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        header = QLabel("Dashboard")
        header.setObjectName("Title")
        layout.addWidget(header)

        goal = QFrame()
        goal.setObjectName("Card")
        goal_layout = QHBoxLayout(goal)
        goal_layout.setContentsMargins(14, 12, 14, 12)
        goal_text = QLabel(f"Today's training target: {metrics['daily_goal']}")
        goal_text.setObjectName("SectionTitle")
        goal_layout.addWidget(goal_text, 1)
        for label, screen in [
            ("Start Training", "Spot Practice Trainer"),
            ("Review Worst Hands", "Hand History Analyzer"),
            ("Play Fast Simulation", "Fast Play Simulator"),
            ("Ask AI Coach", "AI Poker Coach"),
        ]:
            button = QPushButton(label)
            button.setObjectName("PrimaryButton" if label == "Start Training" else "")
            button.clicked.connect(lambda checked=False, target=screen: self.navigate_requested.emit(target))
            goal_layout.addWidget(button)
        layout.addWidget(goal)

        cards = QGridLayout()
        card_data = [
            ("Drills Today", str(metrics["drills_today"]), "daily pace +12"),
            ("Preflop Accuracy", f"{metrics['preflop_accuracy']}%", "range work stable"),
            ("Postflop Accuracy", f"{metrics['postflop_accuracy']}%", "flop/turn repair"),
            ("River Decision Score", f"{metrics['river_score']}%", "blocker leaks active"),
            ("ICM Discipline", f"{metrics['icm_discipline']}%", "bubble calls improving"),
            ("Math Reflex Score", f"{metrics['math_reflex']}%", "alpha/MDF ready"),
            ("EV Loss / 100 Decisions", f"{metrics['ev_loss_per_100']:.1f}bb", "target < 20bb", "Amber"),
            ("Personal Skill Score", str(metrics["skill_score"]), f"{metrics['streak']}-day streak", "Green"),
        ]
        for idx, item in enumerate(card_data):
            title, value, detail = item[:3]
            accent = item[3] if len(item) > 3 else "Cyan"
            cards.addWidget(MetricCard(title, value, detail, accent), idx // 4, idx % 4)
        layout.addLayout(cards)

        middle = QHBoxLayout()
        leak_panel = QFrame()
        leak_panel.setObjectName("DataPanel")
        leak_layout = QVBoxLayout(leak_panel)
        leak_title = QLabel("Top Leaks")
        leak_title.setObjectName("SectionTitle")
        leak_layout.addWidget(leak_title)
        for leak in leaks()[:3]:
            leak_layout.addWidget(LeakCard(leak))
        middle.addWidget(leak_panel, 2)

        right_panel = QFrame()
        right_panel.setObjectName("DataPanel")
        right_layout = QVBoxLayout(right_panel)
        progress_title = QLabel("7-Day Progress")
        progress_title.setObjectName("SectionTitle")
        right_layout.addWidget(progress_title)
        progress = QLabel("  ".join(f"{v}%" for v in metrics["progress_7d"]))
        progress.setObjectName("Cyan")
        right_layout.addWidget(progress)
        right_layout.addWidget(QLabel("Most expensive spots"))
        for spot in metrics["expensive_spots"]:
            label = QLabel(f"- {spot}")
            label.setWordWrap(True)
            label.setObjectName("Muted")
            right_layout.addWidget(label)
        plan_title = QLabel("Active Study Plan")
        plan_title.setObjectName("SectionTitle")
        right_layout.addWidget(plan_title)
        for day in study_plan()[:3]:
            label = QLabel(f"{day['day']}: {day['focus']} | {day['target']}")
            label.setWordWrap(True)
            label.setObjectName("Green")
            right_layout.addWidget(label)
        right_layout.addStretch(1)
        middle.addWidget(right_panel, 1)
        layout.addLayout(middle)

