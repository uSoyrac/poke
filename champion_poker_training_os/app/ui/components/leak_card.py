from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class LeakCard(QFrame):
    def __init__(self, leak: dict):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel(leak["name"])
        title.setObjectName("SectionTitle")
        severity = QLabel(f"{leak['severity']} | EV lost {leak['ev_lost']}bb | Dev {leak['frequency_deviation']}")
        severity.setObjectName("Red" if leak["severity"] in {"Critical", "High"} else "Amber")
        why = QLabel(leak["why"])
        why.setWordWrap(True)
        why.setObjectName("Muted")
        fix = QLabel(leak["fix"])
        fix.setWordWrap(True)
        fix.setObjectName("Green")
        button = QPushButton("Create Drill Pack")
        button.setObjectName("PrimaryButton")
        layout.addWidget(title)
        layout.addWidget(severity)
        layout.addWidget(why)
        layout.addWidget(fix)
        layout.addWidget(button)

