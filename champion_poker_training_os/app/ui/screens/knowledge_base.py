from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.rag import search_concepts
from app.core.app_state import AppState
from app.training.concept_routing import APPLICATION_NAV, route_for


class ConceptCard(QFrame):
    """A single concept card with summary + 'Practice this concept' button."""

    practice_clicked = Signal(dict)
    coach_clicked = Signal(dict)

    def __init__(self, card: dict):
        super().__init__()
        self.card = card
        self.setObjectName("Card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header row: concept name + source pill
        header = QHBoxLayout()
        title = QLabel(card["concept"])
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        source_pill = QLabel(card["source"])
        source_pill.setStyleSheet(
            "background: #1B2A3D; color: #22D3EE; font-weight: 700; "
            "padding: 3px 10px; border-radius: 11px;"
        )
        header.addWidget(source_pill)
        layout.addLayout(header)

        # Summary
        summary = QLabel(card["summary"])
        summary.setWordWrap(True)
        summary.setObjectName("Muted")
        layout.addWidget(summary)

        # Application + drill idea
        meta = QLabel(
            f"📚 Linked module: <b>{card.get('application', '—')}</b>  ·  "
            f"💡 {card.get('drill_idea', '—')}"
        )
        meta.setTextFormat(Qt.RichText)
        meta.setStyleSheet("color: #9CA3AF;")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        # Misuse warning
        if card.get("misuse_risk"):
            risk = QLabel(f"⚠ {card['misuse_risk']}")
            risk.setStyleSheet("color: #F59E0B; font-size: 11px;")
            risk.setWordWrap(True)
            layout.addWidget(risk)

        # Action buttons row
        actions = QHBoxLayout()
        practice_btn = QPushButton("▶ Practice this concept")
        practice_btn.setObjectName("PrimaryButton")
        practice_btn.setStyleSheet(
            "QPushButton { background: #10B981; color: #04110D; font-weight: 800; "
            "padding: 7px 14px; border-radius: 7px; border: none; }"
            "QPushButton:hover { background: #34D399; }"
        )
        practice_btn.setCursor(Qt.PointingHandCursor)
        practice_btn.clicked.connect(lambda: self.practice_clicked.emit(self.card))

        coach_btn = QPushButton("🤖 Ask AI Coach")
        coach_btn.setCursor(Qt.PointingHandCursor)
        coach_btn.clicked.connect(lambda: self.coach_clicked.emit(self.card))

        actions.addWidget(practice_btn)
        actions.addWidget(coach_btn)
        actions.addStretch(1)
        layout.addLayout(actions)


class KnowledgeBaseScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Knowledge Base")
        title.setObjectName("Title")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search concepts: MDF, Bayes, ICM, blockers...")
        self.search.returnPressed.connect(self.render)
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
        for card_data in search_concepts(self.search.text() or "poker"):
            card = ConceptCard(card_data)
            card.practice_clicked.connect(self._on_practice)
            card.coach_clicked.connect(self._on_coach)
            self.cards_layout.addWidget(card)
        self.cards_layout.addStretch(1)

    # --- handlers --------------------------------------------------------
    def _on_practice(self, card: dict) -> None:
        """Route the user to the trainer linked to this concept's application,
        priming drill_filters when relevant."""
        app = card.get("application") or "Spot Practice Trainer"
        nav_target, filters = route_for(app)
        if filters is not None:
            self.state.drill_filters = {
                **filters,
                "concept": card.get("concept", ""),
                "concept_source": card.get("source", ""),
            }
        else:
            # Still record concept context so AI Coach can mention it
            self.state.drill_filters = {
                "concept": card.get("concept", ""),
                "concept_source": card.get("source", ""),
            }
        self.coach_message.emit(
            f"Practice mode: '{card.get('concept', '?')}' — {nav_target}'a yönlendiriliyorsun. "
            f"({card.get('source', '')})"
        )
        self.navigate_requested.emit(nav_target)

    def _on_coach(self, card: dict) -> None:
        self.coach_message.emit(
            f"Concept '{card.get('concept', '?')}' from {card.get('source', '?')}.\n\n"
            f"{card.get('summary', '')}\n\n"
            f"Application: {card.get('application', '—')}\n"
            f"Drill idea: {card.get('drill_idea', '—')}"
        )
