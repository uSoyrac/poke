from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from app.ui.components.card_view import CardView


class PlayerSeat(QFrame):
    def __init__(self, name: str, stack: str, highlight: bool = False):
        super().__init__()
        self.setObjectName("Elevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        name_label = QLabel(name)
        name_label.setObjectName("Cyan" if highlight else "Muted")
        stack_label = QLabel(stack)
        stack_label.setObjectName("Green" if highlight else "Meta")
        layout.addWidget(name_label)
        layout.addWidget(stack_label)


class PokerTableView(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("PokerTable")
        self.hero_cards = QHBoxLayout()
        self.board_cards = QHBoxLayout()
        self.pot_label = QLabel("Pot 0bb")
        self.pot_label.setObjectName("SectionTitle")
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(PlayerSeat("UTG Bot", "100bb"), 0, 1)
        layout.addWidget(PlayerSeat("CO Bot", "96bb"), 1, 0)
        layout.addWidget(PlayerSeat("BTN Bot", "112bb"), 1, 2)
        layout.addWidget(PlayerSeat("Hero", "100bb", True), 2, 1)
        center = QVBoxLayout()
        center.setAlignment(Qt.AlignCenter)
        center.addWidget(self.pot_label, alignment=Qt.AlignCenter)
        board_holder = QFrame()
        board_holder.setLayout(self.board_cards)
        center.addWidget(board_holder, alignment=Qt.AlignCenter)
        hero_holder = QFrame()
        hero_holder.setLayout(self.hero_cards)
        center.addWidget(hero_holder, alignment=Qt.AlignCenter)
        layout.addLayout(center, 1, 1)

    def set_hand(self, hero_cards: str, board: str, pot: float) -> None:
        _clear_layout(self.hero_cards)
        _clear_layout(self.board_cards)
        cards = [hero_cards[i : i + 2] for i in range(0, min(len(hero_cards), 4), 2)]
        for card in cards:
            self.hero_cards.addWidget(CardView(card))
        if board and board != "preflop":
            for card in [board[i : i + 2] for i in range(0, len(board), 2)]:
                self.board_cards.addWidget(CardView(card))
        else:
            self.board_cards.addWidget(QLabel("Preflop"))
        self.pot_label.setText(f"Pot {pot:.1f}bb")


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

