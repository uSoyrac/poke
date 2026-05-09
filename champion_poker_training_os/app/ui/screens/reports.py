from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
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
from app.db.repository import get_decision_review_summary, get_imported_hands, get_session_history
from app.db.seed_data import dashboard_metrics, leaks
from app.training.position_breakdown import compute_position_breakdown_from_rows
from app.ui.components.metric_card import MetricCard
from app.ui.components.weekly_progress import WeeklyProgressChart


class MiniChart(QWidget):
    """Simple custom-painted chart widget for trend visualization."""

    def __init__(self, data: list[float], label: str = "", color: str = "#22D3EE"):
        super().__init__()
        self.data = data
        self.chart_label = label
        self.color = QColor(color)
        self.setMinimumHeight(120)
        self.setMinimumWidth(200)

    def paintEvent(self, event) -> None:
        if not self.data or len(self.data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 30
        chart_w = w - margin * 2
        chart_h = h - margin * 2

        min_val = min(self.data) * 0.9
        max_val = max(self.data) * 1.1
        val_range = max(max_val - min_val, 1)

        # Draw grid lines
        painter.setPen(QPen(QColor("#2D3748"), 1))
        for i in range(5):
            y = margin + chart_h * i // 4
            painter.drawLine(margin, y, w - margin, y)

        # Draw axis labels
        painter.setPen(QPen(QColor("#9CA3AF"), 1))
        painter.drawText(2, margin + 4, f"{max_val:.0f}")
        painter.drawText(2, h - margin + 4, f"{min_val:.0f}")
        painter.drawText(margin, h - 5, self.chart_label)

        # Draw data points and lines
        points = []
        for i, val in enumerate(self.data):
            x = margin + int(chart_w * i / (len(self.data) - 1))
            y = margin + int(chart_h * (1 - (val - min_val) / val_range))
            points.append((x, y))

        # Fill area under curve
        painter.setPen(Qt.NoPen)
        fill_color = QColor(self.color)
        fill_color.setAlpha(30)
        painter.setBrush(fill_color)
        fill_points = [(points[0][0], margin + chart_h)] + points + [(points[-1][0], margin + chart_h)]
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        polygon = QPolygon([QPoint(x, y) for x, y in fill_points])
        painter.drawPolygon(polygon)

        # Draw line
        painter.setPen(QPen(self.color, 2))
        for i in range(len(points) - 1):
            painter.drawLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1])

        # Draw dots
        painter.setBrush(self.color)
        for x, y in points:
            painter.drawEllipse(x - 4, y - 4, 8, 8)

        # Draw value labels on dots
        painter.setPen(QPen(QColor("#E5E7EB"), 1))
        for i, (x, y) in enumerate(points):
            painter.drawText(x - 10, y - 10, f"{self.data[i]:.0f}")

        painter.end()


