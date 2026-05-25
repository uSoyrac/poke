from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class CoachPanel(QFrame):
    ask_requested = Signal()
    chat_requested = Signal(str)

    EXPANDED_WIDTH = 360
    COLLAPSED_WIDTH = 40

    def __init__(self):
        super().__init__()
        self.setObjectName("CoachPanel")
        self._collapsed = False

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(
            "AI Coach hazır.\n\nBir spot çözün, hand analiz edin veya Math Lab sorusu cevaplayın; burada Türkçe koç açıklaması görünecek.\n\nAşağıdan da soru sorabilirsin."
        )

        self.ask_button = QPushButton("Spot Analizi (Ask Coach Why)")
        self.ask_button.setObjectName("PrimaryButton")
        self.ask_button.setToolTip("Seçili spot'u Gemini ile analiz et")
        self.ask_button.clicked.connect(self.ask_requested.emit)

        # Chat input row
        self._input = QLineEdit()
        self._input.setPlaceholderText("Soru sor…  (Enter ile gönder)")
        self._input.setObjectName("CoachInput")
        self._input.returnPressed.connect(self._send_chat)
        self._send_btn = QPushButton("→")
        self._send_btn.setObjectName("PrimaryButton")
        self._send_btn.setFixedWidth(36)
        self._send_btn.setToolTip("Gönder")
        self._send_btn.clicked.connect(self._send_chat)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(0, 0, 0, 0)
        input_row.setSpacing(6)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setObjectName("PaneToggle")
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
        layout.addLayout(input_row)
        layout.addWidget(self.ask_button)

    def _send_chat(self) -> None:
        prompt = self._input.text().strip()
        if not prompt:
            return
        self._input.clear()
        self.chat_requested.emit(prompt)

    def set_message(self, message: str) -> None:
        self.text.setPlainText(message)

    def set_thinking(self) -> None:
        self.text.setPlainText("Düşünüyor…")

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self.text.hide()
            self.ask_button.hide()
            self.title_label.hide()
            self._input.hide()
            self._send_btn.hide()
            self.toggle_btn.setText("◀")
            self.toggle_btn.setToolTip("Expand coach (⌘J)")
        else:
            self.setFixedWidth(self.EXPANDED_WIDTH)
            self.text.show()
            self.ask_button.show()
            self.title_label.show()
            self._input.show()
            self._send_btn.show()
            self.toggle_btn.setText("▶")
            self.toggle_btn.setToolTip("Collapse coach (⌘J)")
