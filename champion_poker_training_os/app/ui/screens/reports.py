from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import dashboard_metrics, leaks


class ReportsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        metrics = dashboard_metrics()
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Reports")
        title.setObjectName("Title")
        export = QPushButton("Export HTML/PDF Report")
        export.clicked.connect(lambda: self.status.setText("Demo report exported preview: HTML/PDF adapter placeholder ready."))
        self.status = QLabel("Weekly report ready.")
        self.status.setObjectName("Green")
        root.addWidget(title)
        root.addWidget(export)
        root.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)
        summary = QLabel(
            f"Weekly Skill Score: {metrics['skill_score']}\n"
            f"Completed drills: 315\nAccuracy: Preflop {metrics['preflop_accuracy']}%, Postflop {metrics['postflop_accuracy']}%, River {metrics['river_score']}%\n"
            f"EV loss trend: 29.4 -> {metrics['ev_loss_per_100']:.1f}bb / 100 decisions\n"
            "Fixed leaks: SB overflat, delayed cbet hesitation\nActive leaks:"
        )
        summary.setWordWrap(True)
        summary.setObjectName("Card")
        summary.setStyleSheet("padding: 12px;")
        layout.addWidget(summary)
        for leak in leaks():
            label = QLabel(f"{leak['name']} | {leak['severity']} | EV lost {leak['ev_lost']}bb | Fix: {leak['fix']}")
            label.setWordWrap(True)
            label.setObjectName("Card")
            label.setStyleSheet("padding: 12px;")
            layout.addWidget(label)
        layout.addStretch(1)
        root.addWidget(scroll, 1)

