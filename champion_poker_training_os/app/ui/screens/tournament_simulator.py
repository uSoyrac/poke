"""Tournament Simulator — real playable MTT.

Flow: setup → play (single table) → leak analysis
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSlider, QSpinBox, QVBoxLayout, QWidget,
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
from app.db.repository import save_played_hand
from app.engine.hand_state import ActionType, Street
from app.simulator.tournament_runner import (
    Tournament, TournamentConfig, PAYOUT_STRUCTURES,
)
from app.ui.components.card_view import CardView, CardBackView, CardPlaceholder
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import LivePokerTable, SeatState, seats_from_hand


class TournamentSimulatorScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.tournament: Tournament | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Stage container — switches between setup / play / report
        self.stack = QFrame()
        self.stack_layout = QVBoxLayout(self.stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.stack, 1)

        self._build_setup()

    # ── STAGES ─────────────────────────────────────────────────────

    def _clear_stack(self):
        while self.stack_layout.count():
            item = self.stack_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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

        # Page header
        num = QLabel("03 / TOURNAMENT")
        num.setObjectName("PageNum")
        title = _big_title("Live MTT — real chips, real blinds")
        sub = QLabel("Set conditions, play real Texas Hold'em, every hand is saved, leaks analyzed after.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 13px;")
        sub.setMaximumWidth(720)
        l.addWidget(num)
        l.addWidget(title)
        l.addWidget(sub)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #23271f; border: none; max-height: 1px;")
        l.addWidget(sep)

        # CONFIG CARD
        card = QFrame()
        card.setObjectName("Card")
        c_l = QVBoxLayout(card)
        c_l.setContentsMargins(22, 20, 22, 22)
        c_l.setSpacing(16)

        hd = QLabel("TOURNAMENT CONDITIONS")
        hd.setObjectName("TLabel")
        c_l.addWidget(hd)

        grid = QGridLayout()
        grid.setSpacing(14)

        # Tournament name
        self.name_input = QComboBox()
        self.name_input.addItems([
            "$22 Bounty Hunter", "$5.50 NLHE Turbo", "$11 Deepstack",
            "$55 Daily Sunday", "$215 High Roller", "Freebuy Daily",
        ])
        self.name_input.setEditable(True)
        grid.addWidget(self._label("EVENT NAME"), 0, 0)
        grid.addWidget(self.name_input, 1, 0)

        # Field size
        self.field_combo = QComboBox()
        self.field_combo.addItems(["2 (Heads-Up)", "6 (6-max)", "8 (8-max)", "9 (9-max)"])
        self.field_combo.setCurrentIndex(3)
        grid.addWidget(self._label("FIELD SIZE"), 0, 1)
        grid.addWidget(self.field_combo, 1, 1)

        # Starting chips
        self.chips_input = QSpinBox()
        self.chips_input.setRange(500, 50000)
        self.chips_input.setValue(2000)
        self.chips_input.setSingleStep(500)
        grid.addWidget(self._label("STARTING CHIPS"), 0, 2)
        grid.addWidget(self.chips_input, 1, 2)

        # Buy-in
        self.buyin_input = QSpinBox()
        self.buyin_input.setRange(0, 10000)
        self.buyin_input.setValue(22)
        self.buyin_input.setPrefix("$ ")
        grid.addWidget(self._label("BUY-IN"), 0, 3)
        grid.addWidget(self.buyin_input, 1, 3)

        # Structure
        self.structure_combo = QComboBox()
        self.structure_combo.addItems(["regular", "turbo", "hyper"])
        grid.addWidget(self._label("BLIND STRUCTURE"), 2, 0)
        grid.addWidget(self.structure_combo, 3, 0)

        # Hands per level
        self.handspl_input = QSpinBox()
        self.handspl_input.setRange(3, 30)
        self.handspl_input.setValue(12)
        grid.addWidget(self._label("HANDS PER LEVEL"), 2, 1)
        grid.addWidget(self.handspl_input, 3, 1)

        # Bot difficulty
        self.bot_difficulty = QComboBox()
        diff_tooltips = {
            "recreational mix": "Fish + Stations + Maniacs — softest field, biggest edge.",
            "balanced field":   "Mix of regs and a few weak spots — realistic mid-stakes.",
            "tough field":      "TAGs, Sharks, and Solver Bots — every seat plays back.",
            "sharks only":      "Solver-grade field. Expect tiny edges; bring your A-game.",
        }
        for label, note in diff_tooltips.items():
            self.bot_difficulty.addItem(label)
            self.bot_difficulty.setItemData(self.bot_difficulty.count() - 1,
                                            note, Qt.ToolTipRole)
        self.bot_difficulty.currentTextChanged.connect(
            lambda t: self.bot_difficulty.setToolTip(diff_tooltips.get(t, ""))
        )
        self.bot_difficulty.setToolTip(diff_tooltips["recreational mix"])
        grid.addWidget(self._label("FIELD STRENGTH"), 2, 2)
        grid.addWidget(self.bot_difficulty, 3, 2)

        c_l.addLayout(grid)
        l.addWidget(card)

        # Action buttons
        btn_row = QHBoxLayout()
        start_btn = QPushButton("▶  START TOURNAMENT")
        start_btn.setObjectName("PrimaryButton")
        start_btn.setMinimumHeight(46)
        start_btn.setStyleSheet("padding: 12px 32px; font-size: 14px;")
        start_btn.clicked.connect(self._start_tournament)
        btn_row.addStretch(1)
        btn_row.addWidget(start_btn)
        l.addLayout(btn_row)
        l.addStretch(1)

        self.stack_layout.addWidget(scroll)

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("TLabel")
        return lbl

    def _start_tournament(self):
        field_map = {0: 2, 1: 6, 2: 8, 3: 9}
        size = field_map.get(self.field_combo.currentIndex(), 9)
        payout_key = "Heads-Up" if size == 2 else ("6-max" if size <= 6 else "9-max")

        # Build bot mix based on difficulty
        diff = self.bot_difficulty.currentText()
        if diff == "recreational mix":
            mix = ["Fish", "Calling Station", "Aggro Fish", "Tight Passive", "Fish", "Maniac", "LAG", "Reg"]
        elif diff == "balanced field":
            mix = ["TAG", "Reg", "LAG", "Fish", "Tight Passive", "Reg", "Aggro Fish", "TAG"]
        elif diff == "tough field":
            mix = ["TAG", "Shark", "LAG", "Reg", "Solver Bot", "TAG", "Shark", "Reg"]
        else:
            mix = ["Shark", "Solver Bot", "TAG", "Shark", "Solver Bot", "TAG", "Shark", "Solver Bot"]

        config = TournamentConfig(
            name=self.name_input.currentText(),
            field_size=size,
            starting_chips=self.chips_input.value(),
            structure=self.structure_combo.currentText(),
            buyin=float(self.buyin_input.value()),
            payout_key=payout_key,
            hands_per_level=self.handspl_input.value(),
            bot_mix=mix,
        )
        self.tournament = Tournament(config)
        # Drive bot pacing from the UI (one bot per timer tick) so the
        # user sees actions land in true poker order: UTG → … → SB → BB.
        self.tournament.game.paced_bots = True
        self._bot_timer = QTimer(self)
        self._bot_timer.setInterval(450)
        self._bot_timer.timeout.connect(self._tick_bot)
        self._between_hands = False
        self._build_play()
        # Spacebar = skip waiting period / advance to next hand
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space_pressed)
        self._deal_next_hand()
        self.coach_message.emit(
            f"Turnuva başladı: {config.name}, {config.field_size} oyuncu, {config.starting_chips} chip start, "
            f"{config.structure} struct. Hedef: ödül masasına ulaşmak ve leak'leri minimize etmek."
        )

    def _build_play(self):
        self._clear_stack()
        # Top-level layout: meta bar + table area + action deck
        page = QFrame()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        # META BAR
        self.meta_bar = QFrame()
        self.meta_bar.setObjectName("Card")
        self.meta_bar.setStyleSheet("background: #131613; border: 1px solid #23271f; border-left: none; border-right: none;")
        meta_l = QHBoxLayout(self.meta_bar)
        meta_l.setContentsMargins(22, 0, 22, 0)
        meta_l.setSpacing(0)

        self.meta_cells = {}
        for key, label in [
            ("EVENT", "EVENT"),
            ("BLINDS", "BLINDS · L1"),
            ("PLAYERS", "PLAYERS"),
            ("NEXT_LVL", "NEXT LVL"),
            ("AVG", "AVG STACK"),
            ("PRIZE", "PRIZE POOL"),
        ]:
            cell = self._meta_cell(label, "—")
            self.meta_cells[key] = cell
            meta_l.addWidget(cell, 1)
        pl.addWidget(self.meta_bar)

        # SCROLL CONTENT
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 18, 22, 22)
        cl.setSpacing(16)

        # Unified poker table — same BB convention as cash games. Modern
        # online poker (PokerStars, GG, ClubGG) all display tournament
        # stacks/bets/pot in BB, not raw chips. The engine still runs in
        # chips; we only translate at the UI boundary.
        self.table = LivePokerTable()
        self.table.set_unit("bb")
        self.table.setMinimumHeight(460)
        cl.addWidget(self.table)

        # FEEDBACK BAR
        self.feedback_label = QLabel("Dealing first hand...")
        self.feedback_label.setObjectName("Muted")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; padding: 8px 0;"
        )
        cl.addWidget(self.feedback_label)

        # HAND HISTORY (compact)
        self.history_card = QFrame()
        self.history_card.setObjectName("Card")
        hist_l = QVBoxLayout(self.history_card)
        hist_l.setContentsMargins(16, 14, 16, 14)
        hist_l.setSpacing(8)
        hist_l.addWidget(self._section_head("LAST 5 HANDS"))
        self.history_layout = QVBoxLayout()
        self.history_layout.setSpacing(4)
        hist_l.addLayout(self.history_layout)
        cl.addWidget(self.history_card)

        cl.addStretch(1)
        pl.addWidget(scroll, 1)

        # ACTION DECK (sticky bottom)
        self.action_deck = self._build_action_deck()
        pl.addWidget(self.action_deck)

        self.stack_layout.addWidget(page)

    def _meta_cell(self, label: str, value: str) -> QFrame:
        f = QFrame()
        f.setStyleSheet("border-right: 1px solid #23271f;")
        v = QVBoxLayout(f)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(3)
        lbl = QLabel(label)
        lbl.setObjectName("TLabel")
        val = QLabel(value)
        val.setStyleSheet(
            "font-family: 'Space Grotesk', Inter, sans-serif; font-size: 16px; "
            "font-weight: 700; color: #f4f5ee;"
        )
        v.addWidget(lbl)
        v.addWidget(val)
        f._value_label = val
        return f

    def _section_head(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("TLabel")
        return lbl

    def _build_action_deck(self) -> QFrame:
        deck = QFrame()
        deck.setStyleSheet("background: #0f1210; border-top: 2px solid #23271f;")
        deck_v = QVBoxLayout(deck)
        deck_v.setContentsMargins(22, 8, 22, 12)
        deck_v.setSpacing(6)

        # TO CALL banner above the buttons (kept out of the felt center
        # so hero cards never cover it).
        self.to_call_banner = QLabel("")
        self.to_call_banner.setAlignment(Qt.AlignCenter)
        self.to_call_banner.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1.4px; color: #5ad17a; "
            "padding: 4px 12px; border: 1px solid #2a4a30; background: #0f1d11;"
        )
        self.to_call_banner.hide()
        banner_row = QHBoxLayout()
        banner_row.addStretch(1); banner_row.addWidget(self.to_call_banner); banner_row.addStretch(1)
        deck_v.addLayout(banner_row)

        dl = QHBoxLayout()
        dl.setSpacing(12)
        deck_v.addLayout(dl)

        # Sizing column
        sizing_box = QVBoxLayout()
        sizing_box.setSpacing(4)
        sizing_label = QLabel("RAISE SIZE")
        sizing_label.setObjectName("TLabel")
        sizing_box.addWidget(sizing_label)

        presets_row = QHBoxLayout()
        presets_row.setSpacing(0)
        self.preset_buttons = []
        for pct, label in [(33, "33%"), (50, "50%"), (66, "66%"), (75, "75%"), (100, "POT"), (150, "1.5x"), (1000, "ALL")]:
            b = QPushButton(label)
            b.setObjectName("PresetButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, p=pct: self._set_size_pct(p))
            presets_row.addWidget(b)
            self.preset_buttons.append(b)
        sizing_box.addLayout(presets_row)

        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setRange(1, 1000)
        self.size_slider.setValue(75)
        self.size_slider.valueChanged.connect(self._refresh_size_label)
        sizing_box.addWidget(self.size_slider)

        self.size_value_label = QLabel("0 chips")
        self.size_value_label.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px; color: #f4f5ee;"
        )
        sizing_box.addWidget(self.size_value_label)
        dl.addLayout(sizing_box, 2)

        # Action buttons
        actions_box = QHBoxLayout()
        actions_box.setSpacing(6)

        self.fold_btn = QPushButton("FOLD")
        self.fold_btn.setObjectName("ActionFold")
        self.fold_btn.clicked.connect(lambda: self._hero_action(ActionType.FOLD))

        self.check_btn = QPushButton("CHECK")
        self.check_btn.setObjectName("ActionCheck")
        self.check_btn.clicked.connect(lambda: self._hero_action(ActionType.CHECK))

        self.call_btn = QPushButton("CALL")
        self.call_btn.setObjectName("ActionCall")
        self.call_btn.clicked.connect(lambda: self._hero_action(ActionType.CALL))

        self.raise_btn = QPushButton("RAISE")
        self.raise_btn.setObjectName("ActionRaise")
        self.raise_btn.clicked.connect(lambda: self._hero_action(ActionType.RAISE))

        self.allin_btn = QPushButton("ALL-IN")
        self.allin_btn.setObjectName("ActionAllin")
        self.allin_btn.clicked.connect(lambda: self._hero_action(ActionType.ALL_IN))

        from PySide6.QtWidgets import QSizePolicy
        for b in (self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.allin_btn):
            # Min width fits "CALL ALL-IN  100.0 bb"; equal stretch reflows
            # cleanly when the user toggles sidebar/coach.
            b.setMinimumWidth(160)
            b.setMinimumHeight(48)
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            actions_box.addWidget(b, 1)

        dl.addLayout(actions_box, 4)
        return deck

    # ── GAME LOOP ─────────────────────────────────────────────────

    def _deal_next_hand(self):
        if not self.tournament:
            return
        if self.tournament.is_complete:
            self._build_report()
            return
        self.tournament.start_hand()
        self._refresh_table()
        # Begin paced bot processing
        if (not self.tournament.game.is_waiting_for_hero
                and not self.tournament.game.current_hand.is_complete):
            self._bot_timer.start()

    def _hero_action(self, action_type: ActionType):
        if not self.tournament or self.tournament.is_complete:
            return
        if not self.tournament.game.is_waiting_for_hero:
            return

        hand = self.tournament.game.current_hand
        hero = hand.hero
        amount = 0.0

        if action_type in (ActionType.BET, ActionType.RAISE):
            chips_target = self._compute_size_chips()
            if action_type == ActionType.RAISE:
                amount = max(hand.last_full_raise_size, chips_target)
            else:
                amount = max(hand.big_blind, chips_target)
        elif action_type == ActionType.CALL:
            amount = hand.to_call(hand.hero_idx)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack

        self.tournament.hero_act(action_type, amount)
        self._refresh_table()

        if hand.is_complete:
            self._on_hand_complete()
        else:
            self._bot_timer.start()

    def _tick_bot(self):
        """Run one engine step (one bot action) per tick — see PokerGame.step_action."""
        if not self.tournament or not self.tournament.game.current_hand:
            self._bot_timer.stop()
            return
        keep_going = self.tournament.game.step_action()
        self._refresh_table()
        if not keep_going:
            self._bot_timer.stop()
            if self.tournament.game.current_hand.is_complete:
                self._on_hand_complete()

    def _compute_size_chips(self) -> float:
        """Slider → legal raise/bet amount in tournament chips.

        Floor the value at the engine's legal min-raise so the engine
        never has to silently coerce the bet up.
        """
        hand = self.tournament.game.current_hand
        hero = hand.hero
        pct = self.size_slider.value() / 100.0
        if hand.street == Street.PREFLOP and hand.pot <= hand.big_blind * 3:
            # Open-raise land — size as 2.0x to 4.5x BB
            target = hand.big_blind * (2.0 + pct * 2.5)
        else:
            target = hand.pot * pct
        floor = max(hand.last_full_raise_size, hand.big_blind)
        if hand.current_bet > 0 and hero:
            min_raise_add = hand.current_bet + floor - hero.current_bet
            target = max(target, min_raise_add)
        else:
            target = max(target, hand.big_blind)
        if hero:
            target = min(target, hero.stack)
        return round(target, 2)

    def _set_size_pct(self, pct: int):
        # 1000 = ALL-IN
        self.size_slider.setValue(min(1000, max(1, pct)))

    def _refresh_size_label(self):
        if not self.tournament or not self.tournament.game.current_hand:
            return
        hand = self.tournament.game.current_hand
        chips = self._compute_size_chips()
        bb = max(hand.big_blind, 1)
        bb_eq = chips / bb
        pot_bb = max(hand.pot / bb, 0.01)
        pct_pot = int(round(100 * bb_eq / pot_bb))
        # BB-first display, matching the felt — chips kept as a small hint
        # at the end so the player still knows the absolute amount.
        self.size_value_label.setText(
            f"{bb_eq:.1f} bb  ·  {pct_pot}% pot  ·  {int(chips):,} chips"
        )

    # ── REFRESH UI ────────────────────────────────────────────────

    def _refresh_table(self):
        if not self.tournament:
            return
        game = self.tournament.game
        hand = game.current_hand
        if not hand:
            return

        # Meta bar
        config = self.tournament.config
        level = self.tournament.state.current_level
        self.meta_cells["EVENT"]._value_label.setText(config.name)
        ante_str = f" / {level.ante:,}" if level.ante else ""
        self.meta_cells["BLINDS"]._value_label.setText(f"{level.sb:,} / {level.bb:,}{ante_str}")
        self.meta_cells["PLAYERS"]._value_label.setText(f"{self.tournament.players_remaining} / {config.field_size}")
        self.meta_cells["NEXT_LVL"]._value_label.setText(f"{self.tournament.state.hands_until_next_level} hands")
        avg = int(sum(p.stack for p in game.players if not p.is_eliminated) / max(self.tournament.players_remaining, 1))
        self.meta_cells["AVG"]._value_label.setText(f"{avg:,}")
        self.meta_cells["PRIZE"]._value_label.setText(f"${config.prize_pool:.0f}")

        # ── Feed the unified poker table ────────────────────────────
        # Display everything in BB on the felt — divide chip values by
        # the current big blind. Matches real online poker convention.
        bb = max(hand.big_blind, 1.0)
        action_top = game._action_queue[0] if game._action_queue else -1
        seats, hero_slot, dealer_slot = seats_from_hand(
            hand.players, hand.hero_idx,
            action_queue_top=action_top, unit="bb", hand=hand,
            bb_divisor=bb,
        )
        # Flag the most-aggressive non-hero as villain
        villain_idx = None
        max_bet = 0.0
        for i, p in enumerate(hand.players):
            if p.is_hero or p.is_folded:
                continue
            if p.current_bet > max_bet:
                max_bet = p.current_bet
                villain_idx = i
        if villain_idx is not None:
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

        hero = hand.hero
        hero_cards = ([c.display for c in hero.hole_cards]
                      if (hero and hero.hole_cards and not hero.is_folded) else None)
        board = [c.display for c in hand.community]
        big_pot = (hand.street == Street.PREFLOP)
        ante_str = f" · ANTE {int(hand.ante):,}" if hand.ante else ""
        note = f"BLINDS {int(hand.small_blind):,} / {int(hand.big_blind):,}{ante_str}"

        hero_to_call = hand.to_call(hand.hero_idx) if hero else 0.0
        self.table.render_state(
            seats=seats,
            hero_slot_idx=hero_slot,
            dealer_slot_idx=dealer_slot,
            street=hand.street_name,
            board=board,
            pot=hand.pot / bb,
            hero_cards=hero_cards,
            note=note,
            big_pot=big_pot,
            show_opponent_backs=not hand.is_complete,
            to_call=hero_to_call / bb,
        )

        # TO CALL banner — BB-first, matches the table display.
        if game.is_waiting_for_hero and hero_to_call > 0 and hand.pot > 0:
            pct = int(round(100 * hero_to_call / hand.pot))
            self.to_call_banner.setText(
                f"TO CALL  {hero_to_call / bb:.1f} bb  ·  {pct}% POT"
            )
            self.to_call_banner.show()
        else:
            self.to_call_banner.hide()

        # Action buttons state
        self._update_action_buttons()

        # Refresh sizing label
        self._refresh_size_label()

    # (Legacy _opponent_widget / _next_actor_idx removed — LivePokerTable
    # now renders all opponent state directly.)

    def _update_action_buttons(self):
        """Show only legal actions. We HIDE-only (never setEnabled) so Qt's
        stylesheet engine can't get stuck in the disabled palette — see the
        matching note in play_session._update_action_buttons.
        """
        game = self.tournament.game
        hand = game.current_hand
        waiting = game.is_waiting_for_hero
        all_btns = [self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.allin_btn]
        for b in all_btns:
            b.hide()

        if not waiting or not hand or hand.is_complete:
            return

        hero_idx = hand.hero_idx
        valid = hand.get_valid_actions(hero_idx)
        valid_types = {v[0] for v in valid}
        to_call = hand.to_call(hero_idx)

        hero = hand.hero
        bb = max(hand.big_blind, 1)
        stack_meaningful = (hero and hero.stack >= bb * 0.05)
        if ActionType.FOLD in valid_types:
            self.fold_btn.show()
        if ActionType.CHECK in valid_types:
            self.check_btn.show()
        if ActionType.CALL in valid_types:
            self.call_btn.setText(f"CALL  {to_call / bb:.1f} bb")
            self.call_btn.show()
        elif to_call > 0 and ActionType.ALL_IN in valid_types and stack_meaningful:
            self.call_btn.setText(f"CALL ALL-IN  {hero.stack / bb:.1f} bb")
            self.call_btn.show()
        if ActionType.BET in valid_types:
            self.raise_btn.setText("BET")
            self.raise_btn.show()
        if ActionType.RAISE in valid_types:
            self.raise_btn.setText("RAISE")
            self.raise_btn.show()
        if stack_meaningful and to_call < hero.stack:
            self.allin_btn.setText(f"ALL-IN  {hero.stack / bb:.1f} bb")
            self.allin_btn.show()

    def _on_hand_complete(self):
        if not self.tournament:
            return
        if not self.tournament.hand_log:
            return
        result = self.tournament.hand_log[-1]

        # Persist
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
                "session_id": 1,
            })
        except Exception:
            pass

        # Feedback
        outcome = "✓  WON" if result.hero_won else ("✗  LOST" if result.hero_invested > 0 else "—  FOLDED")
        color = "#5ad17a" if result.hero_won else "#e87474" if result.hero_invested > 0 else "#898d80"
        self.feedback_label.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px; "
            f"font-weight: 600; color: {color}; padding: 8px 0;"
        )
        self.feedback_label.setText(
            f"HAND #{result.hand_id}  ·  {outcome}  ·  "
            f"Pot {int(result.pot):,}  ·  Net {int(result.hero_profit):+,} chips  ·  "
            f"{result.winner_hand_name}"
        )

        # History row
        row = QLabel(
            f"#{result.hand_id:>3}  {result.hero_cards:<8}  →  {result.community:<22}  "
            f"{'W' if result.hero_won else 'L'}  {result.hero_profit:+8,.0f}  {result.winner_hand_name}"
        )
        row.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            f"color: {'#5ad17a' if result.hero_won else '#898d80'}; padding: 2px 0;"
        )
        self.history_layout.addWidget(row)
        # Keep only last 5
        while self.history_layout.count() > 5:
            it = self.history_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        # Coach feedback
        self.coach_message.emit(
            f"El #{result.hand_id} ({result.hero_position}): {result.hero_cards} | Board: {result.community} | "
            f"{'Kazandın' if result.hero_won else 'Kaybettin'} ({result.hero_profit:+,.0f} chip). "
            f"Pot: {int(result.pot):,}. Showdown: {result.winner_hand_name}."
        )

        # Tournament complete?
        if self.tournament.is_complete:
            self._between_hands = False
            QTimer.singleShot(900, self._build_report)
        else:
            # Brief pause so the showdown is readable, then auto-deal.
            # Spacebar can skip the wait — _space_pressed checks the flag.
            self._between_hands = True
            QTimer.singleShot(1400, self._maybe_auto_deal_next)

    def _maybe_auto_deal_next(self):
        if self._between_hands:
            self._between_hands = False
            self._deal_next_hand()

    def _space_pressed(self):
        """Spacebar — skip the inter-hand wait to deal immediately."""
        if self._between_hands:
            self._between_hands = False
            self._deal_next_hand()

    # ── REPORT ────────────────────────────────────────────────────

    def _build_report(self):
        self._clear_stack()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        l = QVBoxLayout(body)
        l.setContentsMargins(28, 24, 28, 60)
        l.setSpacing(18)

        report = self.tournament.leak_report() if self.tournament else {"leaks": [], "stats": {}}

        # Header
        num = QLabel("03 / TOURNAMENT  →  POST-SESSION REPORT")
        num.setObjectName("PageNum")
        l.addWidget(num)

        finish = self.tournament.state.finish_position or "—"
        prize = self.tournament.state.prize_won
        won = (finish == 1)
        title = _big_title(f"{'CHAMPION' if won else 'Finished'} · {finish}/{self.tournament.config.field_size}")
        l.addWidget(title)

        sub = QLabel(f"Prize: ${prize:.2f} of ${self.tournament.config.prize_pool:.0f}  ·  Hands played: {self.tournament.state.hands_total}")
        sub.setObjectName("Muted")
        l.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #23271f; border: none; max-height: 1px;")
        l.addWidget(sep)

        # KPI row
        stats = report.get("stats", {})
        kpi_row = QGridLayout()
        kpi_row.setSpacing(8)
        kpis = [
            ("VPIP", f"{stats.get('vpip', 0)}%", "voluntary in pot"),
            ("PFR", f"{stats.get('pfr', 0)}%", "preflop raise"),
            ("WTSD", f"{stats.get('wtsd', 0)}%", "went to showdown"),
            ("WIN RATE", f"{stats.get('win_rate', 0)}%", "hands won"),
            ("PROFIT", f"{stats.get('profit_bb', 0):+}bb", "vs blind level"),
            ("BB/100", f"{stats.get('bb_per_100', 0):+}bb", "expectation"),
        ]
        for i, (lbl, val, sub_lbl) in enumerate(kpis):
            mc = MetricCard(lbl, val, sub_lbl, accent="Green" if "+" in val else "Mono")
            kpi_row.addWidget(mc, 0, i)
        l.addLayout(kpi_row)

        # LEAKS card
        leak_card = QFrame()
        leak_card.setObjectName("Card")
        lc_l = QVBoxLayout(leak_card)
        lc_l.setContentsMargins(20, 18, 20, 20)
        lc_l.setSpacing(12)
        lc_l.addWidget(self._section_head("LEAK ANALYSIS  ·  EV LOSS RANKED"))

        for leak in report.get("leaks", []):
            lc_l.addWidget(self._leak_row(leak))
        l.addWidget(leak_card)

        # POSITION breakdown
        pos_card = QFrame()
        pos_card.setObjectName("Card")
        pc_l = QVBoxLayout(pos_card)
        pc_l.setContentsMargins(20, 18, 20, 20)
        pc_l.setSpacing(8)
        pc_l.addWidget(self._section_head("POSITION BREAKDOWN"))
        header = QLabel(f"{'POS':<10}{'HANDS':<10}{'VPIP%':<10}{'PFR%':<10}{'BB/100':<10}")
        header.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; "
            "color: #898d80;"
        )
        pc_l.addWidget(header)
        for pos, ps in sorted(report.get("position_stats", {}).items()):
            row = QLabel(
                f"{pos:<10}{ps['hands']:<10}{ps['vpip_pct']:<10}{ps['pfr_pct']:<10}{ps['bb_per_100']:<10}"
            )
            color = "#5ad17a" if ps.get("bb_per_100", 0) > 0 else "#e87474"
            row.setStyleSheet(
                f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; color: {color};"
            )
            pc_l.addWidget(row)
        l.addWidget(pos_card)

        # Buttons
        btn_row = QHBoxLayout()
        again_btn = QPushButton("▶  PLAY AGAIN")
        again_btn.setObjectName("PrimaryButton")
        again_btn.setMinimumHeight(44)
        again_btn.clicked.connect(self._build_setup)
        ask_coach_btn = QPushButton("ASK COACH ABOUT LEAKS")
        ask_coach_btn.setObjectName("GhostButton")
        ask_coach_btn.setMinimumHeight(44)
        ask_coach_btn.clicked.connect(self._send_leaks_to_coach)
        btn_row.addStretch(1)
        btn_row.addWidget(ask_coach_btn)
        btn_row.addWidget(again_btn)
        l.addLayout(btn_row)
        l.addStretch(1)

        self.stack_layout.addWidget(scroll)

    def _leak_row(self, leak: dict) -> QFrame:
        f = QFrame()
        sev = leak.get("severity", "INFO")
        if sev == "HIGH":
            f.setStyleSheet("background: #1a0c0e; border: 1px solid #5a2828; padding: 12px;")
            sev_color = "#e87474"
        elif sev == "MEDIUM":
            f.setStyleSheet("background: #1a1408; border: 1px solid #5a4f28; padding: 12px;")
            sev_color = "#d6c668"
        else:
            f.setStyleSheet("background: #0f1d11; border: 1px solid #2a4a30; padding: 12px;")
            sev_color = "#5ad17a"

        v = QVBoxLayout(f)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)

        top = QHBoxLayout()
        sev_lbl = QLabel(sev)
        sev_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; "
            f"font-weight: 700; color: {sev_color}; "
            f"border: 1px solid {sev_color}; padding: 2px 8px;"
        )
        name = QLabel(leak.get("name", ""))
        name.setStyleSheet("font-size: 14px; font-weight: 600; color: #f4f5ee;")
        ev_loss = leak.get("ev_loss", 0)
        ev = QLabel(f"-{ev_loss:.2f}bb" if ev_loss else "")
        ev.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px; "
            f"font-weight: 500; color: {sev_color};"
        )
        top.addWidget(sev_lbl)
        top.addSpacing(10)
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(ev)
        v.addLayout(top)

        detail = QLabel(leak.get("detail", ""))
        detail.setWordWrap(True)
        detail.setStyleSheet("color: #d6d8cf; font-size: 12px;")
        v.addWidget(detail)

        fix = QLabel(f"→  {leak.get('fix', '')}")
        fix.setWordWrap(True)
        fix.setStyleSheet("color: #898d80; font-size: 12px; font-style: italic;")
        v.addWidget(fix)
        return f

    def _send_leaks_to_coach(self):
        if not self.tournament:
            return
        report = self.tournament.leak_report()
        lines = [
            f"Turnuva bitti: {self.tournament.config.name}",
            f"Sonuç: {self.tournament.state.finish_position}/{self.tournament.config.field_size} · "
            f"Ödül ${self.tournament.state.prize_won:.0f}",
            f"Toplam el: {self.tournament.state.hands_total}",
            "",
            "🔍 LEAK ANALİZİ:",
        ]
        for leak in report["leaks"][:5]:
            lines.append(f"  • [{leak['severity']}] {leak['name']}")
            lines.append(f"    {leak['detail']}")
            lines.append(f"    → Fix: {leak['fix']}")
            lines.append("")
        self.coach_message.emit("\n".join(lines))


def _clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w:
            w.deleteLater()
