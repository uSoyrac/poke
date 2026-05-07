from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class HandTimeline(QFrame):
    def __init__(self, events: list[str] | None = None):
        super().__init__()
        self.setObjectName("Card")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel("Hand Timeline")
        title.setObjectName("SectionTitle")
        self.layout.addWidget(title)
        self.set_events(events or [])

    def set_events(self, events: list[str]) -> None:
        while self.layout.count() > 1:
            item = self.layout.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for event in events:
            label = QLabel(f"- {event}")
            label.setWordWrap(True)
            label.setObjectName("Muted")
            self.layout.addWidget(label)

