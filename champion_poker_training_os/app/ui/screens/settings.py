from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.core.compliance import OFFLINE_COMPLIANCE_RULES
from app.core.rta_guard import RtaGuard


class SettingsScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.guard = RtaGuard(strict_mode=state.strict_rta_guard)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Settings / Compliance Guard")
        title.setObjectName("Title")
        self.strict = QCheckBox("RTA Guard Strict Mode")
        self.strict.setChecked(state.strict_rta_guard)
        self.strict.stateChanged.connect(self.update_strict)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("Green")
        scan = QPushButton("Scan Poker Clients")
        scan.setObjectName("PrimaryButton")
        scan.clicked.connect(self.scan)
        layout.addWidget(title)
        layout.addWidget(self.strict)
        layout.addWidget(scan)
        layout.addWidget(self.status)
        rules = QLabel("\n".join(f"- {rule}" for rule in OFFLINE_COMPLIANCE_RULES))
        rules.setObjectName("Muted")
        layout.addWidget(rules)
        layout.addStretch(1)
        self.scan()

    def update_strict(self) -> None:
        self.state.strict_rta_guard = self.strict.isChecked()
        self.guard.strict_mode = self.state.strict_rta_guard
        self.scan()

    def scan(self) -> None:
        status = self.guard.scan_processes()
        self.state.strategy_locked = status.locked
        self.status.setObjectName("Red" if status.locked else "Green")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(status.message)

