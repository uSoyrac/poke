from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QTextEdit, QVBoxLayout


class CoachPanel(QFrame):
    ask_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("CoachPanel")
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
        title = QLabel("AI Coach / Study Notes")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.ask_button)

    def set_message(self, message: str) -> None:
        self.text.setPlainText(message)

