from __future__ import annotations

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import analyze_played_hand, session_summary
from app.core.app_state import AppState
from app.db.repository import save_decision_review, save_played_hand
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from app.engine.bot_brain import BOT_ARCHETYPES
from app.training.decision_review import analyze_hero_decision, format_decision_review, summarize_decision_reviews
from app.ui.components.card_view import CardView
from app.ui.components.live_poker_table import LivePokerTable
from app.ui.components.metric_card import MetricCard


class FastPlaySimulatorScreen(QWidget):
    """Fast-fold style rapid hand training. Hero makes quick decisions,
    hands auto-advance for high volume practice."""

    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.game: PokerGame | None = None
        self.auto_fold_weak = False
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
        title = QLabel("⚡ Fast Play Simulator")
        title.setObjectName("Title")
        header.addWidget(title)
        subtitle = QLabel("High-volume rapid decision training. 200+ hands/hour.")
        subtitle.setObjectName("Muted")
        header.addWidget(subtitle, 1)
        layout.addLayout(header)

        # Setup row — players spinbox supports 2-11
        setup = QHBoxLayout()
        self.players_spin = QSpinBox()
        self.players_spin.setRange(2, 11)
        self.players_spin.setValue(6)
        self.players_spin.setSuffix(" players")
        self.bot_combo = QComboBox()
        self.bot_combo.addItems(list(BOT_ARCHETYPES.keys()))
        self.bot_combo.setCurrentIndex(list(BOT_ARCHETYPES.keys()).index("Balanced Reg"))
        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["20bb Short", "50bb Mid", "100bb Deep"])
        self.stack_combo.setCurrentIndex(2)

        for lbl, w in [("Players (2-11)", self.players_spin), ("Opponent", self.bot_combo), ("Stack", self.stack_combo)]:
            setup.addWidget(QLabel(lbl))
            setup.addWidget(w)

        # Shot-clock control
        self.timer_combo = QComboBox()
        self.timer_combo.addItems(["Shot clock: Off", "8s", "15s", "30s"])
        setup.addWidget(QLabel("Pressure"))
        setup.addWidget(self.timer_combo)

        self.start_btn = QPushButton("▶ Start Fast Play")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self._start)
        setup.addWidget(self.start_btn)
        layout.addLayout(setup)

        # Shot-clock countdown bar (hidden until session starts)
        self.shot_clock = ShotClockBar()
        self.shot_clock.setVisible(False)
        layout.addWidget(self.shot_clock)
        self._shot_clock_timer = QTimer(self)
        self._shot_clock_timer.setInterval(100)
        self._shot_clock_timer.timeout.connect(self._tick_shot_clock)
        self._shot_deadline: float | None = None
        self._shot_total: float = 0.0
        self._shot_clock_misses = 0

        # Stats bar
        stats = QGridLayout()
        self.stat_hands = MetricCard("Hands", "0", "played")
        self.stat_speed = MetricCard("Speed", "0/hr", "estimated", "Cyan")
        self.stat_profit = MetricCard("Profit", "0bb", "session", "Green")
        self.stat_vpip = MetricCard("VPIP", "—", "voluntary")
        for i, w in enumerate([self.stat_hands, self.stat_speed, self.stat_profit, self.stat_vpip]):
            stats.addWidget(w, 0, i)
        layout.addLayout(stats)

        # Game area
        self.game_frame = QFrame()
        self.game_frame.setObjectName("Card")
        self.game_frame.hide()
        game_layout = QVBoxLayout(self.game_frame)

        # Live oval poker table — shows all 2-11 seats with action chips, dealer, etc.
        self.live_table = LivePokerTable()
        self.live_table.setMinimumHeight(380)
        game_layout.addWidget(self.live_table, 1)

        # Compact hero / community summary row (kept for legacy lookup)
        board_row = QHBoxLayout()
        board_row.setAlignment(Qt.AlignCenter)

        self.hero_cards_row = QHBoxLayout()
        self.hero_cards_row.setAlignment(Qt.AlignCenter)
        board_row.addLayout(self.hero_cards_row)
        board_row.addWidget(QLabel("  |  "))
        self.community_row = QHBoxLayout()
        self.community_row.setAlignment(Qt.AlignCenter)
        board_row.addLayout(self.community_row)
        game_layout.addLayout(board_row)

        # Info label
        self.info_label = QLabel("—")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setObjectName("Cyan")
        game_layout.addWidget(self.info_label)

        # Quick action buttons — large for speed
        action_row = QHBoxLayout()
        self.fold_btn = QPushButton("FOLD (F)")
        self.fold_btn.setFixedHeight(50)
        self.fold_btn.clicked.connect(lambda: self._act(ActionType.FOLD))
        self.check_btn = QPushButton("CHECK (C)")
        self.check_btn.setFixedHeight(50)
        self.check_btn.clicked.connect(lambda: self._act(ActionType.CHECK))
        self.call_btn = QPushButton("CALL (L)")
        self.call_btn.setObjectName("PrimaryButton")
        self.call_btn.setFixedHeight(50)
        self.call_btn.clicked.connect(lambda: self._act(ActionType.CALL))
        self.bet_half_btn = QPushButton("BET ½ (B)")
        self.bet_half_btn.setObjectName("PrimaryButton")
        self.bet_half_btn.setFixedHeight(50)
        self.bet_half_btn.clicked.connect(lambda: self._bet_pct(0.5))
        self.bet_pot_btn = QPushButton("BET POT (P)")
        self.bet_pot_btn.setObjectName("PrimaryButton")
        self.bet_pot_btn.setFixedHeight(50)
        self.bet_pot_btn.clicked.connect(lambda: self._bet_pct(1.0))
        self.allin_btn = QPushButton("ALL-IN (A)")
        self.allin_btn.setObjectName("DangerButton")
        self.allin_btn.setFixedHeight(50)
        self.allin_btn.clicked.connect(lambda: self._act(ActionType.ALL_IN))

        for btn in [self.fold_btn, self.check_btn, self.call_btn, self.bet_half_btn, self.bet_pot_btn, self.allin_btn]:
            action_row.addWidget(btn)
        game_layout.addLayout(action_row)

        # Feedback
        self.feedback = QLabel("Start a fast play session to practice rapid decisions.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Green")
        game_layout.addWidget(self.feedback)

        layout.addWidget(self.game_frame)

        # History log (compact)
        self.history_frame = QFrame()
        self.history_frame.setObjectName("Elevated")
        self.history_layout = QVBoxLayout(self.history_frame)
        self.history_layout.addWidget(QLabel("📜 Recent Hands"))
        layout.addWidget(self.history_frame)

        # End session
        self.end_btn = QPushButton("📊 End Session & Review")
        self.end_btn.clicked.connect(self._end_session)
        self.end_btn.hide()
        layout.addWidget(self.end_btn)

        import time
        self._session_start = time.time()

    def _start(self) -> None:
        stack_map = {0: 20, 1: 50, 2: 100}
        num = self.players_spin.value()
        stack = stack_map.get(self.stack_combo.currentIndex(), 100)

        self.game = PokerGame(
            num_players=num, starting_stack=float(stack),
            small_blind=0.5, big_blind=1.0, hero_seat=0,
            bot_archetype=self.bot_combo.currentText(),
        )
        self.game_frame.show()
        self.end_btn.show()
        self.start_btn.setEnabled(False)

        # Activate shot clock if user picked one
        choice = self.timer_combo.currentText()
        if choice.startswith("Shot clock"):
            self._shot_total = 0.0
            self.shot_clock.setVisible(False)
        else:
            self._shot_total = float(choice.replace("s", "").strip())
            self.shot_clock.setVisible(True)

        import time
        self._session_start = time.time()
        self._deal()

    def _deal(self) -> None:
        if not self.game:
            return
        self._current_decision_reviews = []
        self.game.start_hand()
        self._refresh()

    def _act(self, action_type: ActionType) -> None:
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        hero = hand.hero
        amount = 0.0
        if action_type == ActionType.CALL:
            amount = min(hand.current_bet - hero.current_bet, hero.stack)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack

        review = None
        try:
            review = analyze_hero_decision(hand, action_type, amount)
            review["hand_id"] = review["hand_id"] + 10000
            review["spot_id"] = f"FAST-{review['spot_id']}"
            self._current_decision_reviews.append(review)
        except Exception:
            review = None

        self.game.hero_act(action_type, amount)
        self._refresh()

        if review and not hand.is_complete:
            self.feedback.setText(format_decision_review(review))
            self.feedback.setObjectName("Green" if review["is_correct"] else "Red")
            self.feedback.style().unpolish(self.feedback)
            self.feedback.style().polish(self.feedback)

        if hand.is_complete:
            self._on_complete()

    def _bet_pct(self, pct: float) -> None:
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        hero = hand.hero
        pot = max(hand.pot, 1)
        amount = round(pot * pct, 1)
        amount = max(hand.big_blind, min(amount, hero.stack))

        to_call = hand.current_bet - hero.current_bet
        action_type = ActionType.RAISE if to_call > 0 else ActionType.BET
        review = None
        try:
            review = analyze_hero_decision(hand, action_type, amount)
            review["hand_id"] = review["hand_id"] + 10000
            review["spot_id"] = f"FAST-{review['spot_id']}"
            self._current_decision_reviews.append(review)
        except Exception:
            review = None
        if to_call > 0:
            self.game.hero_act(ActionType.RAISE, amount)
        else:
            self.game.hero_act(ActionType.BET, amount)
        self._refresh()

        if review and not hand.is_complete:
            self.feedback.setText(format_decision_review(review))
            self.feedback.setObjectName("Green" if review["is_correct"] else "Red")
            self.feedback.style().unpolish(self.feedback)
            self.feedback.style().polish(self.feedback)

        if hand.is_complete:
            self._on_complete()

    def _start_shot_clock(self) -> None:
        """Reset & start the per-decision countdown."""
        if self._shot_total <= 0:
            return
        import time as _t
        self._shot_deadline = _t.monotonic() + self._shot_total
        self.shot_clock.set_remaining(self._shot_total, self._shot_total)
        self._shot_clock_timer.start()

    def _stop_shot_clock(self) -> None:
        self._shot_clock_timer.stop()
        self._shot_deadline = None
        if self._shot_total > 0:
            self.shot_clock.set_remaining(self._shot_total, self._shot_total)

    def _tick_shot_clock(self) -> None:
        if self._shot_deadline is None:
            return
        import time as _t
        remaining = self._shot_deadline - _t.monotonic()
        if remaining <= 0:
            # Time's up — auto-fold (or check if check is free) and count miss
            self._shot_clock_misses += 1
            self._shot_clock_timer.stop()
            self._shot_deadline = None
            self.shot_clock.set_remaining(0.0, self._shot_total)
            self.feedback.setText(
                f"⏰ Shot clock expired — auto-folded. ({self._shot_clock_misses} miss this session)"
            )
            self.feedback.setObjectName("Red")
            self.feedback.style().unpolish(self.feedback)
            self.feedback.style().polish(self.feedback)
            # Try check first (free), else fold
            if self.game and self.game.is_waiting_for_hero:
                hand = self.game.current_hand
                if hand:
                    valid = {v[0] for v in hand.get_valid_actions(hand.hero_idx)}
                    if ActionType.CHECK in valid:
                        self._act(ActionType.CHECK)
                    else:
                        self._act(ActionType.FOLD)
        else:
            self.shot_clock.set_remaining(remaining, self._shot_total)

    def _refresh(self) -> None:
        if not self.game or not self.game.current_hand:
            return
        hand = self.game.current_hand
        hero = hand.hero

        # Push hand state into the live oval table
        self.live_table.update_state(hand)

        # Hero cards (legacy compact row)
        _clear(self.hero_cards_row)
        if hero and hero.hole_cards:
            for c in hero.hole_cards:
                self.hero_cards_row.addWidget(CardView(c.display))

        # Community
        _clear(self.community_row)
        if hand.community:
            for c in hand.community:
                self.community_row.addWidget(CardView(c.display))
        else:
            for _ in range(5):
                ph = QLabel("🂠")
                ph.setFixedSize(40, 52)
                ph.setAlignment(Qt.AlignCenter)
                ph.setStyleSheet("font-size:22px;color:#4B5563;")
                self.community_row.addWidget(ph)

        # Info
        to_call = hand.current_bet - hero.current_bet if hero else 0
        self.info_label.setText(
            f"{hand.street_name} | Pot: {hand.pot:.1f}bb | "
            f"To call: {to_call:.1f}bb | Stack: {hero.stack:.1f}bb | "
            f"Position: {hero.position}"
        )

        # Shot clock: start fresh on hero's turn, stop otherwise
        if self.game.is_waiting_for_hero and self._shot_total > 0:
            if self._shot_deadline is None:
                self._start_shot_clock()
        else:
            self._stop_shot_clock()

        # Button visibility
        waiting = self.game.is_waiting_for_hero
        valid_types = {v[0] for v in hand.get_valid_actions(hand.hero_idx)} if waiting else set()

        self.fold_btn.setEnabled(ActionType.FOLD in valid_types)
        self.check_btn.setEnabled(ActionType.CHECK in valid_types)
        self.call_btn.setEnabled(ActionType.CALL in valid_types)
        self.call_btn.setText(f"CALL {to_call:.1f}" if to_call > 0 else "CALL")
        self.bet_half_btn.setEnabled(ActionType.BET in valid_types or ActionType.RAISE in valid_types)
        self.bet_pot_btn.setEnabled(ActionType.BET in valid_types or ActionType.RAISE in valid_types)
        self.allin_btn.setEnabled(waiting)

        # Update stats
        import time
        stats = self.game.get_session_stats()
        elapsed = max(1, time.time() - self._session_start)
        hands_per_hour = int(stats["hands"] / elapsed * 3600) if stats["hands"] else 0
        _update_mc(self.stat_hands, str(stats["hands"]))
        _update_mc(self.stat_speed, f"{hands_per_hour}/hr")
        _update_mc(self.stat_profit, f"{stats['profit_bb']:+.1f}bb")
        _update_mc(self.stat_vpip, f"{stats['vpip']:.0f}%")

    def _on_complete(self) -> None:
        if not self.game or not self.game.hand_history:
            return
        result = self.game.hand_history[-1]
        persisted_hand_id = result.hand_id + 10000
        if persisted_hand_id in self._completed_hand_ids:
            return
        self._completed_hand_ids.add(persisted_hand_id)
        decision_summary = summarize_decision_reviews(self._current_decision_reviews)

        # Save to DB
        try:
            save_played_hand({
                "hand_id": persisted_hand_id,  # Offset to avoid collision
                "hero_cards": result.hero_cards,
                "community": result.community,
                "pot": result.pot,
                "hero_invested": result.hero_invested,
                "hero_profit": result.hero_profit,
                "hero_won": result.hero_won,
                "winner_hand_name": result.winner_hand_name,
                "streets_seen": result.streets_seen,
            })
            for review in self._current_decision_reviews:
                save_decision_review(review)
        except Exception:
            pass

        icon = "✓" if result.hero_won else "✗"
        self.feedback.setText(
            f"{icon} #{result.hand_id} | {result.hero_cards} vs {result.community} | "
            f"{result.hero_profit:+.1f}bb | {result.winner_hand_name} | "
            f"Decisions {decision_summary['accuracy']:.0f}% | EV loss {decision_summary['ev_loss']:.2f}bb"
        )
        self.feedback.setObjectName("Green" if result.hero_won else "Red")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

        # Compact history entry
        entry = QLabel(
            f"#{result.hand_id} {result.hero_cards} | {result.hero_profit:+.1f}bb | "
            f"{decision_summary['mistakes']} mistake(s)"
        )
        entry.setObjectName("Green" if result.hero_won else "Muted")
        self.history_layout.addWidget(entry)

        # Auto deal next hand
        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, self._deal)

    def _end_session(self) -> None:
        if not self.game:
            return
        stats = self.game.get_session_stats()
        hands_data = [
            {"hero_profit": h.hero_profit, "hero_won": h.hero_won, "streets_seen": h.streets_seen}
            for h in self.game.hand_history
        ]
        summary = session_summary(stats, hands_data)
        self.coach_message.emit(summary)
        self.feedback.setText("Session ended. Check AI Coach for summary.")


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()


