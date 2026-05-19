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


# ── Poke-styled row primitives for Dashboard bottom panels ───────────────


def _row_frame() -> QFrame:
    """Hairline-separated row container, used for leak/skill/weakness rows."""
    f = QFrame()
    f.setAttribute(Qt.WA_StyledBackground, True)
    f.setStyleSheet(
        f"QFrame {{ background: transparent; "
        f"border-top: 1px solid {t.LINE}; }}"
    )
    return f


def _mono(text: str, color: str, size: int = 11, weight: int = 500) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-weight: {weight}; "
        f"font-size: {size}px;"
    )
    return lbl


def _grotesk(text: str, color: str, size: int = 13, weight: int = 500,
              wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; background: transparent; "
        f"font-family: 'Space Grotesk'; font-weight: {weight}; "
        f"font-size: {size}px;"
    )
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def _section_eyebrow(text: str) -> QLabel:
    """▸ PROGRESS-style mono uppercase label."""
    lbl = QLabel(f"▸  {text.upper()}")
    lbl.setStyleSheet(
        f"color: {t.MUTED}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px;"
    )
    return lbl


class _PokeLeakRow(QFrame):
    """A single leak row in the Poke style — severity tag · name · EV loss."""

    def __init__(self, leak: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#leakrow {{ background: transparent; "
            f"border-top: 1px solid {t.LINE}; }}"
        )
        self.setObjectName("leakrow")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 12, 0, 12)
        row.setSpacing(12)

        sev = leak.get("severity", "")
        tone = {"Critical": "r", "High": "r",
                "Medium": "y", "Low": "b"}.get(sev, "neutral")
        tag = PokeTag(sev or "—", tone=tone, dot=True)
        tag.setFixedWidth(96)
        row.addWidget(tag)

        body = QVBoxLayout()
        body.setSpacing(2)
        body.addWidget(_grotesk(leak["name"], t.INK, size=13, weight=600,
                                  wrap=True))
        meta = (f"{leak.get('sample_size', 0)} hands · "
                f"{leak.get('frequency_deviation', '')}")
        body.addWidget(_mono(meta, t.MUTED, size=10))
        row.addLayout(body, 1)

        ev = QLabel(f"-{leak.get('ev_lost', 0):.1f}")
        ev.setStyleSheet(
            f"color: {t.DANGER_2}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 700; font-size: 18px;"
        )
        ev.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(ev)
        unit = _mono("bb", t.MUTED, size=10)
        unit.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        row.addWidget(unit)


