from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit

from app.core.app_state import AppState
from app.core.rta_guard import RtaGuardStatus


class ComplianceStatusBadge(QLabel):
    def __init__(self):
        super().__init__("STRICT ACTIVE")
        self.setObjectName("Green")

    def set_status(self, status: RtaGuardStatus) -> None:
        self.setText(status.label)
        self.setObjectName("Red" if status.locked else "Green")
        self.style().unpolish(self)
        self.style().polish(self)


class TopStatusBar(QFrame):
    def __init__(self, state: AppState):
        super().__init__()
        self.setObjectName("TopBar")
        self.mode_label = QLabel(state.active_mode)
        self.mode_label.setObjectName("SectionTitle")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search spots, leaks, hands...")
        self.compliance = ComplianceStatusBadge()
        self.import_label = QLabel(f"Last import: {state.last_import}")
        self.import_label.setObjectName("Muted")
        self.ai_label = QLabel(f"AI: {state.ai_provider}")
        self.ai_label.setObjectName("Cyan")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.search, 1)
        layout.addWidget(self.compliance)
        layout.addWidget(self.import_label)
        layout.addWidget(self.ai_label)

    def set_mode(self, mode: str) -> None:
        self.mode_label.setText(mode)