class ReportsScreen(QWidget):
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
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Reports")
        title.setObjectName("Title")
        header.addWidget(title)
        self.period = QComboBox()
        self.period.addItems(["Weekly", "Monthly", "Session"])
        header.addWidget(self.period)
        export = QPushButton("Export HTML/PDF Report")
        export.setObjectName("PrimaryButton")
        export.clicked.connect(lambda: self.status.setText("✓ Demo report exported: HTML/PDF adapter ready."))
        header.addWidget(export)
        layout.addLayout(header)

        self.status = QLabel("Weekly report ready.")
        self.status.setObjectName("Green")
        layout.addWidget(self.status)

        # Summary cards
        stats = QGridLayout()
        stats.addWidget(MetricCard("Skill Score", str(metrics["skill_score"]), f"{metrics['streak']}-day streak", "Green"), 0, 0)
        stats.addWidget(MetricCard("Drills Completed", "315", "this week"), 0, 1)
        stats.addWidget(MetricCard("EV Loss Trend", f"{metrics['ev_loss_per_100']:.1f}bb", "per 100 decisions", "Amber"), 0, 2)
        stats.addWidget(MetricCard("Fixed Leaks", "2", "SB overflat, delayed cbet", "Green"), 0, 3)
        layout.addLayout(stats)

        decision_summary = get_decision_review_summary()
        decision_stats = QGridLayout()
        decision_stats.addWidget(MetricCard("Decision Accuracy", f"{decision_summary['accuracy']:.0f}%", f"{decision_summary['count']} reviewed actions", "Cyan"), 0, 0)
        decision_stats.addWidget(MetricCard("Decision EV Loss", f"{decision_summary['ev_loss']:.2f}bb", "played simulations", "Amber"), 0, 1)
        decision_stats.addWidget(MetricCard("Wrong Decisions", str(decision_summary["mistakes"]), "auto drill candidates", "Red" if decision_summary["mistakes"] else "Green"), 0, 2)
        layout.addLayout(decision_stats)

        # Charts row
        charts = QHBoxLayout()

        # 7-day accuracy trend
        accuracy_chart = QFrame()
        accuracy_chart.setObjectName("Card")
        ac_layout = QVBoxLayout(accuracy_chart)
        ac_title = QLabel("7-Day Accuracy Trend")
        ac_title.setObjectName("SectionTitle")
        ac_layout.addWidget(ac_title)
        ac_layout.addWidget(MiniChart(
            [float(v) for v in metrics["progress_7d"]],
            "Mon → Sun",
            "#22D3EE",
        ))
        charts.addWidget(accuracy_chart)

        # EV loss trend
        ev_chart = QFrame()
        ev_chart.setObjectName("Card")
        ev_layout = QVBoxLayout(ev_chart)
        ev_title = QLabel("EV Loss Trend (bb/100)")
        ev_title.setObjectName("SectionTitle")
        ev_layout.addWidget(ev_title)
        ev_layout.addWidget(MiniChart(
            [29.4, 27.1, 25.8, 24.2, 23.5, 22.9, metrics["ev_loss_per_100"]],
            "Improving ↓",
            "#10B981",
        ))
        charts.addWidget(ev_chart)

        # Skill score progression
        skill_chart = QFrame()
        skill_chart.setObjectName("Card")
        sk_layout = QVBoxLayout(skill_chart)
        sk_title = QLabel("Skill Score Progression")
        sk_title.setObjectName("SectionTitle")
        sk_layout.addWidget(sk_title)
        sk_layout.addWidget(MiniChart(
            [680, 695, 710, 718, 725, 735, float(metrics["skill_score"])],
            "Rising ↑",
            "#8B5CF6",
        ))
        charts.addWidget(skill_chart)
        layout.addLayout(charts)

        # Accuracy breakdown
        breakdown = QFrame()
        breakdown.setObjectName("DataPanel")
        bd_layout = QVBoxLayout(breakdown)
        bd_title = QLabel("Accuracy Breakdown")
        bd_title.setObjectName("SectionTitle")
        bd_layout.addWidget(bd_title)

        breakdown_data = [
            ("Preflop", metrics["preflop_accuracy"], "Cyan"),
            ("Postflop", metrics["postflop_accuracy"], "Amber"),
            ("River", metrics["river_score"], "Amber"),
            ("ICM", metrics["icm_discipline"], "Green"),
            ("Math Reflex", metrics["math_reflex"], "Green"),
        ]
        for name, value, color in breakdown_data:
            row = QHBoxLayout()
            label = QLabel(name)
            label.setFixedWidth(120)
            bar = _PercentBar(value)
            pct = QLabel(f"{value}%")
            pct.setObjectName(color)
            pct.setFixedWidth(50)
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(pct)
            bd_layout.addLayout(row)
        layout.addWidget(breakdown)

        decision_card = QFrame()
        decision_card.setObjectName("DataPanel")
        decision_layout = QVBoxLayout(decision_card)
        decision_title = QLabel("🎯 Recent GTO / Exploit Decision Review")
        decision_title.setObjectName("SectionTitle")
        decision_layout.addWidget(decision_title)
        if not decision_summary["worst"]:
            empty = QLabel("Henüz oynanmış karar review yok — Play Session'da el oyna, her hero aksiyonu burada EV loss ve doğru/yanlış olarak görünecek.")
            empty.setWordWrap(True)
            empty.setObjectName("Muted")
            decision_layout.addWidget(empty)
        else:
            for item in decision_summary["worst"][:5]:
                row = QHBoxLayout()
                spot = QLabel(f"H{item['hand_id']} {item['street'].title()} {item['position']}")
                spot.setObjectName("Cyan")
                spot.setFixedWidth(130)
                action = QLabel(f"Hero {item['hero_action']} → baseline {item['solver_action']}")
                action.setObjectName("Muted")
                ev = QLabel(f"{float(item['ev_loss'] or 0):.2f}bb")
                ev.setObjectName("Red" if float(item["ev_loss"] or 0) >= 0.45 else "Amber")
                drill = QLabel(item.get("drill_target") or "")
                drill.setObjectName("Green")
                row.addWidget(spot)
                row.addWidget(action, 1)
                row.addWidget(ev)
                row.addWidget(drill, 1)
                decision_layout.addLayout(row)
        layout.addWidget(decision_card)

        # 7-day progress chart (live from played_hands + adaptive_spots)
        weekly_card = QFrame()
        weekly_card.setObjectName("DataPanel")
        weekly_layout = QVBoxLayout(weekly_card)
        weekly_title = QLabel("📈 Last 7 Days — Hands & Drills")
        weekly_title.setObjectName("SectionTitle")
        weekly_layout.addWidget(weekly_title)
        weekly_layout.addWidget(WeeklyProgressChart())
        layout.addWidget(weekly_card)

        # Position-by-position win rate breakdown
        pos_card = QFrame()
        pos_card.setObjectName("DataPanel")
        pos_layout = QVBoxLayout(pos_card)
        pos_title_row = QHBoxLayout()
        pos_title = QLabel("🎯 Position Breakdown — Win Rate")
        pos_title.setObjectName("SectionTitle")
        pos_title_row.addWidget(pos_title)
        pos_title_row.addStretch(1)
        pos_meta = QLabel("(from imported + played hands)")
        pos_meta.setObjectName("Muted")
        pos_title_row.addWidget(pos_meta)
        pos_layout.addLayout(pos_title_row)

        breakdown = self._compute_position_breakdown()
        if not breakdown:
            empty = QLabel("Henüz pozisyon verisi yok — Play Session'da oyna veya Hands sayfasından el import et.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            pos_layout.addWidget(empty)
        else:
            for entry in breakdown:
                row = QHBoxLayout()
                pos_lbl = QLabel(entry["position"])
                pos_lbl.setObjectName("Cyan")
                pos_lbl.setFixedWidth(70)
                pos_lbl.setStyleSheet("font-weight: 800;")
                count_lbl = QLabel(f"{entry['count']} hands")
                count_lbl.setObjectName("Muted")
                count_lbl.setFixedWidth(80)
                wr_bar = _PercentBar(int(entry["win_rate"]))
                wr_pct = QLabel(f"{entry['win_rate']:.0f}%")
                wr_pct.setObjectName(
                    "Green" if entry["win_rate"] >= 55
                    else "Cyan" if entry["win_rate"] >= 45
                    else "Red"
                )
                wr_pct.setFixedWidth(50)
                profit_lbl = QLabel(f"{entry['profit_bb']:+.1f}bb")
                profit_lbl.setObjectName("Green" if entry["profit_bb"] >= 0 else "Red")
                profit_lbl.setFixedWidth(70)
                row.addWidget(pos_lbl)
                row.addWidget(count_lbl)
                row.addWidget(wr_bar, 1)
                row.addWidget(wr_pct)
                row.addWidget(profit_lbl)
                pos_layout.addLayout(row)
        layout.addWidget(pos_card)

        # Active leaks
        leak_frame = QFrame()
        leak_frame.setObjectName("DataPanel")
        leak_layout = QVBoxLayout(leak_frame)
        leak_title = QLabel("Active Leaks")
        leak_title.setObjectName("SectionTitle")
        leak_layout.addWidget(leak_title)
        for leak in leaks():
            row = QHBoxLayout()
            name = QLabel(leak["name"])
            name.setObjectName("Muted")
            severity = QLabel(leak["severity"])
            severity.setObjectName("Red" if leak["severity"] in ("Critical", "High") else "Amber")
            ev = QLabel(f"-{leak['ev_lost']}bb")
            ev.setObjectName("Red")
            fix = QLabel(leak["fix"])
            fix.setObjectName("Green")
            fix.setWordWrap(True)
            row.addWidget(name, 2)
            row.addWidget(severity)
            row.addWidget(ev)
            row.addWidget(fix, 3)
            leak_layout.addLayout(row)
        layout.addWidget(leak_frame)

        # Recommendations
        rec = QFrame()
        rec.setObjectName("Card")
        rec_layout = QVBoxLayout(rec)
        rec_title = QLabel("Next Week Focus")
        rec_title.setObjectName("SectionTitle")
        rec_layout.addWidget(rec_title)
        recommendations = [
            "1. River bluff discipline: reduce overbluff frequency by 15%",
            "2. BB defend expansion: add suited gappers and wheel aces",
            "3. ICM call-off tightening: respect pay jump premium",
            "4. Turn paired board: check more, barrel less",
            "5. Thin value practice: half-pot river bets vs capped ranges",
        ]
        for r in recommendations:
            label = QLabel(r)
            label.setObjectName("Cyan")
            rec_layout.addWidget(label)
        layout.addWidget(rec)

    def _compute_position_breakdown(self) -> list[dict]:
        try:
            imported = get_imported_hands(500)
        except Exception:
            imported = []
        try:
            played = get_session_history(500)
        except Exception:
            played = []
        return compute_position_breakdown_from_rows(imported, played)


class _PercentBar(QWidget):
    """Simple horizontal bar showing a percentage."""

    def __init__(self, value: int):
        super().__init__()
        self.value = min(100, max(0, value))
        self.setMinimumHeight(20)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        # Background
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(0, 2, w, h - 4, 4, 4)

        # Filled portion
        fill_w = int(w * self.value / 100)
        if self.value >= 80:
            color = QColor("#10B981")
        elif self.value >= 60:
            color = QColor("#22D3EE")
        else:
            color = QColor("#F59E0B")
        painter.setBrush(color)
        painter.drawRoundedRect(0, 2, fill_w, h - 4, 4, 4)
        painter.end()
