from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class DrillCard(QFrame):
    start_requested = Signal(dict)

    def __init__(self, drill: dict):
        super().__init__()
        self.drill = drill
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel(drill.get("title") or drill.get("name", "Drill"))
        title.setObjectName("SectionTitle")
        meta = QLabel(
            f"{drill.get('format', drill.get('difficulty', 'demo'))} | "
            f"{drill.get('position', drill.get('spots', ''))} | "
            f"{drill.get('stack_bb', drill.get('skill_score', ''))}"
        )
        meta.setObjectName("Muted")
        button = QPushButton("Start")
        button.clicked.connect(lambda: self.start_requested.emit(self.drill))
        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(button)