def _update_mc(card: MetricCard, value: str) -> None:
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
            break


class ShotClockBar(QWidget):
    """Visual countdown bar — green (>50%) → amber (>25%) → red (<25%)."""

    def __init__(self):
        super().__init__()
        self.remaining = 0.0
        self.total = 0.0
        self.setFixedHeight(34)
        self.setMinimumWidth(300)

    def set_remaining(self, remaining: float, total: float) -> None:
        self.remaining = max(0.0, remaining)
        self.total = total
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        # Track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1F2937"))
        painter.drawRoundedRect(0, 6, w, h - 12, 4, 4)
        # Filled portion
        ratio = (self.remaining / self.total) if self.total > 0 else 0
        fill_w = int(w * ratio)
        if ratio > 0.5:
            color = QColor("#10B981")
        elif ratio > 0.25:
            color = QColor("#F59E0B")
        else:
            color = QColor("#EF4444")
        painter.setBrush(color)
        painter.drawRoundedRect(0, 6, fill_w, h - 12, 4, 4)
        # Time text
        painter.setPen(QColor("#F3F4F6"))
        from PySide6.QtGui import QFont
        font = QFont(); font.setPointSize(11); font.setBold(True)
        painter.setFont(font)
        text = f"⏱  {self.remaining:0.1f}s / {self.total:0.0f}s"
        painter.drawText(self.rect(), Qt.AlignCenter, text)
        painter.end()
