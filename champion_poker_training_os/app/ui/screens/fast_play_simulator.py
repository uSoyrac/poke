from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.simulator.bot_profiles import all_bot_profiles
from app.simulator.fast_play_engine import FastPlayEngine
from app.ui.components.poker_table import PokerTableView


class FastPlaySimulatorScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.engine = FastPlayEngine()
        self.action_layout = QHBoxLayout()

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
        title = QLabel("Fast Play Simulator")
        title.setObjectName("Title")
        header.addWidget(title)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Cash 6-max", "Cash 9-max", "Heads-up", "SNG", "MTT", "Spin-style jackpot", "Short-stack practice"])
        self.mode_combo.currentTextChanged.connect(self._set_mode)
        self.bot_combo = QComboBox()
        self.bot_combo.addItems([bot["name"] for bot in all_bot_profiles()])
        self.bot_combo.setCurrentText(self.engine.bot_name)
        self.bot_combo.currentTextChanged.connect(self._set_bot)
        header.addWidget(QLabel("Mode"))
        header.addWidget(self.mode_combo)
        header.addWidget(QLabel("Bot"))
        header.addWidget(self.bot_combo)
        layout.addLayout(header)

        top = QHBoxLayout()
        self.table = PokerTableView()
        top.addWidget(self.table, 2)
        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.hand_title = QLabel()
        self.hand_title.setObjectName("SectionTitle")
        self.stats = QLabel()
        self.stats.setObjectName("Cyan")
        self.bot_info = QLabel()
        self.bot_info.setWordWrap(True)
        self.bot_info.setObjectName("Muted")
        panel_layout.addWidget(self.hand_title)
        panel_layout.addWidget(self.stats)
        panel_layout.addWidget(self.bot_info)
        panel_layout.addLayout(self.action_layout)
        retry = QPushButton("Retry Hand")
        retry.clicked.connect(self.retry)
        panel_layout.addWidget(retry)
        top.addWidget(panel, 1)
        layout.addLayout(top)

        self.feedback = QLabel("Pick an action. Fast mode estimates 100-500 hands/hour with rule-based bots.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Green")
        layout.addWidget(self.feedback)
        self.load_hand()

    def _set_mode(self, mode: str) -> None:
        self.engine.mode = mode
        self.load_hand()

    def _set_bot(self, bot: str) -> None:
        self.engine.bot_name = bot
        self.load_hand()

    def load_hand(self) -> None:
        hand = self.engine.current_hand
        self.state.selected_spot = hand
        self.table.set_hand(hand["hero_cards"], hand["board"], hand["pot_bb"])
        self.hand_title.setText(f"{hand['id']} | {self.engine.mode} | {hand['title']}")
        bot = self.engine.bot
        self.stats.setText(
            f"Hands {self.engine.hands_played} | Skill {self.engine.skill_score} | "
            f"Session EV loss {self.engine.ev_loss:.2f}bb"
        )
        self.bot_info.setText(
            f"{bot['name']} VPIP {bot['vpip']} / PFR {bot['pfr']} / 3bet {bot['three_bet']} | "
            f"Fold cbet {bot['fold_to_cbet']} | River bluff {bot['river_bluff']} | {bot['adjustment']}"
        )
        _clear_layout(self.action_layout)
        for action in hand["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self.play(a))
            self.action_layout.addWidget(button)

    def play(self, action: str) -> None:
        hand = self.engine.current_hand
        result = self.engine.play(action)
        self.feedback.setText(
            f"Hero {action}; bot responds {result['bot_response']}. "
            f"Best {result['best_action']}, EV loss {result['ev_loss']:.2f}bb, "
            f"skill score {result['skill_score']}."
        )
        self.coach_message.emit(explain_spot(hand, action))
        self.load_hand()

    def retry(self) -> None:
        self.engine.retry()
        self.feedback.setText("Same hand loaded again. Try a different line.")
        self.load_hand()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

