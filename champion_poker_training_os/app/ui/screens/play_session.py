"""Play Session — quick cash table for one-off practice (no tournament structure)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget,
)


def _big_title(text: str) -> QLabel:
    lbl = QLabel(text)
    f = QFont()
    f.setFamily("Helvetica Neue")
    f.setPixelSize(36)
    f.setWeight(QFont.Black)
    lbl.setFont(f)
    lbl.setStyleSheet("color: #f4f5ee; padding: 0; margin: 0;")
    return lbl

from app.core.app_state import AppState
from app.ai.coach_engine import analyze_played_hand, session_summary
from app.db.repository import save_played_hand
from app.engine.game_loop import PokerGame, HandResult
from app.engine.hand_state import ActionType, Street
from app.engine.bot_brain import BOT_ARCHETYPES
from app.ui.components.card_view import CardView, CardBackView, CardPlaceholder
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import LivePokerTable, SeatState, seats_from_hand


class PlaySessionScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.game: PokerGame | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QFrame()
        self.stack_layout = QVBoxLayout(self.stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.stack, 1)
        self._build_setup()

    def _clear_stack(self):
        while self.stack_layout.count():
            item = self.stack_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── SETUP ─────────────────────────────────────────────────────

    def _build_setup(self):
        self._clear_stack()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        l = QVBoxLayout(body)
        l.setContentsMargins(28, 24, 28, 60)
        l.setSpacing(20)

        num = QLabel("02 / PLAY")
        num.setObjectName("PageNum")
        title = _big_title("Cash game — drill mode")
        sub = QLabel("Pick stakes, archetype, table size. Hands are saved to your DB and feed leak analysis.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        l.addWidget(num)
        l.addWidget(title)
        l.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #23271f; border: none; max-height: 1px;")
        l.addWidget(sep)

        card = QFrame()
        card.setObjectName("Card")
        c_l = QVBoxLayout(card)
        c_l.setContentsMargins(22, 20, 22, 22)
        c_l.setSpacing(16)
        c_l.addWidget(self._label("CASH GAME CONDITIONS"))

        grid = QGridLayout()
        grid.setSpacing(14)
        self.players_combo = QComboBox()
        self.players_combo.addItems(["2 (Heads-Up)", "6 (6-max)", "9 (Full Ring)"])
        self.players_combo.setCurrentIndex(1)
        grid.addWidget(self._label("PLAYERS"), 0, 0); grid.addWidget(self.players_combo, 1, 0)

        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["20bb", "50bb", "100bb", "150bb", "200bb"])
        self.stack_combo.setCurrentIndex(2)
        grid.addWidget(self._label("EFFECTIVE STACK"), 0, 1); grid.addWidget(self.stack_combo, 1, 1)

        # Featured bot options first (Karma + GTO Expert), then the rest
        featured = ["Karma (Mixed)", "GTO Expert", "Balanced Reg"]
        rest = [k for k in BOT_ARCHETYPES.keys() if k not in featured]
        bot_options = featured + rest
        self.bot_combo = QComboBox()
        for name in bot_options:
            self.bot_combo.addItem(name)
            # Tooltip = the archetype's `notes` so the user knows what they pick
            note = BOT_ARCHETYPES.get(name)
            if note and getattr(note, "notes", ""):
                idx = self.bot_combo.count() - 1
                self.bot_combo.setItemData(idx, f"{name} — {note.notes}", Qt.ToolTipRole)
        self.bot_combo.setCurrentIndex(bot_options.index("Karma (Mixed)"))
        self.bot_combo.currentTextChanged.connect(self._sync_bot_tooltip)
        self._sync_bot_tooltip(self.bot_combo.currentText())
        grid.addWidget(self._label("BOT ARCHETYPE"), 0, 2); grid.addWidget(self.bot_combo, 1, 2)

        c_l.addLayout(grid)
        l.addWidget(card)

        btn_row = QHBoxLayout()
        start_btn = QPushButton("▶  START SESSION")
        start_btn.setObjectName("PrimaryButton")
        start_btn.setMinimumHeight(46)
        start_btn.setStyleSheet("padding: 12px 32px; font-size: 14px;")
        start_btn.clicked.connect(self._start)
        btn_row.addStretch(1)
        btn_row.addWidget(start_btn)
        l.addLayout(btn_row)
        l.addStretch(1)

        self.stack_layout.addWidget(scroll)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("TLabel")
        return lbl

    def _sync_bot_tooltip(self, name: str) -> None:
        prof = BOT_ARCHETYPES.get(name)
        if prof and getattr(prof, "notes", ""):
            self.bot_combo.setToolTip(prof.notes)
        else:
            self.bot_combo.setToolTip("")

    def _start(self):
        players_map = {0: 2, 1: 6, 2: 9}
        stack_map = {0: 20, 1: 50, 2: 100, 3: 150, 4: 200}
        num = players_map.get(self.players_combo.currentIndex(), 6)
        stack_bb = stack_map.get(self.stack_combo.currentIndex(), 100)
        bot = self.bot_combo.currentText()

        self.game = PokerGame(
            num_players=num,
            starting_stack=float(stack_bb),
            small_blind=0.5, big_blind=1.0,
            hero_seat=0,
            bot_archetype=bot,
        )
        self._build_play()
        self._deal_next()
        self.coach_message.emit(f"Yeni session: {num}-max, {stack_bb}bb, {bot} bot. İyi eller.")

    # ── PLAY UI ───────────────────────────────────────────────────

    def _build_play(self):
        self._clear_stack()
        page = QFrame()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        # Stats bar
        stats_bar = QFrame()
        stats_bar.setStyleSheet("background: #131613; border: 1px solid #23271f; border-left: none; border-right: none;")
        sb_l = QHBoxLayout(stats_bar)
        sb_l.setContentsMargins(22, 10, 22, 10)
        sb_l.setSpacing(0)

        self.stat_hands = MetricCard("HANDS", "0", "played")
        self.stat_profit = MetricCard("PROFIT", "+0bb", "session", accent="Green")
        self.stat_vpip = MetricCard("VPIP", "—", "voluntary")
        self.stat_winrate = MetricCard("WIN RATE", "—", "won", accent="Green")
        for w in (self.stat_hands, self.stat_profit, self.stat_vpip, self.stat_winrate):
            sb_l.addWidget(w, 1)
        pl.addWidget(stats_bar)

        # Scroll body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 18, 22, 22)
        cl.setSpacing(16)

        # Unified poker table (design spec — stadium felt, seats around, hero anchored bottom)
        self.table = LivePokerTable()
        self.table.set_unit("bb")
        self.table.setMinimumHeight(440)
        cl.addWidget(self.table)

        self.feedback = QLabel("Dealing first hand...")
        self.feedback.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; color: #898d80; padding: 6px 0;"
        )
        self.feedback.setWordWrap(True)
        cl.addWidget(self.feedback)

        # History
        hist = QFrame()
        hist.setObjectName("Card")
        hist_l = QVBoxLayout(hist)
        hist_l.setContentsMargins(16, 14, 16, 14)
        hist_l.setSpacing(6)
        hist_l.addWidget(self._sect("HAND HISTORY"))
        self.history_layout = QVBoxLayout()
        self.history_layout.setSpacing(2)
        hist_l.addLayout(self.history_layout)
        cl.addWidget(hist)

        # Session control row
        ctrl = QHBoxLayout()
        next_btn = QPushButton("DEAL NEXT HAND")
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(self._deal_next)
        self.next_btn = next_btn
        next_btn.hide()
        self.review_btn = QPushButton("REVIEW LAST")
        self.review_btn.setObjectName("GhostButton")
        self.review_btn.clicked.connect(self._review_last)
        self.review_btn.setEnabled(False)  # only after a hand completes
        end_btn = QPushButton("END SESSION")
        end_btn.setObjectName("GhostButton")
        end_btn.clicked.connect(self._end_session)
        for b in (self.review_btn, end_btn, next_btn):
            b.setMinimumHeight(38)
            ctrl.addWidget(b)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        cl.addStretch(1)
        pl.addWidget(scroll, 1)

        # Action deck
        deck = QFrame()
        deck.setStyleSheet("background: #0f1210; border-top: 2px solid #23271f;")
        dl = QHBoxLayout(deck)
        dl.setContentsMargins(22, 12, 22, 12)
        dl.setSpacing(12)

        sizing = QVBoxLayout()
        sizing.setSpacing(4)
        sl = QLabel("BET SIZE (% POT)")
        sl.setObjectName("TLabel")
        sizing.addWidget(sl)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(0)
        for pct, label in [(33, "33%"), (50, "50%"), (66, "66%"), (75, "75%"), (100, "POT"), (150, "1.5x")]:
            b = QPushButton(label)
            b.setObjectName("PresetButton")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, p=pct: self.size_slider.setValue(p))
            preset_row.addWidget(b)
        sizing.addLayout(preset_row)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 300)
        self.size_slider.setValue(66)
        self.size_slider.valueChanged.connect(self._refresh_size)
        sizing.addWidget(self.size_slider)
        self.size_label = QLabel("0bb")
        self.size_label.setStyleSheet("font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px;")
        sizing.addWidget(self.size_label)
        dl.addLayout(sizing, 2)

        acts = QHBoxLayout()
        acts.setSpacing(6)
        self.fold_btn = QPushButton("FOLD"); self.fold_btn.setObjectName("ActionFold")
        self.check_btn = QPushButton("CHECK"); self.check_btn.setObjectName("ActionCheck")
        self.call_btn = QPushButton("CALL"); self.call_btn.setObjectName("ActionCall")
        self.raise_btn = QPushButton("RAISE"); self.raise_btn.setObjectName("ActionRaise")
        self.allin_btn = QPushButton("ALL-IN"); self.allin_btn.setObjectName("ActionAllin")

        self.fold_btn.clicked.connect(lambda: self._hero_action(ActionType.FOLD))
        self.check_btn.clicked.connect(lambda: self._hero_action(ActionType.CHECK))
        self.call_btn.clicked.connect(lambda: self._hero_action(ActionType.CALL))
        self.raise_btn.clicked.connect(lambda: self._hero_action(ActionType.RAISE))
        self.allin_btn.clicked.connect(lambda: self._hero_action(ActionType.ALL_IN))

        for b in (self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.allin_btn):
            b.setMinimumWidth(110)
            b.setMinimumHeight(46)
            b.setCursor(Qt.PointingHandCursor)
            acts.addWidget(b)
        dl.addLayout(acts, 3)
        pl.addWidget(deck)

        self.stack_layout.addWidget(page)

    def _sect(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("TLabel")
        return l

    # ── GAME LOOP ─────────────────────────────────────────────────

    def _deal_next(self):
        if not self.game:
            return
        if self.next_btn:
            self.next_btn.hide()
        self.game.start_hand()
        self._refresh()

    def _hero_action(self, action_type: ActionType):
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        hero = hand.hero
        amount = 0.0
        if action_type in (ActionType.BET, ActionType.RAISE):
            amount = self._size_amount_bb()
        elif action_type == ActionType.CALL:
            amount = hand.to_call(hand.hero_idx)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack
        self.game.hero_act(action_type, amount)
        self._refresh()
        if hand.is_complete:
            self._on_complete()

    def _size_amount_bb(self) -> float:
        """Translate the sizing slider into a legal raise/bet amount in bb.

        Preflop with no pot built we anchor on the big blind (open-raise
        sizing 2.2x–3x). Post-flop the slider is read as % of current pot,
        floored at the legal min-raise so the engine never has to coerce.
        """
        hand = self.game.current_hand
        hero = hand.hero
        pct = self.size_slider.value() / 100.0
        if hand.street == Street.PREFLOP and hand.pot <= hand.big_blind * 3:
            # Open or 3-bet land — size in BBs (2.2x to 4x)
            target = hand.big_blind * (2.0 + pct * 1.5)
        else:
            target = hand.pot * pct
        # Floor to legal min-raise / min-bet
        floor = max(hand.last_full_raise_size, hand.big_blind)
        if hand.current_bet > 0:
            min_raise_add = hand.current_bet + floor - hero.current_bet
            target = max(target, min_raise_add)
        else:
            target = max(target, hand.big_blind)
        return round(min(target, hero.stack), 2)

    def _refresh_size(self):
        if not self.game or not self.game.current_hand:
            return
        chips = self._size_amount_bb()
        pot = max(self.game.current_hand.pot, 0.01)
        pct = int(round(100 * chips / pot)) if pot else 0
        # Show both: total bb committed AND % of current pot
        self.size_label.setText(f"{chips:.1f} bb  ·  {pct}% pot")

    def _refresh(self):
        if not self.game or not self.game.current_hand:
            return
        hand = self.game.current_hand
        hero = hand.hero

        # ── Feed the unified poker table ────────────────────────────
        action_top = self.game._action_queue[0] if self.game._action_queue else -1
        seats, hero_slot, dealer_slot = seats_from_hand(
            hand.players, hand.hero_idx,
            action_queue_top=action_top, unit="bb", hand=hand,
        )
        # Tag the most recent aggressor (non-hero with biggest bet) as villain for visual emphasis
        villain_idx = None
        max_bet = 0.0
        for i, p in enumerate(hand.players):
            if p.is_hero or p.is_folded:
                continue
            if p.current_bet > max_bet:
                max_bet = p.current_bet
                villain_idx = i
        if villain_idx is not None:
            # Find that player in the slot-ordered list and flag villain
            cur = hand.hero_idx
            visited = 0
            slot_pos = 0
            n = len(hand.players)
            while visited < n:
                if not hand.players[cur].is_eliminated:
                    if cur == villain_idx:
                        if 0 <= slot_pos < len(seats):
                            seats[slot_pos].is_villain = True
                        break
                    slot_pos += 1
                cur = (cur + 1) % n
                visited += 1

        hero_cards = [c.display for c in hero.hole_cards] if (hero and hero.hole_cards) else None
        board = [c.display for c in hand.community]
        big_pot = (hand.street == Street.PREFLOP)
        note = f"BLINDS {hand.small_blind:g} / {hand.big_blind:g}"
        if hand.ante > 0:
            note += f" · ANTE {hand.ante:g}"

        hero_to_call = hand.to_call(hand.hero_idx) if hero else 0.0
        self.table.render_state(
            seats=seats,
            hero_slot_idx=hero_slot,
            dealer_slot_idx=dealer_slot,
            street=hand.street_name,
            board=board,
            pot=hand.pot,
            hero_cards=hero_cards,
            note=note,
            big_pot=big_pot,
            show_opponent_backs=not hand.is_complete,
            to_call=hero_to_call,
        )

        # Stats
        stats = self.game.get_session_stats()
        self.stat_hands.set_value(str(stats["hands"]))
        profit_str = f"{stats['profit_bb']:+.1f}bb"
        accent = "Green" if stats["profit_bb"] >= 0 else "Red"
        self.stat_profit.set_value(profit_str)
        self.stat_profit.set_detail(f"{stats['bb_per_100']:+}bb/100", accent=accent)
        self.stat_vpip.set_value(f"{stats['vpip']:.0f}%")
        self.stat_winrate.set_value(f"{stats['win_rate']:.0f}%")

        self._update_action_buttons()
        self._refresh_size()

    def _update_action_buttons(self):
        """Show only the actions that are legal RIGHT NOW.

        Bugfix: when to_call >= hero.stack, the engine offers ALL_IN instead
        of CALL but the user still wants to 'call all-in'. We surface the
        green CALL button in that case too, labelled accordingly.
        """
        for b in (self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.allin_btn):
            b.hide(); b.setEnabled(False)
        if not self.game or not self.game.is_waiting_for_hero:
            return
        hand = self.game.current_hand
        if not hand or hand.is_complete:
            return
        hero_idx = hand.hero_idx
        hero = hand.hero
        valid = hand.get_valid_actions(hero_idx)
        valid_types = {v[0] for v in valid}
        to_call = hand.to_call(hero_idx)

        if ActionType.FOLD in valid_types:
            self.fold_btn.show(); self.fold_btn.setEnabled(True)
        if ActionType.CHECK in valid_types:
            self.check_btn.show(); self.check_btn.setEnabled(True)
        if ActionType.CALL in valid_types:
            self.call_btn.setText(f"CALL  {to_call:.1f}")
            self.call_btn.show(); self.call_btn.setEnabled(True)
        elif to_call > 0 and ActionType.ALL_IN in valid_types and hero and hero.stack > 0:
            # Calling requires going all-in — still surface a green CALL button.
            self.call_btn.setText(f"CALL ALL-IN  {hero.stack:.0f}")
            self.call_btn.show(); self.call_btn.setEnabled(True)
        if ActionType.BET in valid_types:
            self.raise_btn.setText("BET")
            self.raise_btn.show(); self.raise_btn.setEnabled(True)
        if ActionType.RAISE in valid_types:
            self.raise_btn.setText("RAISE")
            self.raise_btn.show(); self.raise_btn.setEnabled(True)
        if hero and hero.stack > 0 and to_call < hero.stack:
            # Only show explicit ALL-IN when it's distinct from "call all-in"
            self.allin_btn.setText(f"ALL-IN  {hero.stack:.0f}")
            self.allin_btn.show(); self.allin_btn.setEnabled(True)

    def _on_complete(self):
        if not self.game or not self.game.hand_history:
            return
        r = self.game.hand_history[-1]
        try:
            save_played_hand({
                "hand_id": r.hand_id, "hero_cards": r.hero_cards, "community": r.community,
                "pot": r.pot, "hero_invested": r.hero_invested, "hero_profit": r.hero_profit,
                "hero_won": r.hero_won, "winner_hand_name": r.winner_hand_name,
                "streets_seen": r.streets_seen,
            })
        except Exception:
            pass

        color = "#5ad17a" if r.hero_won else "#e87474" if r.hero_invested > 0 else "#898d80"
        outcome = "✓  WON" if r.hero_won else ("✗  LOST" if r.hero_invested > 0 else "—  FOLDED")
        self.feedback.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px; "
            f"font-weight: 600; color: {color}; padding: 6px 0;"
        )
        self.feedback.setText(
            f"HAND #{r.hand_id}  ·  {outcome}  ·  Pot {r.pot:.1f}bb  ·  "
            f"Net {r.hero_profit:+.1f}bb  ·  {r.winner_hand_name}"
        )
        row = QLabel(
            f"#{r.hand_id:>3}  {r.hero_cards:<8}  →  {r.community:<22}  "
            f"{'W' if r.hero_won else 'L'}  {r.hero_profit:+6.1f}bb  {r.winner_hand_name}"
        )
        row.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            f"color: {'#5ad17a' if r.hero_won else '#898d80'};"
        )
        self.history_layout.addWidget(row)
        while self.history_layout.count() > 8:
            it = self.history_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        # Now that a hand exists, REVIEW LAST is meaningful
        if hasattr(self, "review_btn"):
            self.review_btn.setEnabled(True)

        self.coach_message.emit(
            f"El #{r.hand_id} ({r.hero_position}): {r.hero_cards} | Board: {r.community}. "
            f"{'Kazandın' if r.hero_won else 'Kaybettin'} ({r.hero_profit:+.1f}bb). "
            f"Pot: {r.pot:.1f}bb. {r.winner_hand_name}."
        )
        self.next_btn.show()

    def _review_last(self):
        if not self.game or not self.game.hand_history:
            return
        r = self.game.hand_history[-1]
        review = analyze_played_hand({
            "hero_cards": r.hero_cards, "community": r.community,
            "hero_profit": r.hero_profit, "hero_won": r.hero_won,
            "hero_invested": r.hero_invested, "pot": r.pot,
            "winner_hand_name": r.winner_hand_name,
        })
        self.coach_message.emit(review)

    def _end_session(self):
        if not self.game:
            return
        stats = self.game.get_session_stats()
        data = [
            {"hero_profit": h.hero_profit, "hero_won": h.hero_won, "streets_seen": h.streets_seen}
            for h in self.game.hand_history
        ]
        self.coach_message.emit(session_summary(stats, data))


def _clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w:
            w.deleteLater()
