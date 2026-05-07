from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)

from app.core.app_state import AppState
from app.ai.coach_engine import analyze_played_hand, session_summary
from app.db.repository import save_played_hand
from app.engine.game_loop import PokerGame, HandResult
from app.engine.hand_state import ActionType, Street
from app.engine.bot_brain import BOT_ARCHETYPES
from app.ui.components.card_view import CardView
from app.ui.components.metric_card import MetricCard


class PlaySessionScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.game: PokerGame | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root.addWidget(scroll)
        self.layout_main = QVBoxLayout(body)
        self.layout_main.setContentsMargins(18, 18, 18, 18)
        self.layout_main.setSpacing(12)

        # === SETUP PANEL ===
        self.setup_frame = QFrame()
        self.setup_frame.setObjectName("Card")
        setup = QVBoxLayout(self.setup_frame)
        setup.setContentsMargins(14, 12, 14, 12)
        setup.addWidget(_title("🎮 Play Session — Texas Hold'em Simulator"))

        controls = QGridLayout()
        self.players_combo = QComboBox()
        self.players_combo.addItems(["2 (Heads-Up)", "6 (6-max)", "9 (Full Ring)"])
        self.players_combo.setCurrentIndex(1)
        self.bot_combo = QComboBox()
        self.bot_combo.addItems(list(BOT_ARCHETYPES.keys()))
        self.bot_combo.setCurrentIndex(list(BOT_ARCHETYPES.keys()).index("Balanced Reg"))
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["20bb", "50bb", "100bb", "200bb"])
        self.stack_combo.setCurrentIndex(2)

        for col, (lbl, w) in enumerate([("Players", self.players_combo), ("Bot Type", self.bot_combo), ("Stack", self.stack_combo)]):
            controls.addWidget(QLabel(lbl), 0, col)
            controls.addWidget(w, 1, col)

        start_btn = QPushButton("▶ Start Session")
        start_btn.setObjectName("PrimaryButton")
        start_btn.clicked.connect(self._start_session)
        controls.addWidget(start_btn, 1, 3)
        setup.addLayout(controls)
        self.layout_main.addWidget(self.setup_frame)

        # === GAME AREA (hidden until session starts) ===
        self.game_frame = QFrame()
        self.game_frame.setObjectName("DataPanel")
        self.game_frame.hide()
        game_layout = QVBoxLayout(self.game_frame)
        game_layout.setSpacing(10)

        # Stats bar
        self.stats_row = QGridLayout()
        self.stat_hands = MetricCard("Hands", "0", "played")
        self.stat_profit = MetricCard("Profit", "0bb", "session", "Green")
        self.stat_vpip = MetricCard("VPIP", "—", "voluntary")
        self.stat_winrate = MetricCard("Win Rate", "—", "showdown", "Cyan")
        for i, w in enumerate([self.stat_hands, self.stat_profit, self.stat_vpip, self.stat_winrate]):
            self.stats_row.addWidget(w, 0, i)
        game_layout.addLayout(self.stats_row)

        # Community cards
        self.community_frame = QFrame()
        self.community_frame.setObjectName("Elevated")
        comm_layout = QVBoxLayout(self.community_frame)
        self.street_label = QLabel("Preflop")
        self.street_label.setObjectName("SectionTitle")
        self.street_label.setAlignment(Qt.AlignCenter)
        self.community_row = QHBoxLayout()
        self.community_row.setAlignment(Qt.AlignCenter)
        self.pot_label = QLabel("Pot: 0")
        self.pot_label.setObjectName("Cyan")
        self.pot_label.setAlignment(Qt.AlignCenter)
        comm_layout.addWidget(self.street_label)
        comm_layout.addLayout(self.community_row)
        comm_layout.addWidget(self.pot_label)
        game_layout.addWidget(self.community_frame)

        # Players display
        self.players_row = QHBoxLayout()
        game_layout.addLayout(self.players_row)

        # Hero cards + actions
        hero_frame = QFrame()
        hero_frame.setObjectName("Card")
        hero_layout = QVBoxLayout(hero_frame)
        hero_top = QHBoxLayout()
        self.hero_cards_row = QHBoxLayout()
        hero_top.addLayout(self.hero_cards_row)
        hero_top.addStretch(1)
        self.hero_stack_label = QLabel("Stack: 100bb")
        self.hero_stack_label.setObjectName("Green")
        hero_top.addWidget(self.hero_stack_label)
        hero_layout.addLayout(hero_top)

        # Action buttons
        self.action_frame = QHBoxLayout()
        self.fold_btn = QPushButton("Fold")
        self.fold_btn.clicked.connect(lambda: self._hero_action(ActionType.FOLD))
        self.check_btn = QPushButton("Check")
        self.check_btn.clicked.connect(lambda: self._hero_action(ActionType.CHECK))
        self.call_btn = QPushButton("Call")
        self.call_btn.setObjectName("PrimaryButton")
        self.call_btn.clicked.connect(lambda: self._hero_action(ActionType.CALL))
        self.bet_btn = QPushButton("Bet")
        self.bet_btn.setObjectName("PrimaryButton")
        self.bet_btn.clicked.connect(lambda: self._hero_action(ActionType.BET))
        self.raise_btn = QPushButton("Raise")
        self.raise_btn.setObjectName("PrimaryButton")
        self.raise_btn.clicked.connect(lambda: self._hero_action(ActionType.RAISE))
        self.allin_btn = QPushButton("ALL-IN")
        self.allin_btn.setObjectName("DangerButton")
        self.allin_btn.clicked.connect(lambda: self._hero_action(ActionType.ALL_IN))

        for b in [self.fold_btn, self.check_btn, self.call_btn, self.bet_btn, self.raise_btn, self.allin_btn]:
            self.action_frame.addWidget(b)

        # Sizing slider
        sizing_row = QHBoxLayout()
        self.sizing_slider = QSlider(Qt.Horizontal)
        self.sizing_slider.setRange(1, 200)
        self.sizing_slider.setValue(50)
        self.sizing_slider.valueChanged.connect(self._update_sizing_label)
        self.sizing_label = QLabel("50% pot")
        sizing_row.addWidget(QLabel("Sizing:"))
        sizing_row.addWidget(self.sizing_slider, 1)
        self.sizing_label_display = QLabel("50% pot")
        sizing_row.addWidget(self.sizing_label_display)
        # Preset buttons
        for pct, label in [(33, "⅓"), (50, "½"), (66, "⅔"), (75, "¾"), (100, "Pot")]:
            btn = QPushButton(label)
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda c=False, p=pct: self.sizing_slider.setValue(p))
            sizing_row.addWidget(btn)

        hero_layout.addLayout(self.action_frame)
        hero_layout.addLayout(sizing_row)
        game_layout.addWidget(hero_frame)

        # Feedback / hand history
        self.feedback_label = QLabel("Session not started.")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setObjectName("Muted")
        game_layout.addWidget(self.feedback_label)

        # Hand log
        self.history_frame = QFrame()
        self.history_frame.setObjectName("Elevated")
        self.history_layout = QVBoxLayout(self.history_frame)
        self.history_layout.addWidget(_title("📜 Hand History"))
        game_layout.addWidget(self.history_frame)

        # Bottom buttons
        bottom_btns = QHBoxLayout()
        self.next_btn = QPushButton("Deal Next Hand →")
        self.next_btn.setObjectName("PrimaryButton")
        self.next_btn.clicked.connect(self._deal_next)
        self.next_btn.hide()
        self.review_btn = QPushButton("🔍 Review Last Hand")
        self.review_btn.clicked.connect(self._review_last)
        self.review_btn.hide()
        self.end_btn = QPushButton("📊 End Session")
        self.end_btn.clicked.connect(self._end_session)
        self.end_btn.hide()
        bottom_btns.addWidget(self.next_btn)
        bottom_btns.addWidget(self.review_btn)
        bottom_btns.addWidget(self.end_btn)
        game_layout.addLayout(bottom_btns)

        self.layout_main.addWidget(self.game_frame)

    def _start_session(self) -> None:
        players_map = {0: 2, 1: 6, 2: 9}
        stack_map = {0: 20, 1: 50, 2: 100, 3: 200}
        num = players_map.get(self.players_combo.currentIndex(), 6)
        stack = stack_map.get(self.stack_combo.currentIndex(), 100)
        bot_name = self.bot_combo.currentText()

        self.game = PokerGame(
            num_players=num, starting_stack=float(stack),
            small_blind=0.5, big_blind=1.0,
            hero_seat=0, bot_archetype=bot_name,
        )
        self.setup_frame.hide()
        self.game_frame.show()
        self.feedback_label.setText("Session started! Dealing first hand...")
        self.coach_message.emit(f"Yeni session: {num}-max, {stack}bb, bot: {bot_name}. İyi eller!")
        self._deal_next()

    def _deal_next(self) -> None:
        if not self.game:
            return
        self.next_btn.hide()
        self.game.start_hand()
        self._refresh_ui()

    def _hero_action(self, action_type: ActionType) -> None:
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        hero = hand.hero
        pot = max(hand.pot, 1)

        # Calculate amount
        amount = 0.0
        if action_type in (ActionType.BET, ActionType.RAISE):
            pct = self.sizing_slider.value() / 100.0
            amount = round(pot * pct, 1)
            amount = max(hand.big_blind, min(amount, hero.stack))
        elif action_type == ActionType.CALL:
            amount = min(hand.current_bet - hero.current_bet, hero.stack)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack

        self.game.hero_act(action_type, amount)
        self._refresh_ui()

        # Coach feedback after hero action
        if hand.is_complete:
            self._on_hand_complete()

    def _refresh_ui(self) -> None:
        if not self.game or not self.game.current_hand:
            return
        hand = self.game.current_hand
        hero = hand.hero

        # Street + pot
        self.street_label.setText(f"🃏 {hand.street_name}")
        self.pot_label.setText(f"Pot: {hand.pot:.1f}bb")

        # Community cards
        _clear(self.community_row)
        if hand.community:
            for c in hand.community:
                self.community_row.addWidget(CardView(c.display))
        else:
            for _ in range(5):
                placeholder = QLabel("🂠")
                placeholder.setFixedSize(46, 62)
                placeholder.setAlignment(Qt.AlignCenter)
                placeholder.setStyleSheet("font-size: 28px; color: #4B5563;")
                self.community_row.addWidget(placeholder)

        # Hero cards
        _clear(self.hero_cards_row)
        if hero and hero.hole_cards:
            for c in hero.hole_cards:
                self.hero_cards_row.addWidget(CardView(c.display))
            self.hero_stack_label.setText(f"Stack: {hero.stack:.1f}bb | Invested: {hero.invested_this_hand:.1f}bb")

        # Players display
        _clear(self.players_row)
        for i, p in enumerate(hand.players):
            if p.is_hero:
                continue
            pf = QFrame()
            pf.setObjectName("Elevated")
            pl = QVBoxLayout(pf)
            pl.setContentsMargins(6, 4, 6, 4)
            name = QLabel(f"{p.position} {p.name}")
            name.setObjectName("Muted" if p.is_folded else "Cyan")
            stack_l = QLabel(f"{p.stack:.1f}bb")
            status = "folded" if p.is_folded else ("all-in" if p.is_all_in else f"bet {p.current_bet:.1f}")
            status_l = QLabel(status)
            status_l.setObjectName("Red" if p.is_folded else "Green")
            pl.addWidget(name)
            pl.addWidget(stack_l)
            pl.addWidget(status_l)
            # Show cards at showdown
            if hand.is_complete and not p.is_folded and p.hole_cards:
                cards_l = QLabel(" ".join(c.display for c in p.hole_cards))
                cards_l.setObjectName("Amber")
                pl.addWidget(cards_l)
            self.players_row.addWidget(pf)

        # Action buttons
        self._update_action_buttons()

        # Stats
        stats = self.game.get_session_stats()
        _update_card(self.stat_hands, str(stats["hands"]), "played")
        profit_str = f"{stats['profit_bb']:+.1f}bb"
        _update_card(self.stat_profit, profit_str, f"{stats['bb_per_100']:+.1f}bb/100")
        _update_card(self.stat_vpip, f"{stats['vpip']:.0f}%", "voluntary")
        _update_card(self.stat_winrate, f"{stats['win_rate']:.0f}%", "showdown")

        if hand.is_complete:
            self._on_hand_complete()

    def _update_action_buttons(self) -> None:
        hand = self.game.current_hand if self.game else None
        waiting = self.game.is_waiting_for_hero if self.game else False

        all_btns = [self.fold_btn, self.check_btn, self.call_btn, self.bet_btn, self.raise_btn, self.allin_btn]
        for b in all_btns:
            b.setEnabled(False)
            b.hide()

        if not waiting or not hand:
            return

        valid = hand.get_valid_actions(hand.hero_idx)
        valid_types = {v[0] for v in valid}
        to_call = hand.current_bet - hand.hero.current_bet if hand.hero else 0

        if ActionType.FOLD in valid_types:
            self.fold_btn.show()
            self.fold_btn.setEnabled(True)
        if ActionType.CHECK in valid_types:
            self.check_btn.show()
            self.check_btn.setEnabled(True)
        if ActionType.CALL in valid_types:
            self.call_btn.setText(f"Call {to_call:.1f}")
            self.call_btn.show()
            self.call_btn.setEnabled(True)
        if ActionType.BET in valid_types:
            self.bet_btn.show()
            self.bet_btn.setEnabled(True)
        if ActionType.RAISE in valid_types:
            self.raise_btn.show()
            self.raise_btn.setEnabled(True)
        self.allin_btn.show()
        self.allin_btn.setEnabled(True)
        self.allin_btn.setText(f"ALL-IN ({hand.hero.stack:.1f})")

    def _on_hand_complete(self) -> None:
        if not self.game or not self.game.hand_history:
            return
        result = self.game.hand_history[-1]

        color = "Green" if result.hero_won else "Red"
        self.feedback_label.setObjectName(color)
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

        winner_names = ", ".join(self.game.players[w].name for w in result.winners)
        self.feedback_label.setText(
            f"Hand #{result.hand_id} complete | "
            f"{'✓ YOU WON' if result.hero_won else '✗ Lost'} | "
            f"Profit: {result.hero_profit:+.1f}bb | Pot: {result.pot:.1f}bb | "
            f"Winner: {winner_names} ({result.winner_hand_name}) | "
            f"Hero cards: {result.hero_cards} | Board: {result.community}"
        )

        # Add to history
        entry = QLabel(
            f"#{result.hand_id} | {result.hero_cards} | {result.community} | "
            f"{'W' if result.hero_won else 'L'} {result.hero_profit:+.1f}bb | {result.winner_hand_name}"
        )
        entry.setObjectName("Green" if result.hero_won else "Muted")
        self.history_layout.addWidget(entry)

        # Persist to DB
        try:
            save_played_hand({
                "hand_id": result.hand_id,
                "hero_cards": result.hero_cards,
                "community": result.community,
                "pot": result.pot,
                "hero_invested": result.hero_invested,
                "hero_profit": result.hero_profit,
                "hero_won": result.hero_won,
                "winner_hand_name": result.winner_hand_name,
                "streets_seen": result.streets_seen,
            })
        except Exception:
            pass  # Don't crash UI on DB errors

        # Coach message
        self.coach_message.emit(
            f"El #{result.hand_id}: Hero {result.hero_cards}, Board {result.community}. "
            f"{'Kazandın' if result.hero_won else 'Kaybettin'} ({result.hero_profit:+.1f}bb). "
            f"Kazanan: {result.winner_hand_name}. "
            f"Session: {self.game.get_session_stats()['profit_bb']:+.1f}bb toplam."
        )

        self.next_btn.show()
        self.review_btn.show()
        self.end_btn.show()

    def _review_last(self) -> None:
        """Send detailed hand analysis to AI coach."""
        if not self.game or not self.game.hand_history:
            return
        result = self.game.hand_history[-1]
        review = analyze_played_hand({
            "hero_cards": result.hero_cards,
            "community": result.community,
            "hero_profit": result.hero_profit,
            "hero_won": result.hero_won,
            "hero_invested": result.hero_invested,
            "pot": result.pot,
            "winner_hand_name": result.winner_hand_name,
        })
        self.coach_message.emit(review)

    def _end_session(self) -> None:
        """Show session summary via AI coach."""
        if not self.game:
            return
        stats = self.game.get_session_stats()
        hands_data = [
            {"hero_profit": h.hero_profit, "hero_won": h.hero_won, "streets_seen": h.streets_seen}
            for h in self.game.hand_history
        ]
        summary = session_summary(stats, hands_data)
        self.coach_message.emit(summary)

    def _update_sizing_label(self, value: int) -> None:
        self.sizing_label_display.setText(f"{value}% pot")


def _title(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("Title")
    return l


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _update_card(card: MetricCard, value: str, detail: str) -> None:
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
        elif child.objectName() in ("Cyan", "Green", "Amber", "Red"):
            child.setText(detail)
