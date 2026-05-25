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
from app.core.live_hud import LiveHUD
from app.db.repository import save_played_hand
from app.engine.hand_state import ActionType, Street
from app.simulator.mtt_field import MTTField
from app.simulator.tournament_runner import (
    Tournament, TournamentConfig, PAYOUT_STRUCTURES,
)
from app.ui.components.card_view import CardView, CardBackView, CardPlaceholder
from app.ui.components.field_picker import FieldPicker
from app.ui.components.gto_range_dialog import show_gto_dialog
from app.ui.components.gto_range_widget import GTORangeWidget
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import LivePokerTable, SeatState, seats_from_hand


class TournamentSimulatorScreen(QWidget):
    coach_message = Signal(str)
    # Emitted when a hand completes — main.py stores it so the user can
    # ask the AI coach about it on demand (no auto-Gemini call).
    hand_completed = Signal(dict)
    # Emitted on tournament start — main.py forwards to Gemini for a
    # tournament-type-specific opening briefing (strategy, ICM landmarks).
    tournament_advice_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.tournament: Tournament | None = None
        self.mtt_field: MTTField | None = None   # large-field background sim
        self.live_hud = LiveHUD()

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

        # NOTE: field size is now driven by the FieldPicker below — adding /
        # removing seats updates the total automatically.

        # Starting chips
        self.chips_input = QSpinBox()
        self.chips_input.setRange(500, 50000)
        self.chips_input.setValue(2000)
        self.chips_input.setSingleStep(500)
        grid.addWidget(self._label("STARTING CHIPS"), 0, 1)
        grid.addWidget(self.chips_input, 1, 1)

        # Buy-in
        self.buyin_input = QSpinBox()
        self.buyin_input.setRange(0, 10000)
        self.buyin_input.setValue(22)
        self.buyin_input.setPrefix("$ ")
        grid.addWidget(self._label("BUY-IN"), 0, 2)
        grid.addWidget(self.buyin_input, 1, 2)

        # FIELD SIZE — total tournament entrants (hero plays at one 9-max table;
        # all other players run statistically in the background)
        self.field_size_combo = QComboBox()
        for label, n in [
            ("9 players (single table)", 9),
            ("27 players (3 tables)", 27),
            ("50 players (6 tables)", 50),
            ("100 players (12 tables)", 100),
            ("200 players (23 tables)", 200),
            ("500 players (56 tables)", 500),
            ("1,000 players (112 tables)", 1000),
        ]:
            self.field_size_combo.addItem(label, n)
        self.field_size_combo.setCurrentIndex(4)   # 200 default
        self.field_size_combo.setToolTip(
            "Total tournament entrants. Hero plays at one 9-max table; background "
            "players are eliminated statistically so the overall player count shrinks "
            "in real-time — just like a real online MTT."
        )
        grid.addWidget(self._label("FIELD SIZE"), 0, 3)
        grid.addWidget(self.field_size_combo, 1, 3)

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

        # Hero range filter
        self.range_filter = QComboBox()
        _range_tooltips = {
            "Tüm Eller (GTO Default)": "Rastgele tüm olasılıklar — standart GTO dağılımı.",
            "Premium Only":            "Sadece AA-JJ, AKs/o — çok az el ama hepsi güçlü.",
            "TAG Range (~14%)":        "UTG açılış range'i — tight-aggressive çalışma.",
            "Geniş Range (~30%)":      "BTN-CO benzeri geniş range — postflop yeteneği gerekir.",
            "Speculative Hands":       "Suited connectors, small pairs, suited aces — implied odds drill.",
        }
        for label, tip in _range_tooltips.items():
            self.range_filter.addItem(label)
            self.range_filter.setItemData(
                self.range_filter.count() - 1, tip, Qt.ToolTipRole
            )
        self.range_filter.currentTextChanged.connect(
            lambda t: self.range_filter.setToolTip(_range_tooltips.get(t, ""))
        )
        self.range_filter.setToolTip(_range_tooltips["Tüm Eller (GTO Default)"])
        grid.addWidget(self._label("HERO EL ARALIK"), 4, 0)
        grid.addWidget(self.range_filter, 5, 0, 1, 2)

        # Field-strength preset — auto-populates the FieldPicker below
        self.bot_difficulty = QComboBox()
        diff_tooltips = {
            "Recreational Mix": "Fish + Stations + Maniacs — softest field, biggest edge.",
            "Balanced Field":   "Mix of regs and a few weak spots — realistic mid-stakes.",
            "Tough Field":      "TAGs, Sharks, and Solver Bots — every seat plays back.",
            "Solver Field":     "Solver-grade field. Expect tiny edges; bring your A-game.",
            "Karma (Random)":   "Her seat KARMA havuzundan her elde random tarz alır.",
            "Custom":           "Custom — alttaki listede istediğin gibi düzenle.",
        }
        for label, note in diff_tooltips.items():
            self.bot_difficulty.addItem(label)
            self.bot_difficulty.setItemData(self.bot_difficulty.count() - 1,
                                            note, Qt.ToolTipRole)
        self.bot_difficulty.currentTextChanged.connect(self._apply_field_preset)
        self.bot_difficulty.setToolTip(diff_tooltips["Recreational Mix"])
        grid.addWidget(self._label("FIELD STRENGTH"), 2, 2)
        grid.addWidget(self.bot_difficulty, 3, 2)

        c_l.addLayout(grid)

        # FieldPicker — seat-by-seat custom composition
        c_l.addSpacing(6)
        self.field_picker = FieldPicker(default_bots=8)  # 9-max default
        c_l.addWidget(self.field_picker)

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

    # Field-strength preset → archetype composition for the picker.
    # User can still hand-tweak via the FieldPicker after picking a preset.
    _FIELD_PRESETS = {
        "Recreational Mix": ["Fish", "Calling Station", "Aggro Fish", "Tight Passive",
                             "Fish", "Maniac", "LAG", "Reg"],
        "Balanced Field":   ["TAG", "Reg", "LAG", "Fish", "Tight Passive",
                             "Reg", "Aggro Fish", "TAG"],
        "Tough Field":      ["TAG", "Shark", "LAG", "Reg", "Solver Bot",
                             "TAG", "Shark", "Reg"],
        "Solver Field":     ["Shark", "Solver Bot", "TAG", "Shark", "Solver Bot",
                             "TAG", "Shark", "Solver Bot"],
        "Karma (Random)":   ["Random (Karma)"] * 8,
    }

    def _apply_field_preset(self, name: str) -> None:
        comp = self._FIELD_PRESETS.get(name)
        if comp:
            self.field_picker.set_composition(comp)
        # "Custom" — leave picker untouched

    def _start_tournament(self):
        archetypes = self.field_picker.get_archetypes()
        size = len(archetypes) + 1  # hero + bots
        payout_key = "Heads-Up" if size == 2 else ("6-max" if size <= 6 else "9-max")

        # Map UI range filter label → game engine preset key
        _range_map = {
            "Tüm Eller (GTO Default)": "",
            "Premium Only":            "Premium",
            "TAG Range (~14%)":        "TAG Range",
            "Geniş Range (~30%)":      "Geniş Range",
            "Speculative Hands":       "Speculative",
        }
        range_filter = _range_map.get(self.range_filter.currentText(), "")

        config = TournamentConfig(
            name=self.name_input.currentText(),
            field_size=size,
            starting_chips=self.chips_input.value(),
            structure=self.structure_combo.currentText(),
            buyin=float(self.buyin_input.value()),
            payout_key=payout_key,
            hands_per_level=self.handspl_input.value(),
            bot_mix=archetypes,
            hero_range_filter=range_filter,
        )
        self.tournament = Tournament(config)
        # Drive bot pacing from the UI (one bot per timer tick) so the
        # user sees actions land in true poker order: UTG → … → SB → BB.
        self.tournament.game.paced_bots = True
        self._bot_timer = QTimer(self)
        self._bot_timer.setInterval(450)
        self._bot_timer.timeout.connect(self._tick_bot)
        self._between_hands = False

        # Background auto-play timer — fires every 250 ms regardless of
        # visibility.  When this tab is the active one it's a no-op; when
        # the user is on another tab it drives the tournament forward
        # automatically so all parallel tabs advance simultaneously.
        self._bg_timer = QTimer(self)
        self._bg_timer.setInterval(250)
        self._bg_timer.timeout.connect(self._bg_tick)

        # Create MTT background field simulator.
        # field_size_combo = total entrants; hero_table_size = seats at hero's table.
        mtt_size = self.field_size_combo.currentData()
        self.mtt_field = MTTField(
            field_size=mtt_size,
            buyin=float(self.buyin_input.value()),
            structure=self.structure_combo.currentText(),
            hero_table_size=size,
        )
        self.mtt_field.update_hero_table(size)  # hero table starts full

        self._bg_timer.start()
        self._build_play()
        # Spacebar = skip waiting period / advance to next hand
        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space_pressed)
        # Style Guide § 8 — F/C/R/A action keys (mirror of play_session)
        QShortcut(QKeySequence("F"), self, activated=lambda: self._key_action("F"))
        QShortcut(QKeySequence("C"), self, activated=lambda: self._key_action("C"))
        QShortcut(QKeySequence("R"), self, activated=lambda: self._key_action("R"))
        QShortcut(QKeySequence("A"), self, activated=lambda: self._key_action("A"))
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._end_and_restart)
        self._deal_next_hand()
        # AI coach fires only on user request — no auto briefing on start.

    def _end_and_restart(self) -> None:
        """Abort the running tournament and return to the setup screen.

        Stops the bot pacing timer, drops the in-memory Tournament, and
        re-builds the setup stage so the user can configure & launch a
        new one. Hands already played are preserved in the DB.
        """
        # Stop any pending bot ticks
        timer = getattr(self, "_bot_timer", None)
        if timer is not None:
            timer.stop()
        bg = getattr(self, "_bg_timer", None)
        if bg is not None:
            bg.stop()
        self.tournament = None
        self.mtt_field = None
        self.live_hud = LiveHUD()
        self.state.tournament_context = None
        self._build_setup()
        self.coach_message.emit(
            "Turnuva bitirildi. Yeni turnuva için setup'ı düzenle veya 'START TOURNAMENT'a bas."
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

        # End / Restart strip — abort the running tournament at any moment
        # and return to setup. The current hand result is preserved in the
        # DB; only the in-memory tournament is dropped.
        end_box = QFrame()
        end_box.setStyleSheet("border: none;")
        end_l = QVBoxLayout(end_box)
        end_l.setContentsMargins(8, 6, 14, 6)
        end_l.setSpacing(4)
        # Escape the ampersand (&& → &) so Qt doesn't treat it as a mnemonic
        # accelerator that would underline the next character.
        self.end_btn = QPushButton("X  END  &&  NEW")
        self.end_btn.setObjectName("EndTournamentBtn")
        self.end_btn.setCursor(Qt.PointingHandCursor)
        self.end_btn.setToolTip("Turnuvayı şimdi bitir ve setup ekranına dön (Esc)")
        self.end_btn.setStyleSheet(
            "QPushButton#EndTournamentBtn { background:#1a0e0e; color:#e87474; "
            "border:1px solid #5a2222; font-family:'JetBrains Mono',monospace; "
            "font-size:11px; font-weight:700; letter-spacing:1.4px; padding:6px 14px; }"
            "QPushButton#EndTournamentBtn:hover { background:#2a1414; color:#f29090; "
            "border-color:#e87474; }"
        )
        self.end_btn.clicked.connect(self._end_and_restart)
        end_l.addWidget(self.end_btn)
        meta_l.addWidget(end_box)

        pl.addWidget(self.meta_bar)

        # FIELD STRIP — real-time MTT field-wide status bar.
        # Shown only when total field > single table (field_size > 9).
        self.field_strip = QFrame()
        self.field_strip.setStyleSheet(
            "background: #090e08; border-bottom: 1px solid #1e221d;"
        )
        fs_l = QHBoxLayout(self.field_strip)
        fs_l.setContentsMargins(22, 5, 22, 5)
        fs_l.setSpacing(0)
        self._fs_label = QLabel("—")
        self._fs_label.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            "color: #898d80; letter-spacing: 0.3px;"
        )
        fs_l.addWidget(self._fs_label)
        pl.addWidget(self.field_strip)
        if not self.mtt_field or self.mtt_field.field_size <= 9:
            self.field_strip.hide()
        else:
            self._refresh_field_strip()

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
        v.setSpacing(2)
        lbl = QLabel(label)
        lbl.setObjectName("TLabel")
        val = QLabel(value)
        val.setStyleSheet(
            "font-family: 'Space Grotesk', Inter, sans-serif; font-size: 16px; "
            "font-weight: 700; color: #f4f5ee;"
        )
        sub = QLabel("")
        sub.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 10px; "
            "color: #5a5e54; letter-spacing: 0.8px;"
        )
        v.addWidget(lbl)
        v.addWidget(val)
        v.addWidget(sub)
        f._label_widget = lbl
        f._value_label = val
        f._sub_label = sub
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

        # GTO buton + mini range strip
        gto_row = QHBoxLayout()
        gto_row.setSpacing(8)
        self.gto_btn = QPushButton("⊞ GTO")
        self.gto_btn.setToolTip("Mevcut pozisyon ve stack'e göre GTO range analizi (G)")
        self.gto_btn.setStyleSheet(
            "QPushButton { background:#0f2318; color:#5ad1ce; border:1px solid #5ad1ce; "
            "font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; "
            "letter-spacing:1.5px; padding:5px 14px; }"
            "QPushButton:hover { background:#132a20; }"
        )
        self.gto_btn.setMinimumHeight(32)
        self.gto_btn.clicked.connect(self._show_gto_popup)
        self.gto_range = GTORangeWidget()
        self.gto_range.setMaximumHeight(52)
        gto_row.addWidget(self.gto_btn)
        gto_row.addWidget(self.gto_range, 1)
        deck_v.addLayout(gto_row)

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
            self.tournament.advance_after_hand_complete()
            self._on_hand_complete()
        else:
            self._bot_timer.start()

    def _tick_bot(self):
        """Run one engine step (one bot action) per tick — see PokerGame.step_action."""
        if not self.tournament or not self.tournament.game.current_hand:
            self._bot_timer.stop()
            return
        keep_going = self.tournament.game.step_action()
        # Only update the display when this tab is the active (visible) one —
        # background tabs skip the expensive UI refresh.
        if self.isVisible():
            self._refresh_table()
        if not keep_going:
            self._bot_timer.stop()
            hand = self.tournament.game.current_hand
            if hand and hand.is_complete:
                # Record hand result + update tournament state BEFORE reading hand_log
                self.tournament.advance_after_hand_complete()
                if self.isVisible():
                    self._on_hand_complete()
                # Background: _bg_tick will deal the next hand automatically.

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
        lvl_idx = self.tournament.state.level_idx + 1
        # Use full MTT field stats when a large field is active; otherwise
        # fall back to the hero-table counters tracked by Tournament.
        if self.mtt_field and self.mtt_field.field_size > 9:
            total     = self.mtt_field.field_size
            remaining = self.mtt_field.players_remaining
            paid      = self.mtt_field.paid_places
        else:
            remaining = self.tournament.players_remaining
            total     = config.field_size
            paid      = config.paid_places
        bubble_dist = remaining - paid   # negative = already ITM

        self.meta_cells["EVENT"]._value_label.setText(config.name)
        self.meta_cells["EVENT"]._sub_label.setText(f"${config.buyin:.0f} buy-in")

        ante_str = f" / {level.ante:,}" if level.ante else ""
        self.meta_cells["BLINDS"]._label_widget.setText(f"BLINDS · L{lvl_idx}")
        self.meta_cells["BLINDS"]._value_label.setText(f"{level.sb:,} / {level.bb:,}{ante_str}")
        self.meta_cells["BLINDS"]._sub_label.setText(config.structure.upper())

        # PLAYERS: "alive / field" — crystal-clear at a glance
        # bubble_dist = how many need to bust before everyone is ITM
        # bubble_dist  > 3  → far from bubble
        # bubble_dist == 1  → ON THE BUBBLE (next bust = ITM for all)
        # remaining <= paid → already ITM
        self.meta_cells["PLAYERS"]._value_label.setText(f"{remaining} / {total}")
        if remaining <= paid:
            bubble_tag = "✓ ITM"
        elif bubble_dist == 1:
            bubble_tag = "🔴 BUBBLE"
        elif bubble_dist <= 3:
            bubble_tag = f"bubble −{bubble_dist}"
        else:
            bubble_tag = f"top {paid} paid"
        self.meta_cells["PLAYERS"]._sub_label.setText(
            f"{total - remaining} elendi  ·  {bubble_tag}"
        )

        self.meta_cells["NEXT_LVL"]._value_label.setText(f"{self.tournament.state.hands_until_next_level}")
        self.meta_cells["NEXT_LVL"]._sub_label.setText("hands to next level")

        avg = int(sum(p.stack for p in game.players if not p.is_eliminated) / max(remaining, 1))
        self.meta_cells["AVG"]._value_label.setText(f"{avg:,}")
        hero_p2 = hand.hero
        if hero_p2:
            hero_bb_avg = round(hero_p2.stack / max(level.bb, 1), 1)
            avg_bb_val = round(avg / max(level.bb, 1), 1)
            self.meta_cells["AVG"]._sub_label.setText(f"hero {hero_bb_avg:.0f}bb · avg {avg_bb_val:.0f}bb")

        prize_pool = (self.mtt_field.prize_pool
                      if self.mtt_field and self.mtt_field.field_size > 9
                      else config.prize_pool)
        self.meta_cells["PRIZE"]._value_label.setText(f"${prize_pool:.0f}")
        self.meta_cells["PRIZE"]._sub_label.setText(f"top {paid} paid")

        # ── Push live tournament context to AppState so the AI Coach can
        # tailor advice (ICM, bubble, stack depth, blind pressure). ─────
        hero_p = hand.hero
        hero_bb = float(hero_p.stack) / max(level.bb, 1) if hero_p else 0.0
        # paid / remaining / total / prize_pool already resolved above (mtt_field or config)
        # bubble_dist < 0 → already ITM; == 1 → on bubble
        on_bubble = (0 <= bubble_dist <= 1)
        avg_bb = avg / max(level.bb, 1)
        stack_pressure = ("short" if hero_bb < 15 else
                          "medium" if hero_bb < 30 else
                          "deep")
        self.state.tournament_context = {
            "active": True,
            "event": config.name,
            "structure": config.structure,
            "buyin": config.buyin,
            "field_size": total,
            "players_remaining": remaining,
            "level": self.tournament.state.level_idx + 1,
            "blinds": f"{level.sb}/{level.bb}",
            "ante": level.ante,
            "hands_until_next_level": self.tournament.state.hands_until_next_level,
            "hero_chips": int(hero_p.stack) if hero_p else 0,
            "hero_bb": round(hero_bb, 1),
            "avg_bb": round(avg_bb, 1),
            "stack_pressure": stack_pressure,
            "payouts_paid": paid,
            "bubble_distance": bubble_dist,
            "on_bubble": on_bubble,
            "prize_pool": prize_pool,
        }

        # ── Feed the unified poker table ────────────────────────────
        # Display everything in BB on the felt — divide chip values by
        # the current big blind. Matches real online poker convention.
        bb = max(hand.big_blind, 1.0)
        action_top = game._action_queue[0] if game._action_queue else -1
        # Live HUD: merge observed stats with bot archetype profile
        raw_profiles = game.get_bot_profiles()
        merged_profiles = {}
        for idx, prof in raw_profiles.items():
            base = {
                "vpip": getattr(prof, "vpip", 0),
                "pfr": getattr(prof, "pfr", 0),
                "three_bet": getattr(prof, "three_bet", 0),
                "aggression": getattr(prof, "aggression", 0),
                "af": getattr(prof, "aggression", 0),
                "fold_to_cbet": getattr(prof, "fold_to_cbet", 0),
                "river_bluff": getattr(prof, "river_bluff", 0),
                "call_down": getattr(prof, "call_down", 0),
                "overbet_freq": getattr(prof, "overbet_freq", 0),
                "notes": getattr(prof, "notes", ""),
            }
            merged = self.live_hud.merge_with_profile(idx, base)
            obs = self.live_hud.get(idx)
            if obs:
                merged["obs_hands"] = obs["obs_hands"]
            merged_profiles[idx] = type("_P", (), merged)()

        seats, hero_slot, dealer_slot = seats_from_hand(
            hand.players, hand.hero_idx,
            action_queue_top=action_top, unit="bb", hand=hand,
            bb_divisor=bb,
            bot_profiles=merged_profiles,
        )

        # ── GTO Range widget güncelle ──────────────────────────────
        if hasattr(self, "gto_range") and not hand.is_complete:
            hero_p = hand.hero
            if hero_p:
                pos = getattr(hero_p, "position", "") or ""
                stack_bb = float(hero_p.stack) / bb
                self.gto_range.update_range(pos, stack_bb, game_type="tournament")
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

    def _show_gto_popup(self) -> None:
        """GTO butonu — mevcut turnuva el state'ini okuyup popup aç."""
        pos, stack_bb, hero_cards, street, pot, players = "", 100.0, "", "preflop", 0.0, 6
        level_str = ""
        if self.tournament and self.tournament.game.current_hand:
            hand = self.tournament.game.current_hand
            game = self.tournament.game
            bb = max(hand.big_blind, 1.0)
            hero = hand.hero
            if hero:
                pos = getattr(hero, "position", "") or ""
                stack_bb = float(hero.stack) / bb
                if hero.hole_cards:
                    hero_cards = " ".join(c.display for c in hero.hole_cards[:2])
            street = getattr(hand, "street_name", "preflop")
            pot = float(hand.pot) / bb
            players = sum(1 for p in hand.players
                          if not getattr(p, "is_eliminated", False)
                          and not getattr(p, "is_folded", False))
            lvl = self.tournament.state.current_level
            level_str = f"L{self.tournament.state.level_idx + 1} · {int(lvl.sb)}/{int(lvl.bb)}"
        elif self.tournament:
            players = self.tournament.players_remaining

        show_gto_dialog(
            parent=self,
            position=pos,
            stack_bb=stack_bb,
            players_active=players,
            game_type="tournament",
            hero_cards=hero_cards,
            street=street,
            pot_bb=pot,
            level=level_str,
        )

    def _maybe_refill_table(self) -> None:
        """Reseat opponents from the background field when hero's table runs low.

        Mirrors real MTT table consolidation: when a table shrinks to ≤ 4 players
        and the overall field still has players, the tournament director breaks
        another table and moves those players here.  We simulate that by:
          1. Pulling the required count from mtt_field's background pool.
          2. Reviving eliminated bot seats with the current average stack.
          3. Resetting the tournament's completion flag if it fired prematurely
             (i.e., hero is still alive but table ran out of bots).
        """
        if not self.mtt_field or not self.tournament:
            return
        if self.tournament.hero_busted:
            return   # Hero is out — tournament legitimately over
        if self.mtt_field.bg_players_remaining <= 0:
            return   # No background players left to draw from

        alive_at_table = self.tournament.players_remaining
        if alive_at_table >= 5:
            return   # Table still healthy — no action needed

        # How many seats to fill (target 8–9, limited by background pool)
        n_to_add = min(8 - alive_at_table, self.mtt_field.bg_players_remaining)
        if n_to_add <= 0:
            return

        # Average stack of active players at hero's table
        alive_players = [p for p in self.tournament.game.players if not p.is_eliminated]
        avg_stack = (sum(p.stack for p in alive_players) / len(alive_players)
                     if alive_players else float(self.tournament.config.starting_chips))
        avg_stack = max(avg_stack, float(self.tournament.state.current_level.bb * 8))

        # Pull these players from the background field
        self.mtt_field._bg_remaining -= n_to_add

        # Revive eliminated bot seats (never revive hero)
        revived = 0
        for seat_idx, p in enumerate(self.tournament.game.players):
            if revived >= n_to_add:
                break
            if p.is_eliminated and not p.is_hero:
                p.is_eliminated = False
                p.stack = avg_stack
                p.current_bet = 0.0
                p.is_folded = False
                p.hole_cards = []
                p.is_all_in = False
                # Remove from the tournament's elimination ledger so these
                # seats don't get double-counted in the finish-position calc.
                if seat_idx in self.tournament.state.eliminated_order:
                    self.tournament.state.eliminated_order.remove(seat_idx)
                revived += 1

        if revived == 0:
            return

        # If the tournament engine already set is_complete because
        # players_left ≤ 1 (but hero is NOT busted), roll it back.
        new_alive = sum(1 for p in self.tournament.game.players if not p.is_eliminated)
        if self.tournament.state.is_complete and not self.tournament.hero_busted:
            self.tournament.state.is_complete = False
            self.tournament.state.finish_position = None
            self.tournament.state.prize_won = 0.0

        self.tournament.state.players_left = new_alive
        self.mtt_field.update_hero_table(new_alive)

        # Announce in the feedback bar
        field_left = self.mtt_field.players_remaining
        self.feedback_label.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; "
            "font-weight: 600; color: #5ad1ce; padding: 8px 0;"
        )
        self.feedback_label.setText(
            f"🔄  MASA DENGELEME — {revived} yeni oyuncu geldi.  "
            f"Masada: {new_alive} oyuncu  ·  "
            f"Sahada kalan: {field_left:,}"
        )

    def _refresh_field_strip(self) -> None:
        """Update the thin MTT field status bar below the meta bar."""
        if not self.mtt_field or not hasattr(self, "_fs_label"):
            return
        f = self.mtt_field
        total_rem = f.players_remaining
        total     = f.field_size
        elim      = total - total_rem
        bd        = f.bubble_distance   # signed; negative = ITM

        if f.is_itm:
            bubble_str = "✓  ITM"
        elif bd == 1:
            bubble_str = "🔴  BUBBLE"
        elif bd <= 5:
            bubble_str = f"bubble  -{bd}"
        else:
            bubble_str = f"{bd} to bubble"

        prizes = f.prize_summary(n=3)
        self._fs_label.setText(
            f"FIELD:  {total_rem:,} / {total:,} players  ·  "
            f"{elim:,} eliminated  ·  {bubble_str}  ·  "
            f"{f.tables_active} tables  ·  {prizes}"
        )
        self.field_strip.show()

    def _on_hand_complete(self):
        if not self.tournament:
            return
        if not self.tournament.hand_log:
            return
        result = self.tournament.hand_log[-1]
        # Live HUD güncelle
        if self.tournament.game.current_hand:
            self.live_hud.update_from_hand(self.tournament.game.current_hand)

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

        # Store hand data for on-demand AI analysis.
        # The coach panel will analyse it only when the user clicks
        # "Soru sor..." or "Spot Analizi" — NOT automatically.
        level = self.tournament.state.current_level
        bb = max(level.bb, 1)
        hero_player = (self.tournament.game.players[0]
                       if self.tournament.game.players else None)
        self.hand_completed.emit({
            "hand_id":          result.hand_id,
            "hero_cards":       result.hero_cards,
            "community":        result.community or "—",
            "hero_position":    result.hero_position,
            "hero_stack_bb":    round(hero_player.stack / bb, 1) if hero_player else 0,
            "pot":              round(result.pot / bb, 1),
            "hero_invested":    round(result.hero_invested / bb, 1),
            "hero_profit":      round(result.hero_profit / bb, 1),
            "hero_won":         result.hero_won,
            "winner_hand_name": result.winner_hand_name,
            "streets_seen":     result.streets_seen,
            "actions":          "",
            "source":           "tournament_simulator",
        })

        # Tick the background MTT field — simulate eliminations at other tables.
        if self.mtt_field:
            n_alive = sum(
                1 for p in self.tournament.game.players if not p.is_eliminated
            )
            self.mtt_field.update_hero_table(n_alive)
            self.mtt_field.tick(1)
            self._refresh_field_strip()

        # Table balancing — if hero's table has run low on opponents but the
        # background field still has players, reseat new opponents so the
        # experience stays a full ring (mirrors real MTT table consolidation).
        self._maybe_refill_table()

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

    # ── BACKGROUND AUTO-PLAY ──────────────────────────────────────

    def _bg_tick(self) -> None:
        """Drive this tournament forward while the tab is in the background.

        Fires every 250 ms.  When the tab is visible the method is a no-op
        so the normal _bot_timer / hero-action flow remains in control.
        When the tab is hidden (user is on another tab) it:
          1. Processes one bot step via step_action() if a hand is running.
          2. Auto-acts for hero (check > cheap-fold) so no hand gets stuck.
          3. Deals the next hand automatically between rounds.
        This gives every parallel tournament tab real-time simultaneous
        progress — the user can switch tabs at any point and see the live state.
        """
        if self.isVisible():
            return   # Active tab — user controls everything
        if not self.tournament or self.tournament.is_complete:
            self._bg_timer.stop()
            return

        game = self.tournament.game

        # ── Between hands: auto-deal ──────────────────────────────
        if not game.current_hand or game.current_hand.is_complete:
            if not self.tournament.is_complete:
                try:
                    self.tournament.start_hand()
                    if (not game.is_waiting_for_hero
                            and game.current_hand
                            and not game.current_hand.is_complete):
                        self._bot_timer.start()
                except Exception:
                    pass
            return

        # ── Hero decision: auto-act ────────────────────────────────
        if game.is_waiting_for_hero:
            self._auto_hero_bg()
            return

        # ── Bot action: process one step ──────────────────────────
        if not self._bot_timer.isActive():
            try:
                keep = game.step_action()
                if not keep and game.current_hand and game.current_hand.is_complete:
                    self.tournament.advance_after_hand_complete()
            except Exception:
                pass

    def _auto_hero_bg(self) -> None:
        """Minimal-investment hero action when running in background.

        Priority: CHECK (free) > FOLD (safe) > CALL if cheap (≤ 5bb).
        Never raises or goes all-in in background — user didn't approve it.
        """
        if not self.tournament or not self.tournament.game.is_waiting_for_hero:
            return
        game = self.tournament.game
        hand = game.current_hand
        if not hand:
            return
        valid = hand.get_valid_actions(hand.hero_idx)
        valid_types = {v[0] for v in valid}
        level = self.tournament.state.current_level
        try:
            if ActionType.CHECK in valid_types:
                self.tournament.hero_act(ActionType.CHECK, 0.0)
            elif ActionType.FOLD in valid_types:
                to_call = hand.to_call(hand.hero_idx)
                # Call if it's ≤ 3bb (limped / min-raised pot) — fold otherwise
                if (ActionType.CALL in valid_types
                        and to_call <= level.bb * 3
                        and to_call < (hand.hero.stack if hand.hero else 0)):
                    self.tournament.hero_act(ActionType.CALL, to_call)
                else:
                    self.tournament.hero_act(ActionType.FOLD, 0.0)
            elif ActionType.CALL in valid_types:
                to_call = hand.to_call(hand.hero_idx)
                self.tournament.hero_act(ActionType.CALL, to_call)
        except Exception:
            pass

        # Post-action: advance tournament if hand is now complete
        if hand.is_complete:
            try:
                self.tournament.advance_after_hand_complete()
            except Exception:
                pass
        elif not game.is_waiting_for_hero and not self._bot_timer.isActive():
            self._bot_timer.start()

    def showEvent(self, event) -> None:
        """Refresh the meta bar and table as soon as this tab becomes visible."""
        super().showEvent(event)
        if self.tournament and self.tournament.game.current_hand:
            self._refresh_table()

    def _key_action(self, key: str) -> None:
        """F/C/R/A → click the matching action button if visible."""
        if (not self.tournament or self.tournament.is_complete
                or not self.tournament.game.is_waiting_for_hero):
            return
        if key == "F" and self.fold_btn.isVisible():
            self.fold_btn.click()
        elif key == "C":
            if self.call_btn.isVisible():
                self.call_btn.click()
            elif self.check_btn.isVisible():
                self.check_btn.click()
        elif key == "R" and self.raise_btn.isVisible():
            self.raise_btn.click()
        elif key == "A" and self.allin_btn.isVisible():
            self.allin_btn.click()

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
