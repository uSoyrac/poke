from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app.ai.coach_engine import coach_chat, explain_spot
from app.core.app_state import AppState


class AiCoachScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("AI Poker Coach")
        title.setObjectName("Title")
        layout.addWidget(title)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setPlainText(
            "Türkçe offline koç hazır. Canlı oyun kararı vermez; geçmiş el, manuel spot, leak ve çalışma planı açıklar."
        )
        self.input = QTextEdit()
        self.input.setMaximumHeight(88)
        self.input.setPlaceholderText("Leak, spot, matematik veya plan sorusu yazın...")
        row = QHBoxLayout()
        ask = QPushButton("Ask Coach")
        ask.setObjectName("PrimaryButton")
        ask.clicked.connect(self.ask)
        explain = QPushButton("Explain Selected Spot")
        explain.clicked.connect(self.explain_selected)
        row.addWidget(ask)
        row.addWidget(explain)
        layout.addWidget(self.history, 1)
        layout.addWidget(self.input)
        layout.addLayout(row)

    def ask(self) -> None:
        prompt = self.input.toPlainText().strip()
        answer = coach_chat(prompt, self.state.selected_spot if "spot" in prompt.lower() else None)
        self.history.append(f"\nUser: {prompt}\nCoach: {answer}")
        self.input.clear()

    def explain_selected(self) -> None:
        if self.state.selected_spot:
            self.history.append("\nCoach: " + explain_spot(self.state.selected_spot))
        else:
            self.history.append("\nCoach: Önce trainer veya analyzer ekranında bir spot seç.")

