from __future__ import annotations

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.ai.rag import search_concepts
from app.core.app_state import AppState


class KnowledgeBaseScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.cards_layout = QVBoxLayout()
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Knowledge Base")
        title.setObjectName("Title")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search concepts: MDF, Bayes, ICM, blockers...")
        button = QPushButton("Search Concept Cards")
        button.setObjectName("PrimaryButton")
        button.clicked.connect(self.render)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setLayout(self.cards_layout)
        scroll.setWidget(body)
        root.addWidget(title)
        root.addWidget(self.search)
        root.addWidget(button)
        root.addWidget(scroll, 1)
        self.render()

    def render(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for card in search_concepts(self.search.text() or "poker"):
            label = QLabel(
                f"{card['concept']} | {card['source']} | {card['reference']}\n"
                f"{card['summary']}\nApplication: {card['application']} | Drill: {card['drill_idea']}\n"
                f"Misuse risk: {card['misuse_risk']}"
            )
            label.setWordWrap(True)
            label.setObjectName("Card")
            label.setStyleSheet("padding: 12px;")
            self.cards_layout.addWidget(label)
        self.cards_layout.addStretch(1)

