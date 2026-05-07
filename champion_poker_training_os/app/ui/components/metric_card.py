from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, detail: str = "", accent: str = "Cyan"):
        super().__init__()
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("Muted")
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        detail_label = QLabel(detail)
        detail_label.setObjectName(accent)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)

