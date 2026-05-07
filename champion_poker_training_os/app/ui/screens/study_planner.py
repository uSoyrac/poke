from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.db.seed_data import study_plan


class StudyPlannerScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Study Planner")
        title.setObjectName("Title")
        self.plan_type = QComboBox()
        self.plan_type.addItems([
            "90-day world-class training plan",
            "MTT low stakes crusher",
            "River decision repair",
            "Preflop bootcamp",
            "ICM bootcamp",
            "Math bootcamp",
            "Leak repair week",
        ])
        regenerate = QPushButton("Generate Personal Plan")
        regenerate.setObjectName("PrimaryButton")
        regenerate.clicked.connect(self.render)
        self.content = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setLayout(self.content)
        scroll.setWidget(body)
        root.addWidget(title)
        root.addWidget(self.plan_type)
        root.addWidget(regenerate)
        root.addWidget(scroll, 1)
        self.render()

    def render(self) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for day in study_plan():
            label = QLabel(f"{day['day']} | {self.plan_type.currentText()}\nFocus: {day['focus']}\n" + "\n".join(day["blocks"]) + f"\nTarget: {day['target']}")
            label.setWordWrap(True)
            label.setObjectName("Card")
            label.setStyleSheet("padding: 12px;")
            self.content.addWidget(label)
        self.content.addStretch(1)

