from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_hands
from app.ui.components.hand_timeline import HandTimeline
from app.ui.components.poker_table import PokerTableView


class HandAnalyzerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.hands = generate_hands(100)
        self.selected = self.hands[0]

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

        header = QHBoxLayout()
        title = QLabel("Hand History Analyzer")
        title.setObjectName("Title")
        header.addWidget(title)
        self.filter = QComboBox()
        self.filter.addItems(["All", "cash", "MTT", "SNG", "PKO", "heads-up"])
        self.filter.currentTextChanged.connect(self.populate_table)
        import_button = QPushButton("Import Demo Session")
        import_button.clicked.connect(lambda: self.coach_message.emit("Demo session imported: 100 hands normalized, 312 decisions analyzed."))
        header.addWidget(self.filter)
        header.addWidget(import_button)
        layout.addLayout(header)

        top = QHBoxLayout()
        self.table_view = PokerTableView()
        top.addWidget(self.table_view, 2)
        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("SectionTitle")
        button_row = QHBoxLayout()
        for label, target in [
            ("Study this spot", "GTO Study Library"),
            ("Practice this spot", "Spot Practice Trainer"),
            ("Ask AI Coach", "AI Poker Coach"),
            ("Add to leak report", "Leak Finder"),
        ]:
            button = QPushButton(label)
            if label == "Ask AI Coach":
                button.clicked.connect(lambda checked=False: self.coach_message.emit(explain_spot(self.selected["spot"])))
            else:
                button.clicked.connect(lambda checked=False, t=target: self.navigate_requested.emit(t))
            button_row.addWidget(button)
        panel_layout.addWidget(self.summary)
        panel_layout.addLayout(button_row)
        self.timeline = HandTimeline([])
        panel_layout.addWidget(self.timeline)
        top.addWidget(panel, 2)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Hand", "Format", "Position", "Cards", "Board", "EV loss", "Mistake"])
        self.table.cellClicked.connect(self.select_row)
        layout.addWidget(self.table)
        self.populate_table()
        self.show_hand(self.selected)

    def populate_table(self) -> None:
        current = self.filter.currentText() if hasattr(self, "filter") else "All"
        rows = [h for h in self.hands if current == "All" or h["format"] == current]
        self.table.setRowCount(len(rows))
        self.table.setProperty("rows", rows)
        for row, hand in enumerate(rows):
            for col, key in enumerate(["id", "format", "position", "hero_cards", "board", "ev_loss", "biggest_mistake"]):
                self.table.setItem(row, col, QTableWidgetItem(str(hand[key])))

    def select_row(self, row: int, _col: int) -> None:
        rows = self.table.property("rows") or self.hands
        self.show_hand(rows[row])

    def show_hand(self, hand: dict) -> None:
        self.selected = hand
        self.state.selected_spot = hand["spot"]
        self.table_view.set_hand(hand["hero_cards"], hand["board"], hand["spot"]["pot_bb"])
        self.timeline.set_events(hand["timeline"])
        self.summary.setText(
            f"{hand['id']} vs {hand['villain']} | Result {hand['result_bb']:+.1f}bb | "
            f"EV loss {hand['ev_loss']:.2f}bb | Biggest mistake: {hand['biggest_mistake']}"
        )

