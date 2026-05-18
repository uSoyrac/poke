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
from app.db.repository import imported_hands_count
from app.db.seed_data import dashboard_metrics, leaks, study_plan
from app.training.mastery_model import demo_skill_tree
from app.ui.components.leak_card import LeakCard
from app.ui.components.metric_card import MetricCard
from app.ui.components.poke import (PokeBtn, PokeCard, PokePageHeader,
                                     PokeStat, PokeTag)
from app.ui.components.weekly_progress import WeeklyProgressChart
from app.ui.theme import poke_tokens as t


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

        # ── Live data overlay — read from mistakes_queue + tournament_archive ──
        try:
            from app.db.mistakes_queue import load_mistakes
            all_m = load_mistakes()
            open_leaks    = [m for m in all_m if not m.drilled]
            drilled_leaks = [m for m in all_m if m.drilled]
            # Recompute accuracy from real persisted mistakes
            if state.completed_drills > 0:
                metrics["drills_today"] = state.completed_drills
                metrics["skill_score"] = max(50, 100 - len(open_leaks) * 2)
            # Replace ev_loss_per_100 with real running tally
            if open_leaks:
                metrics["ev_loss_per_100"] = round(
                    sum(m.ev_loss for m in open_leaks) * 100
                    / max(1, len(open_leaks) * 10), 1
                )
            # Per-street accuracy bucketed from mistakes
            preflop_m  = [m for m in open_leaks if m.pot_type in ("SRP","3BP","4BP")]
            postflop_m = [m for m in open_leaks if m.context in
                          ("postflop_trainer", "river_trainer")]
            river_m    = [m for m in open_leaks if m.context == "river_trainer"]
            icm_m      = [m for m in open_leaks if m.pot_type == "ICM"]
            # Lower accuracy if more open leaks of that type
            if preflop_m:
                metrics["preflop_accuracy"]  = max(40, 95 - len(preflop_m) * 3)
            if postflop_m:
                metrics["postflop_accuracy"] = max(40, 90 - len(postflop_m) * 3)
            if river_m:
                metrics["river_score"]       = max(40, 85 - len(river_m) * 3)
            if icm_m:
                metrics["icm_discipline"]    = max(40, 88 - len(icm_m) * 4)
        except Exception:
            pass
        try:
            from app.db.tournament_archive import load_archive
            arch = load_archive()
            if arch:
                cashed = sum(1 for r in arch if r.cashed)
                metrics["streak"] = cashed
        except Exception:
            pass

        # ── Outer scroll + Poke background ───────────────────────────
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("DashboardRoot")
        self.setStyleSheet(f"#DashboardRoot {{ background: {t.BG}; }}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {t.BG}; border: 0; }}"
            f"QScrollBar:vertical {{ width: 8px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {t.LINE_2}; }}"
        )
        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {t.BG}; }}")
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(t.PAGE_PAD, t.PAGE_PAD, t.PAGE_PAD, 48)
        layout.setSpacing(28)

        # === POKE PAGE HEADER ===
        header_action = PokeBtn("Resume training", variant="primary",
                                 size="md", kbd="↵")
        header_action.clicked.connect(
            lambda: self.navigate_requested.emit("Spot Practice Trainer"))
        header = PokePageHeader(
            num="01 / Dashboard",
            title="Your <em>edge</em>, at a glance.",
            sub=(f"Today's goal: {metrics['daily_goal']}.  "
                 f"Skill score {metrics['skill_score']} · "
                 f"level {tree_summary['overall_level']} · "
                 f"{metrics['streak']} ITM tournaments."),
            actions=header_action,
        )
        layout.addWidget(header)

        # === SECONDARY ACTION ROW (chip-like buttons) ===
        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        for label, screen in [
            ("Inspect hands",   "Hand History Analyzer"),
            ("Fast play",       "Fast Play Simulator"),
            ("Ask AI coach",    "AI Poker Coach"),
            ("Open leak finder","Leak Finder"),
        ]:
            b = PokeBtn(label, variant="ghost", size="md")
            b.clicked.connect(lambda _=False, tgt=screen:
                              self.navigate_requested.emit(tgt))
            action_row.addWidget(b)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        # === KPI STATS GRID (8 cards) ===
        try:
            from app.db.mistakes_queue import load_mistakes
            all_m = load_mistakes()
            open_n = sum(1 for m in all_m if not m.drilled)
            drilled_n = sum(1 for m in all_m if m.drilled)
            leak_detail = f"{open_n} open · {drilled_n} drilled"
        except Exception:
            leak_detail = "no data yet"

        kpi_grid = QGridLayout()
        kpi_grid.setHorizontalSpacing(10)
        kpi_grid.setVerticalSpacing(10)
        kpi_data = [
            ("Drills today",  str(metrics["drills_today"]),   None,    "daily pace"),
            ("Preflop acc",   f"{metrics['preflop_accuracy']}",  "%",  "range work"),
            ("Postflop acc",  f"{metrics['postflop_accuracy']}", "%",  "flop / turn"),
            ("River score",   f"{metrics['river_score']}",       "%",  "blocker aware"),
            ("ICM discipline",f"{metrics['icm_discipline']}",    "%",  "bubble calls"),
            ("Math reflex",   f"{metrics['math_reflex']}",       "%",  "alpha / MDF"),
            ("EV loss / 100", f"{metrics['ev_loss_per_100']:.1f}", "bb", "target < 20bb"),
            ("Skill score",   str(metrics["skill_score"]),     None,   leak_detail),
        ]
        for idx, (lbl, val, unit, sub) in enumerate(kpi_data):
            kpi_grid.addWidget(PokeStat(lbl, val, unit=unit, sub=sub),
                                idx // 4, idx % 4)
        layout.addLayout(kpi_grid)

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

        # === ADAPTIVE ENGINE PANEL ===
        engine = state.adaptive_engine()
        sizes = engine.queue_size()
        weakness = engine.weakness_summary(top_n=5)
        try:
            imp_count = imported_hands_count()
        except Exception:
            imp_count = 0

        ae_card = QFrame()
        ae_card.setObjectName("DataPanel")
        ae_layout = QVBoxLayout(ae_card)
        ae_layout.setContentsMargins(14, 12, 14, 12)
        ae_title_row = QHBoxLayout()
        ae_title = QLabel("🧠 Adaptive Training Queue")
        ae_title.setObjectName("SectionTitle")
        ae_title_row.addWidget(ae_title)
        ae_title_row.addStretch(1)
        ae_practice_btn = QPushButton("▶ Resume training (next mistake)")
        ae_practice_btn.setObjectName("PrimaryButton")
        ae_practice_btn.clicked.connect(self._resume_training)
        ae_title_row.addWidget(ae_practice_btn)
        ae_layout.addLayout(ae_title_row)

        ae_metrics = QHBoxLayout()
        for label, value, color in [
            ("Tracked spots", str(sizes["tracked"]), "Cyan"),
            ("Mistakes pending", str(sizes["mistakes_pending"]), "Red" if sizes["mistakes_pending"] else "Muted"),
            ("Due for review", str(sizes["due_for_review"]), "Amber" if sizes["due_for_review"] else "Muted"),
            ("Imported hands", str(imp_count), "Green" if imp_count else "Muted"),
        ]:
            cell = QFrame()
            cell.setObjectName("Card")
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(12, 8, 12, 8)
            l1 = QLabel(label)
            l1.setObjectName("Muted")
            l2 = QLabel(value)
            l2.setObjectName(color)
            l2.setStyleSheet("font-size: 22px; font-weight: 800;")
            cell_layout.addWidget(l1)
            cell_layout.addWidget(l2)
            ae_metrics.addWidget(cell)
        ae_layout.addLayout(ae_metrics)

        # 7-day progress chart (drills + hands + accuracy)
        chart_title = QLabel("📈 Last 7 days")
        chart_title.setObjectName("Muted")
        ae_layout.addWidget(chart_title)
        ae_layout.addWidget(WeeklyProgressChart())

        if weakness:
            weak_title = QLabel("Top weaknesses (rolling EV loss):")
            weak_title.setObjectName("Muted")
            ae_layout.addWidget(weak_title)
            for w in weakness:
                row = QHBoxLayout()
                spot_lbl = QLabel(w["spot_id"])
                spot_lbl.setObjectName("Cyan")
                spot_lbl.setFixedWidth(120)
                acc_lbl = QLabel(f"{w['accuracy']:.0f}% acc · {w['attempts']} att")
                acc_lbl.setObjectName("Muted")
                ev_lbl = QLabel(f"-{w['rolling_ev_loss']:.2f}bb")
                ev_lbl.setObjectName("Red")
                ev_lbl.setStyleSheet("font-weight: 800;")
                row.addWidget(spot_lbl)
                row.addWidget(acc_lbl, 1)
                row.addWidget(ev_lbl)
                ae_layout.addLayout(row)
        else:
            empty = QLabel("Henüz drill çözülmedi. Spot Practice Trainer'a git ve birkaç soruya cevap ver — burada zayıflıkların listelenecek.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            ae_layout.addWidget(empty)
        layout.addWidget(ae_card)

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

    def _resume_training(self) -> None:
        """Pick the top of the adaptive mistake queue (or top weakness) and route to Spot Trainer."""
        engine = self.state.adaptive_engine()
        target: str | None = None
        if engine.mistake_queue:
            target = engine.mistake_queue[0]
        elif engine.spots:
            weak = engine.weakness_summary(top_n=1)
            target = weak[0]["spot_id"] if weak else None
        if target:
            self.state.pending_spot_id = target
        self.navigate_requested.emit("Spot Practice Trainer")