class _PokeSkillRow(QFrame):
    """A skill-tree category row — name · level · xp progress bar."""

    def __init__(self, node: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("skillrow")
        self.setStyleSheet(
            f"#skillrow {{ background: transparent; "
            f"border-top: 1px solid {t.LINE}; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(12)

        name = _grotesk(node["name"], t.INK, size=12, weight=500)
        name.setFixedWidth(150)
        row.addWidget(name)

        lvl = _mono(f"LV {node['level']:02d}", t.ACCENT, size=10, weight=600)
        lvl.setFixedWidth(42)
        row.addWidget(lvl)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(node["progress"]))
        bar.setTextVisible(False)
        bar.setFixedHeight(4)
        bar.setStyleSheet(
            f"QProgressBar {{ background: {t.BG}; border: 0; }}"
            f"QProgressBar::chunk {{ background: {t.ACCENT}; }}"
        )
        row.addWidget(bar, 1)

        xp = _mono(f"{node['xp']}/{node['xp_next']}", t.MUTED, size=10)
        xp.setFixedWidth(72)
        xp.setAlignment(Qt.AlignRight)
        row.addWidget(xp)


class _PokeAchievementRow(QFrame):
    """Achievement row — status dot · name · lock state."""

    def __init__(self, ach: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("achrow")
        self.setStyleSheet(
            f"#achrow {{ background: transparent; "
            f"border-top: 1px solid {t.LINE}; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)

        unlocked = bool(ach.get("unlocked"))
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {t.ACCENT if unlocked else t.DIM}; "
            f"background: transparent; font-size: 10px;"
        )
        dot.setFixedWidth(14)
        row.addWidget(dot)

        name = _grotesk(ach["name"], t.INK if unlocked else t.MUTED,
                         size=12, weight=500)
        row.addWidget(name, 1)

        status = _mono("UNLOCKED" if unlocked else "LOCKED",
                        t.ACCENT if unlocked else t.DIM, size=9, weight=600)
        row.addWidget(status)


class _PokeMetricCell(QFrame):
    """Small metric cell used in the Adaptive Queue panel."""

    def __init__(self, label: str, value: str, tone: str = "neutral",
                 parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("metriccell")
        self.setStyleSheet(
            f"#metriccell {{ background: {t.BG_2}; "
            f"border: 1px solid {t.LINE}; }}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(4)

        v.addWidget(_mono(label.upper(), t.MUTED, size=10))
        color = {"g": t.ACCENT, "r": t.DANGER_2,
                  "y": t.WARN, "b": t.INFO}.get(tone, t.INK)
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {color}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; font-size: 28px;"
        )
        v.addWidget(val)


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

        # ── Live data overlay — pull real KPIs from SQLite where available ──
        # Strategy: layer real values on top of demo `metrics`. A field is
        # only overridden if we have enough data to make it meaningful.
        # Caller can tell which fields are real via the `_real_fields` set.
        self._real_fields: set[str] = set()

        # 1) Mistakes queue → per-street accuracy + EV-loss tally
        try:
            from app.db.mistakes_queue import load_mistakes
            all_m = load_mistakes()
            open_leaks = [m for m in all_m if not m.drilled]
            drilled_leaks = [m for m in all_m if m.drilled]
            if state.completed_drills > 0:
                metrics["drills_today"] = state.completed_drills
                self._real_fields.add("drills_today")
                metrics["skill_score"] = max(50, 100 - len(open_leaks) * 2)
                self._real_fields.add("skill_score")
            if open_leaks:
                metrics["ev_loss_per_100"] = round(
                    sum(m.ev_loss for m in open_leaks) * 100
                    / max(1, len(open_leaks) * 10), 1
                )
                self._real_fields.add("ev_loss_per_100")
            preflop_m  = [m for m in open_leaks if m.pot_type in ("SRP","3BP","4BP")]
            postflop_m = [m for m in open_leaks if m.context in
                          ("postflop_trainer", "river_trainer")]
            river_m    = [m for m in open_leaks if m.context == "river_trainer"]
            icm_m      = [m for m in open_leaks if m.pot_type == "ICM"]
            if preflop_m:
                metrics["preflop_accuracy"]  = max(40, 95 - len(preflop_m) * 3)
                self._real_fields.add("preflop_accuracy")
            if postflop_m:
                metrics["postflop_accuracy"] = max(40, 90 - len(postflop_m) * 3)
                self._real_fields.add("postflop_accuracy")
            if river_m:
                metrics["river_score"]       = max(40, 85 - len(river_m) * 3)
                self._real_fields.add("river_score")
            if icm_m:
                metrics["icm_discipline"]    = max(40, 88 - len(icm_m) * 4)
                self._real_fields.add("icm_discipline")
        except Exception:
            pass

        # 2) Decision review summary — accuracy + EV-loss from played hands
        try:
            from app.db.repository import get_decision_review_summary
            ds = get_decision_review_summary(limit=500)
            if ds.get("count", 0) > 0:
                # Use accuracy as the global skill_score floor (60..100)
                acc = float(ds["accuracy"])
                metrics["skill_score"] = max(metrics.get("skill_score", 60),
                                                round(60 + acc * 0.4))
                self._real_fields.add("skill_score")
                # EV-loss real running tally if larger than the mistakes-q one
                ev_loss_pct100 = round(ds["ev_loss"] * 100 / max(ds["count"], 1), 1)
                if ev_loss_pct100 > 0:
                    metrics["ev_loss_per_100"] = ev_loss_pct100
                    self._real_fields.add("ev_loss_per_100")
                # Math reflex piggybacks on review accuracy too
                metrics["math_reflex"] = max(int(acc), 0)
                self._real_fields.add("math_reflex")
        except Exception:
            pass

        # 3) Player stats from played hands — bb/100 (display as ev-loss surrogate)
        try:
            from app.db.repository import get_player_stats
            ps = get_player_stats()
            if ps.get("total_hands", 0) > 50:
                # If hero is profitable, ev_loss/100 floors at 0; if losing,
                # show abs(bb_per_100) as the EV-leak surrogate.
                bb100 = float(ps.get("bb_per_100", 0))
                if bb100 < 0:
                    metrics["ev_loss_per_100"] = round(abs(bb100), 1)
                    self._real_fields.add("ev_loss_per_100")
        except Exception:
            pass

        # 4) Tournament archive — cashed-tournament streak
        try:
            from app.db.tournament_archive import load_archive
            arch = load_archive()
            if arch:
                metrics["streak"] = sum(1 for r in arch if r.cashed)
                self._real_fields.add("streak")
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

        # === SECONDARY ACTION ROW (chip-like buttons + data status tag) ===
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

        # Live-data status pill — number of KPIs that reflect real DB data
        n_real = len(self._real_fields)
        total_kpis = 8
        if n_real == 0:
            data_tag = PokeTag("DEMO DATA", tone="y", dot=True)
            data_tag.setToolTip(
                "Henüz yeterli el / drill yok. Tüm KPI'lar demo değer."
            )
        elif n_real >= 5:
            data_tag = PokeTag(f"LIVE · {n_real}/{total_kpis}", tone="g",
                                dot=True)
            data_tag.setToolTip(
                f"{n_real} KPI gerçek verinden hesaplandı."
            )
        else:
            data_tag = PokeTag(f"PARTIAL · {n_real}/{total_kpis}", tone="b",
                                dot=True)
            data_tag.setToolTip(
                f"{n_real} KPI gerçek veriden; geri kalanlar demo."
            )
        action_row.addWidget(data_tag)
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

        def _badge(field: str, default: str) -> str:
            """Stamp the KPI sub-line with LIVE or DEMO so the user can tell
            at a glance which numbers are sourced from real data."""
            return "● LIVE" if field in self._real_fields else default

        kpi_data = [
            ("Drills today",  str(metrics["drills_today"]),   None,
                _badge("drills_today", "daily pace")),
            ("Preflop acc",   f"{metrics['preflop_accuracy']}",  "%",
                _badge("preflop_accuracy", "range work")),
            ("Postflop acc",  f"{metrics['postflop_accuracy']}", "%",
                _badge("postflop_accuracy", "flop / turn")),
            ("River score",   f"{metrics['river_score']}",       "%",
                _badge("river_score", "blocker aware")),
            ("ICM discipline",f"{metrics['icm_discipline']}",    "%",
                _badge("icm_discipline", "bubble calls")),
            ("Math reflex",   f"{metrics['math_reflex']}",       "%",
                _badge("math_reflex", "alpha / MDF")),
            ("EV loss / 100", f"{metrics['ev_loss_per_100']:.1f}", "bb",
                _badge("ev_loss_per_100", "target < 20bb")),
            ("Skill score",   str(metrics["skill_score"]),     None,
                leak_detail if "skill_score" not in self._real_fields
                else f"● LIVE · {leak_detail}"),
        ]
        for idx, (lbl, val, unit, sub) in enumerate(kpi_data):
            kpi_grid.addWidget(PokeStat(lbl, val, unit=unit, sub=sub),
                                idx // 4, idx % 4)
        layout.addLayout(kpi_grid)

        # === MIDDLE ROW: LEAKS + PROGRESS + SKILL TREE (Poke) ===
        middle = QHBoxLayout()
        middle.setSpacing(16)

        # ── Top Leaks card ────────────────────────────────────────────
        leak_count = min(4, len(leaks()))
        leak_card = PokeCard(
            "Top leaks",
            num="A1",
            sub=f"{leak_count} OPEN",
        )
        leak_card.body_layout().setSpacing(0)
        for leak in leaks()[:4]:
            leak_card.add_to_body(_PokeLeakRow(leak))
        leak_btn = PokeBtn("View all leaks", variant="ghost",
                            size="sm", kbd="→")
        leak_btn.clicked.connect(
            lambda: self.navigate_requested.emit("Leak Finder"))
        spacer = QWidget()
        spacer.setFixedHeight(10)
        leak_card.add_to_body(spacer)
        leak_card.add_to_body(leak_btn)
        middle.addWidget(leak_card, 2)

        # ── Progress + Study Plan ─────────────────────────────────────
        prog_card = PokeCard(
            "7-day progress",
            num="A2",
            sub=f"{metrics['progress_7d'][-1]}%",
        )
        prog_card.body_layout().setSpacing(10)
        spark_row = QHBoxLayout()
        spark_row.setSpacing(10)
        spark_row.addWidget(MiniSparkline(
            [float(v) for v in metrics["progress_7d"]], t.ACCENT))
        cur = QLabel(f"{metrics['progress_7d'][-1]}%")
        cur.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; font-size: 22px;"
        )
        spark_row.addWidget(cur)
        spark_row.addStretch(1)
        prog_card.add_layout_to_body(spark_row)

        prog_card.add_to_body(_section_eyebrow("Most expensive spots"))
        for spot in metrics["expensive_spots"][:3]:
            prog_card.add_to_body(_grotesk(f"·  {spot}", t.INK_2,
                                            size=12, weight=500, wrap=True))

        prog_card.add_to_body(_section_eyebrow("Active study plan"))
        for day in study_plan()[:3]:
            prog_card.add_to_body(
                _grotesk(f"{day['day'][:3].upper()}  ·  {day['focus']}",
                          t.INK_2, size=12, weight=500, wrap=True))

        plan_btn = PokeBtn("Open study planner", variant="ghost",
                            size="sm", kbd="→")
        plan_btn.clicked.connect(
            lambda: self.navigate_requested.emit("Study Planner"))
        prog_card.add_to_body(plan_btn)
        middle.addWidget(prog_card, 2)

        # ── Skill tree + Achievements ────────────────────────────────
        skill_card = PokeCard(
            "Skill tree",
            num="A3",
            sub=f"LV {tree_summary['overall_level']}  ·  "
                f"{tree_summary['overall_mastery']}% MASTERY",
        )
        skill_card.body_layout().setSpacing(0)
        for node in tree_summary["categories"][:6]:
            skill_card.add_to_body(_PokeSkillRow(node))

        sp1 = QWidget(); sp1.setFixedHeight(10)
        skill_card.add_to_body(sp1)
        tree_btn = PokeBtn("View full tree", variant="ghost",
                            size="sm", kbd="→")
        tree_btn.clicked.connect(
            lambda: self.navigate_requested.emit("Reports"))
        skill_card.add_to_body(tree_btn)

        sp2 = QWidget(); sp2.setFixedHeight(6)
        skill_card.add_to_body(sp2)
        ach_eyebrow = QLabel(
            f"▸  ACHIEVEMENTS  ·  "
            f"{tree_summary['achievements_unlocked']}/"
            f"{tree_summary['achievements_total']}"
        )
        ach_eyebrow.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px;"
        )
        skill_card.add_to_body(ach_eyebrow)

        all_achievements = list(skill_tree.achievements.values())
        unlocked_first = sorted(all_achievements,
                                  key=lambda a: (not a.unlocked, a.name))
        for ach in unlocked_first[:4]:
            skill_card.add_to_body(_PokeAchievementRow(ach.to_dict()))

        middle.addWidget(skill_card, 2)

        layout.addLayout(middle)

        # === ADAPTIVE TRAINING QUEUE (Poke) ===
        engine = state.adaptive_engine()
        sizes = engine.queue_size()
        weakness = engine.weakness_summary(top_n=5)
        try:
            imp_count = imported_hands_count()
        except Exception:
            imp_count = 0

        ae_action = PokeBtn("Resume training", variant="primary",
                             size="sm", kbd="↵")
        ae_action.clicked.connect(self._resume_training)
        ae_card = PokeCard(
            "Adaptive training queue",
            num="A4",
            sub="NEXT MISTAKE FIRST",
            action=ae_action,
        )
        ae_card.body_layout().setSpacing(14)

        metric_row = QHBoxLayout()
        metric_row.setSpacing(10)
        metric_defs = [
            ("Tracked spots",    str(sizes["tracked"]),          "neutral"),
            ("Mistakes pending", str(sizes["mistakes_pending"]),
             "r" if sizes["mistakes_pending"] else "neutral"),
            ("Due for review",   str(sizes["due_for_review"]),
             "y" if sizes["due_for_review"] else "neutral"),
            ("Imported hands",   str(imp_count),
             "g" if imp_count else "neutral"),
        ]
        for lbl, val, tone in metric_defs:
            metric_row.addWidget(_PokeMetricCell(lbl, val, tone))
        ae_card.add_layout_to_body(metric_row)

        ae_card.add_to_body(_section_eyebrow("Last 7 days"))
        ae_card.add_to_body(WeeklyProgressChart())

        if weakness:
            ae_card.add_to_body(_section_eyebrow(
                "Top weaknesses · rolling EV loss"))
            for w in weakness:
                row = QFrame()
                row.setAttribute(Qt.WA_StyledBackground, True)
                row.setStyleSheet(
                    f"QFrame {{ background: transparent; "
                    f"border-top: 1px solid {t.LINE}; }}"
                )
                rl = QHBoxLayout(row)
                rl.setContentsMargins(0, 8, 0, 8)
                rl.setSpacing(12)
                spot = _mono(w["spot_id"], t.ACCENT, size=11, weight=600)
                spot.setFixedWidth(140)
                rl.addWidget(spot)
                rl.addWidget(_mono(
                    f"{w['accuracy']:.0f}% acc  ·  {w['attempts']} att",
                    t.MUTED, size=10), 1)
                ev = QLabel(f"-{w['rolling_ev_loss']:.2f}bb")
                ev.setStyleSheet(
                    f"color: {t.DANGER_2}; background: transparent; "
                    f"font-family: 'JetBrains Mono'; "
                    f"font-weight: 700; font-size: 14px;"
                )
                rl.addWidget(ev)
                ae_card.add_to_body(row)
        else:
            empty = _grotesk(
                "Henüz drill çözülmedi. Spot Practice Trainer'a git ve birkaç "
                "soruya cevap ver — burada zayıflıkların listelenecek.",
                t.MUTED, size=12, weight=500, wrap=True)
            ae_card.add_to_body(empty)
        layout.addWidget(ae_card)

        # === COMPLIANCE STATUS (Poke) ===
        comp = QFrame()
        comp.setAttribute(Qt.WA_StyledBackground, True)
        comp.setObjectName("ComplianceBar")
        comp.setStyleSheet(
            f"#ComplianceBar {{ background: {t.SURFACE}; "
            f"border: 1px solid {t.LINE}; }}"
        )
        cl = QHBoxLayout(comp)
        cl.setContentsMargins(18, 12, 18, 12)
        cl.setSpacing(12)
        cl.addWidget(PokeTag("STRICT", tone="g", dot=True))
        cl.addWidget(_grotesk(
            "RTA Guard active  ·  Offline-only training  ·  "
            "No HUD / overlay / live advice",
            t.INK_2, size=12, weight=500))
        cl.addStretch(1)
        comp_btn = PokeBtn("View compliance", variant="ghost",
                            size="sm", kbd="→")
        comp_btn.clicked.connect(
            lambda: self.navigate_requested.emit(
                "Settings / Compliance Guard"))
        cl.addWidget(comp_btn)
        layout.addWidget(comp)

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
