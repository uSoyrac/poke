from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import generate_math_drills


class MathLabScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = generate_math_drills(30)
        self.index = 0
        self.correct = 0
        self.answered = 0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Math Lab")
        title.setObjectName("Title")
        layout.addWidget(title)

        cards = QGridLayout()
        for idx, item in enumerate(["Pot odds", "Alpha", "MDF", "EV", "Fold equity", "Bayes update", "Combos", "Variance"]):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            label = QLabel(item)
            label.setObjectName("SectionTitle")
            detail = QLabel("Quick calculation drill ready")
            detail.setObjectName("Muted")
            card_layout.addWidget(label)
            card_layout.addWidget(detail)
            cards.addWidget(card, idx // 4, idx % 4)
        layout.addLayout(cards)

        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.prompt = QLabel()
        self.prompt.setObjectName("SectionTitle")
        self.prompt.setWordWrap(True)
        self.answer = QDoubleSpinBox()
        self.answer.setDecimals(3)
        self.answer.setRange(-1000, 1000)
        self.answer.setSingleStep(0.01)
        self.feedback = QLabel("Enter your answer. Percent answers use decimals: 0.33 = 33%.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Muted")
        row = QHBoxLayout()
        submit = QPushButton("Check Answer")
        submit.setObjectName("PrimaryButton")
        submit.clicked.connect(self.check)
        similar = QPushButton("Similar 5 Questions")
        similar.clicked.connect(lambda: self.coach_message.emit("Benzer 5 matematik sorusu sıraya alındı: aynı formül, farklı pot/risk değerleri."))
        row.addWidget(self.answer)
        row.addWidget(submit)
        row.addWidget(similar)
        panel_layout.addWidget(self.prompt)
        panel_layout.addLayout(row)
        panel_layout.addWidget(self.feedback)
        layout.addWidget(panel)
        self.load()

    def load(self) -> None:
        drill = self.drills[self.index % len(self.drills)]
        self.prompt.setText(f"{drill['id']} | {drill['kind'].title()}: {drill['prompt']}")
        self.answer.setValue(0)

    def check(self) -> None:
        drill = self.drills[self.index % len(self.drills)]
        value = self.answer.value()
        ok = abs(value - drill["answer"]) <= drill["tolerance"]
        self.answered += 1
        self.correct += int(ok)
        reflex = int(100 * self.correct / self.answered)
        self.feedback.setObjectName("Green" if ok else "Red")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(
            f"{'Correct' if ok else 'Review'} | Answer {drill['answer']} | "
            f"Math Reflex Score {reflex}. {drill['explanation']}"
        )
        self.coach_message.emit(
            f"Math Coach: {drill['kind']} sorusunda cevap {drill['answer']}. "
            f"{drill['explanation']} Bunu masada karar vermek için değil, offline refleks geliştirmek için çalışıyoruz."
        )
        self.index += 1
        self.load()

