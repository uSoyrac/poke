from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import dashboard_metrics, leaks, study_plan
from app.training.mastery_model import demo_skill_tree
from app.ui.components.leak_card import LeakCard
from app.ui.components.metric_card import MetricCard


class MiniSparkline(QWidget):
    """Tiny inline sparkline chart."""

    def __init__(self, data: list[float], color: str = "#22D3EE"):
        super().__init__()
        self.data = data
        self.color = QColor(color)
        self.setFixedHeight(36)
        self.setMinimumWidth(100)

    def paintEvent(self, event) -> None:
        if not self.data or len(self.data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin = 4
        min_val = min(self.data) * 0.95
        max_val = max(self.data) * 1.05
        val_range = max(max_val - min_val, 1)

        # Fill area
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        points = []
        for i, val in enumerate(self.data):
            x = margin + int((w - margin * 2) * i / (len(self.data) - 1))
            y = margin + int((h - margin * 2) * (1 - (val - min_val) / val_range))
            points.append((x, y))

        fill = QColor(self.color)
        fill.setAlpha(25)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        poly = [(points[0][0], h - margin)] + points + [(points[-1][0], h - margin)]
        painter.drawPolygon(QPolygon([QPoint(x, y) for x, y in poly]))

        painter.setPen(QPen(self.color, 2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        painter.setBrush(self.color)
        x, y = points[-1]
        painter.drawEllipse(x - 3, y - 3, 6, 6)
        painter.end()


class SkillNodeWidget(QFrame):
    """Compact skill node display."""

    def __init__(self, node: dict):
        super().__init__()
        self.setObjectName("Elevated")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        icon = QLabel(node["icon"])
        icon.setFixedWidth(22)
        name = QLabel(node["name"])
        name.setObjectName("Muted")
        name.setFixedWidth(120)
        level = QLabel(f"Lv.{node['level']}")
        level.setObjectName("Cyan")
        level.setFixedWidth(35)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(node["progress"]))
        bar.setFormat(f"{node['xp']}/{node['xp_next']}xp")
        bar.setMaximumHeight(14)
        layout.addWidget(icon)
        layout.addWidget(name)
        layout.addWidget(level)
        layout.addWidget(bar, 1)


class AchievementBadge(QFrame):
    """Compact achievement badge."""

    def __init__(self, ach: dict):
        super().__init__()
        self.setObjectName("Elevated" if ach["unlocked"] else "Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        icon = QLabel(ach["icon"])
        icon.setFixedWidth(22)
        name = QLabel(ach["name"])
        name.setObjectName("Green" if ach["unlocked"] else "Muted")
        status = QLabel("✓" if ach["unlocked"] else "🔒")
        status.setFixedWidth(20)
        layout.addWidget(icon)
        layout.addWidget(name, 1)
        layout.addWidget(status)


class DashboardScreen(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        metrics = dashboard_metrics()
        skill_tree = demo_skill_tree()
        tree_summary = skill_tree.get_summary()

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

        # === HEADER ===
        header = QLabel("Dashboard")
        header.setObjectName("Title")
        layout.addWidget(header)

        # === DAILY GOAL + ACTION BUTTONS ===
        goal = QFrame()
        goal.setObjectName("Card")
        goal_layout = QHBoxLayout(goal)
        goal_layout.setContentsMargins(14, 12, 14, 12)
        goal_left = QVBoxLayout()
        goal_text = QLabel(f"🎯 Today's training target: {metrics['daily_goal']}")
        goal_text.setObjectName("SectionTitle")
        streak_text = QLabel(f"🔥 {metrics['streak']}-day streak | Skill Score: {metrics['skill_score']} | Level: {tree_summary['overall_level']}")
        streak_text.setObjectName("Cyan")
        goal_left.addWidget(goal_text)
        goal_left.addWidget(streak_text)
        goal_layout.addLayout(goal_left, 1)
        for label, screen, style in [
            ("▶ Start Training", "Spot Practice Trainer", "PrimaryButton"),
            ("📊 Review Hands", "Hand History Analyzer", ""),
            ("🎮 Fast Play", "Fast Play Simulator", ""),
            ("🤖 Ask AI Coach", "AI Poker Coach", ""),
        ]:
            button = QPushButton(label)
            button.setObjectName(style)
            button.clicked.connect(lambda checked=False, target=screen: self.navigate_requested.emit(target))
            goal_layout.addWidget(button)
        layout.addWidget(goal)

        # === METRIC CARDS ===
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

        # === MIDDLE ROW: LEAKS + PROGRESS + SKILL TREE ===
        middle = QHBoxLayout()

        # Left: Top Leaks
        leak_panel = QFrame()
        leak_panel.setObjectName("DataPanel")
        leak_layout = QVBoxLayout(leak_panel)
        leak_title = QLabel("🔴 Top Leaks")
        leak_title.setObjectName("SectionTitle")
        leak_layout.addWidget(leak_title)
        for leak in leaks()[:3]:
            leak_layout.addWidget(LeakCard(leak))
        leak_btn = QPushButton("View All Leaks →")
        leak_btn.clicked.connect(lambda: self.navigate_requested.emit("Leak Finder"))
        leak_layout.addWidget(leak_btn)
        middle.addWidget(leak_panel, 2)

        # Center: 7-Day Progress + Expensive Spots
        center_panel = QFrame()
        center_panel.setObjectName("DataPanel")
        center_layout = QVBoxLayout(center_panel)
        progress_title = QLabel("📈 7-Day Progress")
        progress_title.setObjectName("SectionTitle")
        center_layout.addWidget(progress_title)
        sparkline_row = QHBoxLayout()
        sparkline_row.addWidget(MiniSparkline([float(v) for v in metrics["progress_7d"]], "#22D3EE"))
        sparkline_row.addWidget(QLabel(f"{metrics['progress_7d'][-1]}%"))
        center_layout.addLayout(sparkline_row)

        center_layout.addWidget(QLabel("💸 Most expensive spots:"))
        for spot in metrics["expensive_spots"][:4]:
            label = QLabel(f"  • {spot}")
            label.setWordWrap(True)
            label.setObjectName("Muted")
            center_layout.addWidget(label)

        # Study plan preview
        plan_title = QLabel("📋 Active Study Plan")
        plan_title.setObjectName("SectionTitle")
        center_layout.addWidget(plan_title)
        for day in study_plan()[:3]:
            label = QLabel(f"{day['day']}: {day['focus']} | {day['target']}")
            label.setWordWrap(True)
            label.setObjectName("Green")
            center_layout.addWidget(label)
        plan_btn = QPushButton("Open Study Planner →")
        plan_btn.clicked.connect(lambda: self.navigate_requested.emit("Study Planner"))
        center_layout.addWidget(plan_btn)
        center_layout.addStretch(1)
        middle.addWidget(center_panel, 2)

        # Right: Skill Tree Summary
        skill_panel = QFrame()
        skill_panel.setObjectName("DataPanel")
        skill_layout = QVBoxLayout(skill_panel)
        skill_title = QLabel("🌳 Skill Tree")
        skill_title.setObjectName("SectionTitle")
        skill_layout.addWidget(skill_title)
        skill_summary = QLabel(
            f"Overall Level: {tree_summary['overall_level']} | "
            f"Mastery: {tree_summary['overall_mastery']}% | "
            f"Total XP: {tree_summary['total_xp']}"
        )
        skill_summary.setObjectName("Cyan")
        skill_layout.addWidget(skill_summary)

        for node in tree_summary["categories"][:6]:
            skill_layout.addWidget(SkillNodeWidget(node))

        more_btn = QPushButton("View Full Skill Tree →")
        more_btn.clicked.connect(lambda: self.navigate_requested.emit("Reports"))
        skill_layout.addWidget(more_btn)

        # Achievements
        ach_title = QLabel(f"🏆 Achievements ({tree_summary['achievements_unlocked']}/{tree_summary['achievements_total']})")
        ach_title.setObjectName("SectionTitle")
        skill_layout.addWidget(ach_title)

        all_achievements = list(skill_tree.achievements.values())
        unlocked_first = sorted(all_achievements, key=lambda a: (not a.unlocked, a.name))
        for ach in unlocked_first[:5]:
            skill_layout.addWidget(AchievementBadge(ach.to_dict()))

        skill_layout.addStretch(1)
        middle.addWidget(skill_panel, 2)

        layout.addLayout(middle)

        # === COMPLIANCE STATUS ===
        compliance = QFrame()
        compliance.setObjectName("Card")
        comp_layout = QHBoxLayout(compliance)
        comp_layout.setContentsMargins(14, 8, 14, 8)
        comp_icon = QLabel("🔒")
        comp_text = QLabel("RTA Guard: Strict Mode Active — Offline-only training, no HUD/overlay/live advice")
        comp_text.setObjectName("Green")
        comp_btn = QPushButton("View Compliance →")
        comp_btn.clicked.connect(lambda: self.navigate_requested.emit("Settings / Compliance Guard"))
        comp_layout.addWidget(comp_icon)
        comp_layout.addWidget(comp_text, 1)
        comp_layout.addWidget(comp_btn)
        layout.addWidget(compliance)
