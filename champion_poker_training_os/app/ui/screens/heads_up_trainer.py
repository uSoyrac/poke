"""HeadsUpTrainerScreen — 1v1 heads-up poker training.

Specialized for heads-up play with:
  - Aggressive preflop ranges
  - Position awareness (BTN vs BB)
  - 3-bet/4-bet dynamics
  - Shallow stack play (20-50bb)
  - Exploitative adjustments
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.app_state import AppState
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from app.engine.bot_brain import BOT_ARCHETYPES
from app.training.decision_review import analyze_hero_decision, format_decision_review, summarize_decision_reviews
from app.ui.components.card_view import CardView
from app.ui.components.live_poker_table import LivePokerTable
from app.ui.components.metric_card import MetricCard


class HeadsUpTrainerScreen(QWidget):
    """1v1 heads-up poker trainer with HU-specific ranges and dynamics."""

    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.game: PokerGame | None = None
        self._current_decision_reviews: list[dict] = []
        self._completed_hand_ids: set[int] = set()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("🎯 Heads-Up Trainer")
        title.setObjectName("Title")
        header.addWidget(title)
        subtitle = QLabel("1v1 aggressive play — BTN vs BB dynamics")
        subtitle.setObjectName("Muted")
        header.addWidget(subtitle, 1)
        layout.addLayout(header)

        # Setup panel
        self.setup_frame = QFrame()
        self.setup_frame.setObjectName("Card")
        setup = QVBoxLayout(self.setup_frame)
        setup.setContentsMargins(14, 12, 14, 12)

        controls = QGridLayout()
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["15bb HU Short", "20bb HU", "30bb HU", "50bb HU", "100bb HU Deep"])
        self.stack_combo.setCurrentIndex(1)
        self.bot_combo = QComboBox()
        self.bot_combo.addItems(list(BOT_ARCHETYPES.keys()))
        # Pick first available LAG-like archetype, fall back to first item
        _arch_keys = list(BOT_ARCHETYPES.keys())
        _default_arch = next((a for a in ("LAG", "Aggro Fish", "Maniac", "Reg") if a in _arch_keys), _arch_keys[0])
        self.bot_combo.setCurrentIndex(_arch_keys.index(_default_arch))
        self.position_combo = QComboBox()
        self.position_combo.addItems(["Hero on BTN", "Hero on BB"])
        self.position_combo.setCurrentIndex(0)

        for col, (lbl, w) in enumerate([
            ("Starting Stack", self.stack_combo),
            ("Opponent Style", self.bot_combo),
            ("Hero Position", self.position_combo),
        ]):
            controls.addWidget(QLabel(lbl), 0, col)
            controls.addWidget(w, 1, col)

        start_btn = QPushButton("▶ Start HU Session")
        start_btn.setObjectName("PrimaryButton")
        start_btn.clicked.connect(self._start_session)
        controls.addWidget(start_btn, 1, 3)
        setup.addLayout(controls)

        # HU-specific tips
        tips = QLabel(
            "💡 HU Tips: Open ~70% from BTN, defend ~40% from BB. "
            "3-bet aggressively vs min-raise. Shove 20bb+ with strong hands."
        )
        tips.setObjectName("Muted")
        tips.setWordWrap(True)
        setup.addWidget(tips)

        layout.addWidget(self.setup_frame)

        # Game area (hidden until session starts)
        self.game_frame = QFrame()
        self.game_frame.setObjectName("DataPanel")
        self.game_frame.hide()
        game_layout = QVBoxLayout(self.game_frame)
        game_layout.setSpacing(10)

        # Stats bar
        self.stats_row = QGridLayout()
        self.stat_hands = MetricCard("Hands", "0", "played")
        self.stat_profit = MetricCard("Profit", "0bb", "session", "Green")
        self.stat_winrate = MetricCard("Win Rate", "—", "showdown", "Cyan")
        self.stat_aggression = MetricCard("AF", "—", "agg factor", "Amber")
        for i, w in enumerate([self.stat_hands, self.stat_profit, self.stat_winrate, self.stat_aggression]):
            self.stats_row.addWidget(w, 0, i)
        game_layout.addLayout(self.stats_row)

        # Position indicator
        self.position_label = QLabel("Hero: BTN | Villain: BB")
        self.position_label.setObjectName("SectionTitle")
        self.position_label.setAlignment(Qt.AlignCenter)
        game_layout.addWidget(self.position_label)

        # Live poker table
        self.live_table = LivePokerTable()
        game_layout.addWidget(self.live_table, 1)

        # Community/pot status
        self.community_frame = QFrame()
        self.community_frame.setObjectName("Elevated")
        comm_layout = QHBoxLayout(self.community_frame)
        comm_layout.setContentsMargins(14, 8, 14, 8)
        self.street_label = QLabel("Preflop")
        self.street_label.setObjectName("SectionTitle")
        self.community_row = QHBoxLayout()
        self.pot_label = QLabel("Pot: 0")
        self.pot_label.setObjectName("Cyan")
        comm_layout.addWidget(self.street_label)
        comm_layout.addLayout(self.community_row)
        comm_layout.addStretch(1)
        comm_layout.addWidget(self.pot_label)
        game_layout.addWidget(self.community_frame)

        # Hero cards + actions
        hero_frame = QFrame()
        hero_frame.setObjectName("Card")
        hero_layout = QVBoxLayout(hero_frame)
        hero_top = QHBoxLayout()
        self.hero_cards_row = QHBoxLayout()
        hero_top.addLayout(self.hero_cards_row)
        hero_top.addStretch(1)
        self.hero_stack_label = QLabel("Stack: 20bb")
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
        sizing_row.addWidget(QLabel("Sizing:"))
        sizing_row.addWidget(self.sizing_slider, 1)
        self.sizing_label_display = QLabel("50% pot")
        sizing_row.addWidget(self.sizing_label_display)
        # HU preset buttons
        for pct, label in [(25, "¼"), (50, "½"), (75, "¾"), (100, "Pot"), (200, "2x")]:
            btn = QPushButton(label)
            btn.setFixedWidth(40)
            btn.clicked.connect(lambda c=False, p=pct: self.sizing_slider.setValue(p))
            sizing_row.addWidget(btn)

        hero_layout.addLayout(self.action_frame)
        hero_layout.addLayout(sizing_row)
        game_layout.addWidget(hero_frame)

        # Feedback
        self.feedback_label = QLabel("Session not started.")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setObjectName("Muted")
        game_layout.addWidget(self.feedback_label)

        # Hand log
        self.history_frame = QFrame()
        self.history_frame.setObjectName("Elevated")
        self.history_layout = QVBoxLayout(self.history_frame)
        self.history_layout.addWidget(QLabel("📜 HU Hand History"))
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
        self.end_btn = QPushButton("📊 End HU Session")
        self.end_btn.clicked.connect(self._end_session)
        self.end_btn.hide()
        bottom_btns.addWidget(self.next_btn)
        bottom_btns.addWidget(self.review_btn)
        bottom_btns.addWidget(self.end_btn)
        game_layout.addLayout(bottom_btns)

        layout.addWidget(self.game_frame)

    def _start_session(self) -> None:
        stack_map = {0: 15, 1: 20, 2: 30, 3: 50, 4: 100}
        stack = stack_map.get(self.stack_combo.currentIndex(), 20)
        bot_name = self.bot_combo.currentText()
        hero_on_btn = self.position_combo.currentIndex() == 0

        # HU: hero on BTN (seat 0) or BB (seat 1)
        hero_seat = 0 if hero_on_btn else 1

        self.game = PokerGame(
            num_players=2, starting_stack=float(stack),
            small_blind=0.5, big_blind=1.0,
            hero_seat=hero_seat, bot_archetype=bot_name,
        )
        self.setup_frame.hide()
        self.game_frame.show()
        self.feedback_label.setText("HU session started! Dealing first hand...")
        self.coach_message.emit(
            f"HU session: {stack}bb, hero {'BTN' if hero_on_btn else 'BB'}, bot: {bot_name}. "
            f"Aggressive play expected!"
        )
        self._deal_next()

    def _deal_next(self) -> None:
        if not self.game:
            return
        self.next_btn.hide()
        self._current_decision_reviews = []
        self.game.start_hand()
        self._refresh_ui()

    def _hero_action(self, action_type: ActionType) -> None:
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        hero = hand.hero
        pot = max(hand.pot, 1)

        amount = 0.0
        if action_type in (ActionType.BET, ActionType.RAISE):
            pct = self.sizing_slider.value() / 100.0
            amount = round(pot * pct, 1)
            amount = max(hand.big_blind, min(amount, hero.stack))
        elif action_type == ActionType.CALL:
            amount = min(hand.current_bet - hero.current_bet, hero.stack)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack

        review = None
        try:
            review = analyze_hero_decision(hand, action_type, amount)
            self._current_decision_reviews.append(review)
        except Exception:
            review = None

        self.game.hero_act(action_type, amount)
        self._refresh_ui()

        if review and not hand.is_complete:
            self.feedback_label.setText(format_decision_review(review))
            self.coach_message.emit(_hu_coach_message(review))

        if hand.is_complete:
            self._on_hand_complete()

    def _refresh_ui(self) -> None:
        if not self.game or not self.game.current_hand:
            return
        hand = self.game.current_hand
        hero = hand.hero

        self.live_table.update_state(hand)

        self.street_label.setText(f"🃏 {hand.street_name}")
        self.pot_label.setText(f"Pot: {hand.pot:.1f}bb")

        # Update position label
        hero_pos = hero.position if hero else "?"
        villain = [p for p in hand.players if not p.is_hero][0] if hand.players else None
        villain_pos = villain.position if villain else "?"
        self.position_label.setText(f"Hero: {hero_pos} | Villain: {villain_pos}")

        # Community cards
        _clear(self.community_row)
        if hand.community:
            for c in hand.community:
                self.community_row.addWidget(CardView(c.display))
        else:
            hint = QLabel("— Preflop, henüz board yok —")
            hint.setStyleSheet("color:#4B5563;font-size:12px;font-style:italic;padding:18px 8px;")
            hint.setAlignment(Qt.AlignCenter)
            self.community_row.addWidget(hint)

        # Hero cards
        _clear(self.hero_cards_row)
        if hero and hero.hole_cards:
            for c in hero.hole_cards:
                self.hero_cards_row.addWidget(CardView(c.display))
            self.hero_stack_label.setText(f"Stack: {hero.stack:.1f}bb | Invested: {hero.invested_this_hand:.1f}bb")

        self._update_action_buttons()

        stats = self.game.get_session_stats()
        _update_card(self.stat_hands, str(stats["hands"]), "played")
        profit_str = f"{stats['profit_bb']:+.1f}bb"
        _update_card(self.stat_profit, profit_str, f"{stats['bb_per_100']:+.1f}bb/100")
        _update_card(self.stat_winrate, f"{stats['win_rate']:.0f}%", "showdown")
        _update_card(self.stat_aggression, f"{stats.get('agg_factor', 0):.1f}", "agg factor")

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
        if result.hand_id in self._completed_hand_ids:
            return
        self._completed_hand_ids.add(result.hand_id)
        decision_summary = summarize_decision_reviews(self._current_decision_reviews)

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
            f"Hero cards: {result.hero_cards} | Board: {result.community}\n"
            f"Decision review: {decision_summary['accuracy']:.0f}% correct | "
            f"{decision_summary['mistakes']} mistake(s) | EV loss {decision_summary['ev_loss']:.2f}bb"
        )

        entry = QLabel(
            f"#{result.hand_id} | {result.hero_cards} | {result.community} | "
            f"{'W' if result.hero_won else 'L'} {result.hero_profit:+.1f}bb | "
            f"Decisions {decision_summary['accuracy']:.0f}% | EV loss {decision_summary['ev_loss']:.2f}bb"
        )
        entry.setObjectName("Green" if result.hero_won else "Muted")
        self.history_layout.addWidget(entry)

        self.next_btn.show()
        self.review_btn.show()
        self.end_btn.show()

        worst = decision_summary.get("worst")
        if worst:
            decision_line = (
                f"En pahalı karar: {worst['street']} {worst['position']} "
                f"{worst['hero_action']} yerine {worst['solver_action']} "
                f"({worst['ev_loss']:.2f}bb)."
            )
        else:
            decision_line = "Karar analizi için bu elde hero aksiyonu kaydedilmedi."
        self.coach_message.emit(
            f"HU El #{result.hand_id}: Hero {result.hero_cards}, Board {result.community}. "
            f"{'Kazandın' if result.hero_won else 'Kaybettin'} ({result.hero_profit:+.1f}bb). "
            f"Session: {self.game.get_session_stats()['profit_bb']:+.1f}bb toplam.\n\n"
            f"GTO/Exploit karar özeti: {decision_summary['accuracy']:.0f}% doğru, "
            f"{decision_summary['mistakes']} hata, EV loss {decision_summary['ev_loss']:.2f}bb.\n"
            f"{decision_line}"
        )

    def _review_last(self) -> None:
        if not self.game or not self.game.hand_history:
            return
        result = self.game.hand_history[-1]
        decision_summary = summarize_decision_reviews(self._current_decision_reviews)
        if self._current_decision_reviews:
            decision_lines = "\n".join(
                f"  • {format_decision_review(item)}"
                for item in self._current_decision_reviews
            )
            review = (
                f"🎯 HU Hand Review\n"
                f"Hero: {result.hero_cards} | Board: {result.community}\n"
                f"Result: {'WON' if result.hero_won else 'LOST'} ({result.hero_profit:+.1f}bb)\n\n"
                f"Decisions: {decision_summary['accuracy']:.0f}% correct | "
                f"{decision_summary['mistakes']} mistakes | EV loss {decision_summary['ev_loss']:.2f}bb\n\n"
                f"{decision_lines}"
            )
        else:
            review = f"HU Hand #{result.hand_id}: No hero actions recorded."
        self.coach_message.emit(review)

    def _end_session(self) -> None:
        if not self.game:
            return
        stats = self.game.get_session_stats()
        summary = (
            f"🎯 HU Session Summary\n"
            f"Hands: {stats['hands']} | Profit: {stats['profit_bb']:+.1f}bb | "
            f"Win Rate: {stats['win_rate']:.0f}% | VPIP: {stats['vpip']:.0f}%\n"
            f"BB/100: {stats['bb_per_100']:+.1f} | Aggression Factor: {stats.get('agg_factor', 0):.1f}\n\n"
            f"Keep practicing HU — position and aggression are key!"
        )
        self.coach_message.emit(summary)

    def _update_sizing_label(self, value: int) -> None:
        self.sizing_label_display.setText(f"{value}% pot")


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


def _hu_coach_message(review: dict) -> str:
    return (
        "HU karar review:\n"
        f"Spot: {review['street'].title()} {review['position']} | "
        f"Hero {review['hero_cards']} board {review['board'] or 'preflop'}\n"
        f"Hero aksiyonu: {review['hero_action']} | Baseline: {review['solver_action']} | "
        f"EV loss: {review['ev_loss']:.2f}bb | Verdict: {review['verdict']}\n"
        f"Solver frequency: {review['solver_frequency']:.0%} | Best frequency: {review['best_frequency']:.0%}\n"
        f"{review['sizing_feedback']}\n"
        f"{review['exploit_note']}\n"
        f"Drill önerisi: {review['drill_target']}\n"
        f"Kaynak güveni: {review['source_confidence']}"
    )
