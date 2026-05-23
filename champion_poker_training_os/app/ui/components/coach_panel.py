from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout


class CoachPanel(QFrame):
    ask_requested = Signal()

    EXPANDED_WIDTH = 360
    COLLAPSED_WIDTH = 40

    def __init__(self):
        super().__init__()
        self.setObjectName("CoachPanel")
        self._collapsed = False

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(
            "AI Coach hazır.\n\nBir spot çözün, hand analiz edin veya Math Lab sorusu cevaplayın; burada Türkçe koç açıklaması görünecek."
        )
        self.ask_button = QPushButton("Ask Coach Why")
        self.ask_button.setObjectName("PrimaryButton")
        self.ask_button.clicked.connect(self.ask_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        # Title row with collapse toggle on the left so collapsed state
        # keeps the toggle visible at the panel's edge.
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setObjectName("PaneToggle")  # styled per design (accent on hover)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setToolTip("Collapse coach (⌘J)")
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        title_row.addWidget(self.toggle_btn, 0, Qt.AlignTop)
        self.title_label = QLabel("AI Coach / Study Notes")
        self.title_label.setObjectName("SectionTitle")
        title_row.addWidget(self.title_label, 1)
        layout.addLayout(title_row)

        layout.addWidget(self.text, 1)
        layout.addWidget(self.ask_button)

    def set_message(self, message: str) -> None:
        self.text.setPlainText(message)

    def toggle_collapsed(self) -> None:
        """Toggle between full panel and a narrow rail.

        Collapsed → 40px rail with just the toggle, so the play area
        reclaims ~320px of width. Click ◀ (or ⌘J) to expand again.
        """
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self.text.hide()
            self.ask_button.hide()
            self.title_label.hide()
            self.toggle_btn.setText("◀")
            self.toggle_btn.setToolTip("Expand coach (⌘J)")
        else:
            self.setFixedWidth(self.EXPANDED_WIDTH)
            self.text.show()
            self.ask_button.show()
            self.title_label.show()
            self.toggle_btn.setText("▶")
            self.toggle_btn.setToolTip("Collapse coach (⌘J)")

