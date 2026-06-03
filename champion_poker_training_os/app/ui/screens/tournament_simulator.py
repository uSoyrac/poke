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
from app.core.logging import log_swallowed
from app.core.live_hud import LiveHUD
from app.db.repository import save_played_hand
from app.engine.game_loop import hero_stat_fields
from app.engine.hand_state import ActionType, Street
from app.simulator.mtt_field import MTTField
from app.simulator.tournament_runner import (
    Tournament, TournamentConfig, PAYOUT_STRUCTURES,
)
from app.ui.components.card_view import CardView, CardBackView, CardPlaceholder
from app.ui.components.field_picker import FieldPicker
from app.ui.components.gto_range_dialog import show_gto_dialog
from app.ui.components.gto_range_widget import GTORangeWidget, GTODecisionReveal
from app.poker.decision_capture import DecisionRecorder
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

        # Hero range filter — 169-el CHART picker (varsayılan tüm eller)
        from app.ui.components.hand_range_selector import all_hand_keys
        self._hero_range_hands = all_hand_keys()        # varsayılan: hepsi
        self.range_btn = QPushButton()
        self.range_btn.setCursor(Qt.PointingHandCursor)
        self.range_btn.setToolTip(
            "Hero'nun deal edileceği elleri chart'tan seç. Varsayılan tüm "
            "eller; 'Sıfırla' deyip belirli elleri çalışabilirsin.")
        self.range_btn.clicked.connect(self._open_hero_range_dialog)
        self._update_range_btn_label()
        grid.addWidget(self._label("HERO EL ARALIK"), 4, 0)
        grid.addWidget(self.range_btn, 5, 0, 1, 2)

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
        # GERÇEKÇİ STAKE ALANLARI — buy-in'e göre gerçek online MTT kompozisyonu.
        # Seçilince hem hero masası hem arka-plan alanı o tier'dan örneklenir.
        from app.engine.bot_brain import FIELD_TIERS
        self._field_tier = None
        for tname in FIELD_TIERS:
            label = f"🌍 Gerçek: {tname}"
            self.bot_difficulty.addItem(label)
            self.bot_difficulty.setItemData(
                self.bot_difficulty.count() - 1,
                f"Gerçek {tname} MTT alanı — bu stake'te karşılaşacağın "
                "gerçekçi profil dağılımı (zayıf-ağırlıklı, karikatür değil).",
                Qt.ToolTipRole)
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

    def _update_range_btn_label(self) -> None:
        n = len(getattr(self, "_hero_range_hands", []) or [])
        if n >= 169 or n == 0:
            self.range_btn.setText("Tüm Eller (GTO Default)  ▾")
        else:
            pct = 100.0 * n / 169
            self.range_btn.setText(f"Seçili: {n}/169 el  (%{pct:.0f})  ▾")

    def _open_hero_range_dialog(self) -> None:
        from app.ui.components.hand_range_selector import HandRangeDialog
        dlg = HandRangeDialog(initial=self._hero_range_hands, parent=self)
        if dlg.exec():
            self._hero_range_hands = dlg.selected_hands()
            self._update_range_btn_label()

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
        # Gerçek stake tier → o dağılımdan 8 bot örnekle (hero masası snapshot'ı)
        if name.startswith("🌍 Gerçek: "):
            from app.engine.bot_brain import realistic_mtt_mix
            tier = name.replace("🌍 Gerçek: ", "")
            self._field_tier = tier
            import random as _r
            comp = realistic_mtt_mix(8, rng=_r.Random(), tier=tier)
            self.field_picker.set_composition(comp)
            return
        self._field_tier = None
        comp = self._FIELD_PRESETS.get(name)
        if comp:
            self.field_picker.set_composition(comp)
        # "Custom" — leave picker untouched

    def _start_tournament(self):
        archetypes = self.field_picker.get_archetypes()
        size = len(archetypes) + 1  # hero + bots
        payout_key = "Heads-Up" if size == 2 else ("6-max" if size <= 6 else "9-max")

        # Hero range — chart seçimi: tüm eller seçiliyse filtre yok (""),
        # değilse seçili el kümesi (motor custom set'i destekliyor).
        sel = getattr(self, "_hero_range_hands", None)
        from app.ui.components.hand_range_selector import all_hand_keys
        if not sel or len(sel) >= 169:
            range_filter = ""
        else:
            range_filter = set(sel)

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
        self._recorder = DecisionRecorder()   # hero karar yakalama (reveal/grade)

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
            tier=getattr(self, "_field_tier", None),
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
        # Turnuva başında bir kerelik açılış briefing'i (strateji + ICM landmark).
        self._emit_opening_briefing(config)

    def _emit_opening_briefing(self, config) -> None:
        """Turnuva başlarken bir kerelik açılış briefing prompt'u yayınla.

        tournament_advice_requested sinyali main.py'de Gemini'ye yönlenir.
        Prompt buy-in + structure + Hero range + ICM landmark içerir.
        """
        rng = config.hero_range_filter or "Tüm Eller (GTO Default)"
        mtt_n = (self.field_size_combo.currentData()
                 if hasattr(self, "field_size_combo") else config.field_size)
        prompt = (
            f"[TURNUVA AÇILIŞ BRIEFING]\n"
            f"Event: {config.name} · Structure: {config.structure} · "
            f"Buy-in: ${config.buyin:.0f} · Field: {mtt_n} oyuncu · "
            f"Başlangıç: {config.starting_chips} chip\n"
            f"Hero range filtresi: {rng}\n\n"
            f"Bu turnuvaya başlarken kısa bir strateji brifingi ver (6-8 madde): "
            f"erken/orta/geç aşama planı, stack derinliğine göre yaklaşım, "
            f"ICM landmark'ları (bubble, pay jump, final table), hangi rakip "
            f"tiplerini hedeflemeli, nelerden kaçınmalı. Türkçe, net, maddeli."
        )
        try:
            self.tournament_advice_requested.emit(prompt)
        except Exception:
            pass

    def _emit_closing_evaluation(self, *, finish, field_size, prize, profit,
                                 roi, won, itm, pct_rank, total_hands,
                                 stats, leaks, config) -> None:
        """Turnuva BİTİNCE bu turnuvaya ÖZEL kapsamlı AI koç değerlendirmesi.

        Açılış briefing'in karşılığı — sonuç + gerçek stats + leak'lerle
        beslenip Gemini'den (yoksa offline koç) eğitici bir post-mortem ister.
        """
        def _g(k, d=0):
            try:
                return stats.get(k, d)
            except Exception:
                return d
        leak_lines = "; ".join(
            (l.get("name", "") if isinstance(l, dict) else str(l))
            for l in (leaks or [])[:6]) or "belirgin leak yok"
        outcome = ("ŞAMPİYON 🏆" if won else
                   (f"ITM — {finish}. sıra" if itm else f"{finish}. sıra (ITM dışı)"))
        prompt = (
            f"[TURNUVA SONU DEĞERLENDİRME]\n"
            f"Event: {config.name} · {config.structure} · Buy-in ${config.buyin:.0f} · "
            f"Field {field_size} oyuncu\n"
            f"SONUÇ: {outcome}  ·  top %{pct_rank}  ·  "
            f"Kâr ${profit:+.0f} (ROI %{roi:.0f})  ·  Oynanan el: {total_hands}\n"
            f"Hero stats — VPIP %{_g('vpip'):.0f} · PFR %{_g('pfr'):.0f} · "
            f"3bet %{_g('three_bet', _g('3bet')):.0f} · AF {_g('af', _g('aggression')):.1f} · "
            f"WTSD %{_g('wtsd'):.0f} · W$SD %{_g('wsd'):.0f}\n"
            f"Tespit edilen leak'ler: {leak_lines}\n\n"
            f"Bu turnuvaya ÖZEL, kapsamlı bir POST-MORTEM değerlendirme yap "
            f"(8-10 madde): (1) genel performans + bu finish'in yorumu, "
            f"(2) en kritik 2-3 leak ve SOMUT düzeltme, (3) stack-depth/ICM/"
            f"bubble/final-table oynanışı, (4) pozisyonel kâr/zarar, (5) bir "
            f"sonraki turnuva için 3 somut hedef. Türkçe, net, maddeli, eğitici."
        )
        try:
            self.tournament_advice_requested.emit(prompt)
        except Exception as e:
            from app.core.logging import log_swallowed
            log_swallowed("tournament.closing_eval", e)

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

        # El-sonu notlandırılmış GTO reveal (Real Experience Mode'da bloklayan)
        self.gto_reveal = GTODecisionReveal()
        deck_v.addWidget(self.gto_reveal)

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
        self._recorder.reset()
        self._await_space = False
        if hasattr(self, "gto_reveal"):
            self.gto_reveal.hide_panel()
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

        self._recorder.attach_hero(action_type, amount, bb=max(hand.big_blind, 1))
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
        _real_xp = bool(getattr(getattr(self, "state", None), "real_experience", False))
        if hasattr(self, "gto_range"):
            # Real Experience Mode: TÜM GTO bağlamı gizli (gerçek deneyim).
            self.gto_range.setVisible(not _real_xp)
        if hasattr(self, "gto_range") and not _real_xp and not hand.is_complete:
            hero_p = hand.hero
            if hero_p:
                pos = getattr(hero_p, "position", "") or ""
                stack_bb = float(hero_p.stack) / bb
                # Compute hero hand key (e.g. "AKs", "QJo", "77") for GTO lookup
                hero_hk = None
                if hero_p.hole_cards and len(hero_p.hole_cards) >= 2:
                    try:
                        from app.engine.bot_brain import hand_key
                        hero_hk = hand_key(hero_p.hole_cards[0], hero_p.hole_cards[1])
                    except Exception:
                        hero_hk = None
                _adv = None
                try:
                    from app.poker.gto_live_advice import live_gto_advice
                    _adv = live_gto_advice(hand, hand.hero_idx, mode="MTT")
                except Exception:
                    _adv = None
                self.gto_range.update_range(
                    pos, stack_bb,
                    game_type="tournament",
                    hero_hand=hero_hk,
                    reveal_action=False,   # eğitim modu: cevabı el sonunda göster
                    advice=_adv,           # gerçek senaryo (RFI/vs-3bet/push…)
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

    def _tourn_stage(self) -> str:
        """Turnuva aşaması — kalan oyuncu oranı + bubble/FT yakınlığı.

        Segment analizinde 'MTT · orta aşama · ...' etiketine girer.
        """
        t = getattr(self, "tournament", None)
        if not t:
            return ""
        try:
            field = max(int(getattr(t.config, "field_size", 0) or 0), 1)
            left = int(getattr(t.state, "players_left", field) or field)
            paid = int(getattr(t.config, "paid_places", 0) or 0)
            if left <= max(1, min(9, paid or 9)):
                return "final masa"
            if paid and left <= paid + max(2, int(0.05 * field)):
                return "bubble"
            frac = left / field
            if frac > 0.66:
                return "erken aşama"
            if frac > 0.33:
                return "orta aşama"
            return "geç aşama"
        except Exception:
            return ""

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

        # ── Canlı GTO advice (turnuva → MTT mode) ──
        gto = None
        try:
            from app.poker.gto_live_advice import live_gto_advice
            gto = live_gto_advice(hand, hero_idx, mode="MTT")
            # AI koç için state'e yaz
            st = getattr(self, "state", None)
            if st is not None:
                if gto and gto.available:
                    # Somut pot-matematiği (bb cinsinden) için pot/to_call sakla
                    try:
                        _to_call_bb = float(hand.to_call(hero_idx)) / bb
                        _pot_bb = float(hand.pot) / bb
                        _street = hand.street_name
                    except Exception:
                        _to_call_bb, _pot_bb, _street = 0.0, 0.0, ""
                    st.live_gto = {
                        "scenario": gto.scenario, "hand": gto.hand_key,
                        "stack_bb": gto.stack_bb, "tier": gto.tier_label,
                        "fold": gto.fold, "call": gto.call,
                        "raise": gto.raise_, "allin": gto.allin,
                        "pot_bb": _pot_bb, "to_call_bb": _to_call_bb,
                        "street": _street,
                    }
                    try:
                        from app.poker.sizing_advice import sizing_advice
                        sz = sizing_advice(hand, hero_idx, mode="MTT")
                        if sz and sz.available:
                            st.live_gto["sizing"] = {
                                "label": sz.label, "rec_bb": sz.recommended_bb,
                                "frac": sz.recommended_frac, "note": sz.note,
                            }
                    except Exception:
                        pass
                else:
                    st.live_gto = None
        except Exception:
            gto = None

        # ── Karar noktasını yakala (el sonu reveal/grade için) ──
        _st = getattr(self, "state", None)
        _real_xp = bool(getattr(_st, "real_experience", False))
        _sz = _st.live_gto.get("sizing") if (_st and getattr(_st, "live_gto", None)) else None
        self._recorder.capture(hand, hero_idx, gto, bb=bb, sizing=_sz,
                               fmt="mtt", stage=self._tourn_stage())

        def lbl(base: str, atype) -> str:
            # Oyun sırasında ASLA GTO cevabı/%'si gösterme (her iki modda).
            # GTO sadece el bitince, duruma göre reveal panelinde açıklanır.
            return base

        if ActionType.FOLD in valid_types:
            self.fold_btn.setText(lbl("FOLD", ActionType.FOLD))
            self.fold_btn.show()
        if ActionType.CHECK in valid_types:
            self.check_btn.setText(lbl("CHECK", ActionType.CHECK))
            self.check_btn.show()
        if ActionType.CALL in valid_types:
            self.call_btn.setText(lbl(f"CALL  {to_call / bb:.1f} bb", ActionType.CALL))
            self.call_btn.show()
        elif to_call > 0 and ActionType.ALL_IN in valid_types and stack_meaningful:
            self.call_btn.setText(f"CALL ALL-IN  {hero.stack / bb:.1f} bb")
            self.call_btn.show()
        if ActionType.BET in valid_types:
            self.raise_btn.setText(lbl("BET", ActionType.BET))
            self.raise_btn.show()
        if ActionType.RAISE in valid_types:
            self.raise_btn.setText(lbl("RAISE", ActionType.RAISE))
            self.raise_btn.show()
        if stack_meaningful and to_call < hero.stack:
            self.allin_btn.setText(lbl(f"ALL-IN  {hero.stack / bb:.1f} bb", ActionType.ALL_IN))
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
        if self.mtt_field.is_final_table:
            return   # Final masaya inildi → artık dengeleme yok, kazanana dek oynanır
        if self.mtt_field.bg_players_remaining <= 0:
            return   # No background players left to draw from

        alive_at_table = self.tournament.players_remaining
        seats = len(self.tournament.game.players)
        # Masa ≤6 oyuncuya inince yeniden doldur (gerçek MTT'de kısa masalar
        # kırılır, oyuncular dağıtılır). Hedef: tam masa (koltuk sayısı).
        if alive_at_table > 6:
            return

        target = min(seats, self.mtt_field.players_remaining)
        need = target - alive_at_table
        if need <= 0:
            return

        # Gelen oyuncular gerçekten arka plandan taşınır (toplam saha sabit)
        moved = self.mtt_field.move_into_hero_table(need)
        if moved <= 0:
            return

        # Gelen oyuncuların stack'i ≈ saha ortalaması (başka masadan geliyorlar)
        avg_stack = self.mtt_field.avg_stack_chips
        avg_stack = max(avg_stack, float(self.tournament.state.current_level.bb * 8))

        # Engine: elenen koltukları TAZE arketip + isimle doldur (field bot_mix'ten)
        revived = self.tournament.rebalance_hero_table(alive_at_table + moved, avg_stack)
        if revived == 0:
            # Taşıma geri al (koltuk doldurulamadı)
            self.mtt_field._hero_table_remaining -= moved
            self.mtt_field._bg_remaining += moved
            return

        # Engine prematüre "bitti" dediyse (hero hayatta ama masa boşaldı) geri al
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
        # Alan sertliği: zayıflar hızlı patlar → derinleştikçe reg-ağır olur
        strength = f.field_strength_label()
        strength_seg = f"alan: {strength}  ·  " if strength else ""
        self._fs_label.setText(
            f"FIELD:  {total_rem:,} / {total:,} players  ·  "
            f"{elim:,} eliminated  ·  {bubble_str}  ·  "
            f"{f.tables_active} tables  ·  {strength_seg}{prizes}"
        )
        self.field_strip.show()

    def _on_hand_complete(self):
        if not self.tournament:
            return
        if not self.tournament.hand_log:
            return
        # ── El-sonu GTO reveal + karar persist + oturum karnesi ──
        _real_xp = bool(getattr(getattr(self, "state", None), "real_experience", False))
        if not hasattr(self, "_session_score"):
            from app.poker.session_score import SessionScore
            self._session_score = SessionScore()
        self._session_score.add_hand(self._recorder.log)
        if hasattr(self, "gto_reveal"):
            self.gto_reveal.show_decisions(
                self._recorder.log, graded=_real_xp,
                session_summary=self._session_score.summary())
        try:
            from app.db.repository import record_decision_log
            record_decision_log(self._recorder.log)
        except Exception as e:
            log_swallowed("tournament_simulator.record_decision_log", e)
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
                **hero_stat_fields(result),
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
            # Capture hero's MTT finish position the moment they bust —
            # before tick() runs (which would shrink the field artificially).
            if (self.tournament.hero_busted
                    and self.mtt_field.field_size > 9
                    and not getattr(self.tournament.state, "_mtt_finish_locked", False)):
                hero_alive_count = self.mtt_field.players_remaining
                # +1 because players_remaining excludes hero (just busted)
                self.tournament.state.finish_position = hero_alive_count + 1
                self.tournament.state.prize_won = (
                    self.mtt_field.prize_for_place(hero_alive_count + 1)
                )
                # Lock so we don't keep recomputing on subsequent hand_completes
                self.tournament.state._mtt_finish_locked = True
            else:
                # Only tick the bg field when hero is still alive (eliminations
                # after hero busts shouldn't compress hero's recorded finish).
                if not self.tournament.hero_busted:
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
            self._between_hands = True
            # Hero bu eli OYNADIYSA (karar verdiyse) el-sonu GTO reveal'ı
            # okuması için OTOMATİK dağıtma — SPACE ile geçsin (panel artık
            # "açılıp kapanmıyor"). Sadece hero'nun karışmadığı eller oto-akar.
            has_review = any(d.get("hero_action") for d in self._recorder.log)
            self._await_space = _real_xp or has_review
            if self._await_space:
                self.feedback_label.setText(
                    self.feedback_label.text() + "   ·   ▸ SPACE → sonraki el")
            else:
                QTimer.singleShot(1400, self._maybe_auto_deal_next)

    def _maybe_auto_deal_next(self):
        # Hero el oynadıysa / Real Experience → sadece manuel (SPACE) ilerleme.
        if getattr(self, "_await_space", False):
            return
        if bool(getattr(getattr(self, "state", None), "real_experience", False)):
            return
        if self._between_hands:
            self._between_hands = False
            self._deal_next_hand()

    def _space_pressed(self):
        """Spacebar — skip the inter-hand wait to deal immediately."""
        if self._between_hands:
            self._between_hands = False
            self._deal_next_hand()

    def apply_experience_mode(self, real: bool) -> None:
        """Real Experience Mode toggle'ı — GTO panel görünürlüğünü tazele."""
        if hasattr(self, "gto_range"):
            self.gto_range.setVisible(not real)
        try:
            if self.tournament and self.tournament.game.current_hand:
                self._refresh_table()
        except Exception:
            pass

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
        from app.db.repository import save_tournament_result, get_tournament_history

        self._clear_stack()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        l = QVBoxLayout(body)
        l.setContentsMargins(28, 24, 28, 60)
        l.setSpacing(20)

        if not self.tournament:
            l.addWidget(QLabel("No tournament data."))
            self.stack_layout.addWidget(scroll)
            return

        report  = self.tournament.leak_report()
        stats   = report.get("stats", {})
        config  = self.tournament.config
        state   = self.tournament.state

        # Real field/prize from MTTField when active
        field_size = self.mtt_field.field_size  if self.mtt_field else config.field_size
        prize_pool = self.mtt_field.prize_pool  if self.mtt_field else config.prize_pool

        # ── MTT FIELD CORRECTION ──────────────────────────────────────────
        # tournament_runner sets finish_position using TABLE players_left + 1
        # (correct for single-table). For multi-table tournaments this is
        # wrong: e.g. busting with 5 left at your table while 168 are still
        # alive in the field → real finish is 169th, not 6th.
        # Override with field-level position + prize when MTTField is active.
        if self.mtt_field and self.mtt_field.field_size > 9 and self.tournament.hero_busted:
            field_finish, field_prize = self.mtt_field.hero_finish()
            # hero_finish() returns alive count (excluding hero) → add 1 for
            # hero's actual finishing place
            field_finish = max(1, field_finish + 1)
            state.finish_position = field_finish
            state.prize_won = field_prize

        # Winners (hero is last one standing) — also recompute prize from
        # the MTT field's payout table so 1st place actually pays out
        if self.mtt_field and self.mtt_field.field_size > 9 and not self.tournament.hero_busted \
                and state.finish_position == 1:
            state.prize_won = self.mtt_field.prize_for_place(1)

        finish   = state.finish_position or field_size
        prize    = state.prize_won
        buyin    = config.buyin
        profit   = prize - buyin
        roi      = (profit / buyin * 100) if buyin > 0 else 0.0
        won      = (finish == 1)
        itm      = prize > 0
        pct_rank = round((1 - finish / max(field_size, 1)) * 100, 1)  # top-X%

        # ── Turnuvaya ÖZEL kapsamlı AI koç değerlendirmesi (post-mortem) ──
        self._emit_closing_evaluation(
            finish=finish, field_size=field_size, prize=prize, profit=profit,
            roi=roi, won=won, itm=itm, pct_rank=pct_rank,
            total_hands=len(self.tournament.hand_log), stats=stats,
            leaks=report.get("leaks", []), config=config)

        # ── Persist to history ─────────────────────────────────────────
        try:
            save_tournament_result({
                "name":            config.name,
                "field_size":      field_size,
                "buyin":           buyin,
                "structure":       config.structure,
                "finish_position": finish,
                "prize_won":       prize,
                "hands_played":    state.hands_total,
                "vpip":            stats.get("vpip", 0),
                "pfr":             stats.get("pfr", 0),
                "bb_per_100":      stats.get("bb_per_100", 0),
                "profit":          profit,
            })
        except Exception:
            pass

        # ── Page header ────────────────────────────────────────────────
        num = QLabel("03 / TOURNAMENT  →  SONUÇ RAPORU")
        num.setObjectName("PageNum")
        l.addWidget(num)

        # ── HERO CARD — finish + prize (BIG) ──────────────────────────
        hero_card = QFrame()
        hero_card.setObjectName("Card")
        if won:
            hero_card.setStyleSheet(
                "background: linear-gradient(135deg, #0d2b14, #132e1a); "
                "border: 2px solid #5ad17a;"
            )
        elif itm:
            hero_card.setStyleSheet(
                "background: #131613; border: 2px solid #5ad1ce;"
            )
        else:
            hero_card.setStyleSheet(
                "background: #131613; border: 1px solid #2a2e26;"
            )

        hc_outer = QHBoxLayout(hero_card)
        hc_outer.setContentsMargins(28, 22, 28, 22)
        hc_outer.setSpacing(32)

        # LEFT: finish position
        finish_col = QVBoxLayout()
        finish_col.setSpacing(4)
        ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
        finish_ordinal = ordinals.get(finish, f"{finish}th")
        finish_lbl = QLabel("FİNİŞ POZİSYONU")
        finish_lbl.setObjectName("TLabel")
        finish_num = QLabel(f"{finish_ordinal} / {field_size:,}")
        finish_num.setStyleSheet(
            "font-family: 'Space Grotesk', Inter, sans-serif; "
            "font-size: 42px; font-weight: 800; "
            f"color: {'#5ad17a' if won else ('#5ad1ce' if itm else '#f4f5ee')};"
        )
        rank_lbl = QLabel(
            f"{'🏆 ŞAMPİYON' if won else ('✓ ITM' if itm else f'top {100 - pct_rank:.0f}%  bitişte elendi')}"
        )
        rank_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 1.4px; "
            f"color: {'#5ad17a' if (won or itm) else '#898d80'};"
        )
        finish_col.addWidget(finish_lbl)
        finish_col.addWidget(finish_num)
        finish_col.addWidget(rank_lbl)
        hc_outer.addLayout(finish_col, 2)

        # DIVIDER
        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        div.setStyleSheet("color: #2a2e26; background: #2a2e26; max-width: 1px;")
        hc_outer.addWidget(div)

        # CENTER: prize + ROI
        prize_col = QVBoxLayout()
        prize_col.setSpacing(4)
        prize_head = QLabel("ÖDÜL")
        prize_head.setObjectName("TLabel")
        prize_val = QLabel(f"${prize:,.2f}")
        prize_val.setStyleSheet(
            "font-family: 'Space Grotesk', Inter, sans-serif; "
            "font-size: 38px; font-weight: 800; "
            f"color: {'#5ad17a' if prize > 0 else '#f4f5ee'};"
        )
        roi_color = "#5ad17a" if roi >= 0 else "#e87474"
        roi_lbl = QLabel(
            f"ROI {roi:+.1f}%  ·  net {profit:+.2f}$  ·  pool ${prize_pool:,.0f}"
        )
        roi_lbl.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            f"font-weight: 600; letter-spacing: 0.8px; color: {roi_color};"
        )
        prize_col.addWidget(prize_head)
        prize_col.addWidget(prize_val)
        prize_col.addWidget(roi_lbl)
        hc_outer.addLayout(prize_col, 2)

        div2 = QFrame()
        div2.setFrameShape(QFrame.VLine)
        div2.setStyleSheet("color: #2a2e26; background: #2a2e26; max-width: 1px;")
        hc_outer.addWidget(div2)

        # RIGHT: event meta
        meta_col = QVBoxLayout()
        meta_col.setSpacing(6)
        meta_items = [
            ("EVENT",     config.name),
            ("FIELD",     f"{field_size:,} oyuncu  ·  ${buyin:.0f} buy-in"),
            ("YAPI",      f"{config.structure.upper()}  ·  {state.hands_total} el oynandı"),
            ("ÖDENEN",    f"top {self.mtt_field.paid_places if self.mtt_field else config.paid_places} yer"),
        ]
        for key, val in meta_items:
            kl = QLabel(key)
            kl.setObjectName("TLabel")
            vl = QLabel(val)
            vl.setStyleSheet("font-size: 13px; color: #d6d8cf; font-weight: 600;")
            meta_col.addWidget(kl)
            meta_col.addWidget(vl)
        hc_outer.addLayout(meta_col, 3)

        l.addWidget(hero_card)

        # ── COMPREHENSIVE EVALUATION ───────────────────────────────────
        eval_card = QFrame()
        eval_card.setObjectName("Card")
        ev_l = QVBoxLayout(eval_card)
        ev_l.setContentsMargins(22, 18, 22, 18)
        ev_l.setSpacing(10)
        ev_l.addWidget(self._section_head("KAPSAMLI DEĞERLENDİRME"))

        vpip    = stats.get("vpip", 0)
        pfr     = stats.get("pfr", 0)
        bb100   = stats.get("bb_per_100", 0)
        wtsd    = stats.get("wtsd", 0)
        win_r   = stats.get("win_rate", 0)

        # Grade: based on finish percentile + key stats
        if won:
            grade, grade_color, grade_note = "S", "#5ad17a", "Olağanüstü — turnuva galibiyeti"
        elif pct_rank >= 85:
            grade, grade_color, grade_note = "A+", "#5ad17a", f"Elit finish — top {100-pct_rank:.0f}% içinde"
        elif pct_rank >= 70:
            grade, grade_color, grade_note = "A", "#5ad17a", f"Çok güçlü — top {100-pct_rank:.0f}% içinde"
        elif pct_rank >= 55:
            grade, grade_color, grade_note = "B+", "#a8d17a", f"Ortanın üstü — top {100-pct_rank:.0f}% içinde"
        elif pct_rank >= 40:
            grade, grade_color, grade_note = "B", "#d6c668", f"Ortalama finish — top {100-pct_rank:.0f}% içinde"
        elif pct_rank >= 20:
            grade, grade_color, grade_note = "C", "#d6a668", f"Erken eliş — top {100-pct_rank:.0f}% içinde"
        else:
            grade, grade_color, grade_note = "D", "#e87474", f"Çok erken eliş — ilk %{100-pct_rank:.0f}"

        grade_row = QHBoxLayout()
        grade_box = QLabel(grade)
        grade_box.setAlignment(Qt.AlignCenter)
        grade_box.setFixedSize(64, 64)
        grade_box.setStyleSheet(
            f"font-family: 'Space Grotesk', Inter, sans-serif; font-size: 32px; "
            f"font-weight: 900; color: {grade_color}; "
            f"border: 2px solid {grade_color}; background: transparent;"
        )
        grade_note_lbl = QLabel(grade_note)
        grade_note_lbl.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {grade_color};"
        )
        grade_row.addWidget(grade_box)
        grade_row.addSpacing(16)
        grade_row.addWidget(grade_note_lbl)
        grade_row.addStretch(1)
        ev_l.addLayout(grade_row)

        # Narrative bullets
        bullets = []
        # Finish narrative
        if won:
            bullets.append(("✓", "#5ad17a", "Turnuvayı kazandın — mükemmel performans."))
        elif itm:
            bullets.append(("✓", "#5ad17a", f"Para ödülüne girdin ({finish_ordinal}) — pozitif sonuç."))
        else:
            bullets.append(("✗", "#e87474",
                f"{finish_ordinal} sırada elendi — para ödülüne {finish - (self.mtt_field.paid_places if self.mtt_field else config.paid_places)} yer kaldı."))

        # VPIP
        if 20 <= vpip <= 30:
            bullets.append(("✓", "#5ad17a", f"VPIP {vpip:.1f}% — sağlıklı aralıkta (hedef: 20–30%)."))
        elif vpip > 30:
            bullets.append(("⚠", "#d6c668", f"VPIP {vpip:.1f}% — biraz geniş, özellikle early position'da sıkıştır."))
        else:
            bullets.append(("⚠", "#d6c668", f"VPIP {vpip:.1f}% — sıkı oynuyor, steal ve defend spotları kaçıyor."))

        # PFR
        if pfr > 0:
            gap = vpip - pfr
            if gap <= 8:
                bullets.append(("✓", "#5ad17a", f"PFR {pfr:.1f}% — agresif ve sağlıklı (VPIP-PFR gap: {gap:.1f}%)."))
            else:
                bullets.append(("✗", "#e87474", f"PFR {pfr:.1f}% — çok pasif (gap {gap:.1f}%). Limp yerine raise et."))

        # BB/100
        if bb100 > 5:
            bullets.append(("✓", "#5ad17a", f"Chip EV: {bb100:+.1f} bb/100 — kazançlı oyun ritmi."))
        elif bb100 > -10:
            bullets.append(("→", "#898d80", f"Chip EV: {bb100:+.1f} bb/100 — breakeven yakını."))
        else:
            bullets.append(("✗", "#e87474", f"Chip EV: {bb100:+.1f} bb/100 — önemli chip kayıpları var."))

        # WTSD
        if wtsd <= 28:
            bullets.append(("✓", "#5ad17a", f"WTSD {wtsd:.1f}% — showdown disiplini iyi."))
        elif wtsd <= 36:
            bullets.append(("→", "#898d80", f"WTSD {wtsd:.1f}% — biraz fazla showdown'a gidiliyor."))
        else:
            bullets.append(("✗", "#e87474", f"WTSD {wtsd:.1f}% — showdown'a çok gidiyor, bluff-catch overload."))

        for icon, color, text in bullets:
            row = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(18)
            icon_lbl.setStyleSheet(
                f"font-family: 'JetBrains Mono', monospace; font-size: 12px; "
                f"font-weight: 700; color: {color};"
            )
            txt_lbl = QLabel(text)
            txt_lbl.setWordWrap(True)
            txt_lbl.setStyleSheet(f"font-size: 12px; color: #d6d8cf;")
            row.addWidget(icon_lbl)
            row.addWidget(txt_lbl, 1)
            ev_l.addLayout(row)

        l.addWidget(eval_card)

        # ── KPI STRIP ─────────────────────────────────────────────────
        kpi_row = QGridLayout()
        kpi_row.setSpacing(8)
        kpis = [
            ("VPIP",     f"{vpip:.1f}%",              "voluntary in pot",    20 <= vpip <= 30),
            ("PFR",      f"{pfr:.1f}%",               "preflop raise",       pfr >= 15),
            ("WTSD",     f"{wtsd:.1f}%",              "went to showdown",    wtsd <= 30),
            ("WIN RATE", f"{win_r:.1f}%",             "hands won",           win_r >= 25),
            ("BB/100",   f"{bb100:+.1f}bb",           "chip EV/100 hands",   bb100 > 0),
            ("ELLER",    str(state.hands_total),      "toplam oynanan el",   True),
        ]
        for i, (lbl, val, sub_lbl, good) in enumerate(kpis):
            mc = MetricCard(lbl, val, sub_lbl, accent="Green" if good else "Red")
            kpi_row.addWidget(mc, 0, i)
        l.addLayout(kpi_row)

        # ── LEAK ANALYSIS ─────────────────────────────────────────────
        leak_card = QFrame()
        leak_card.setObjectName("Card")
        lc_l = QVBoxLayout(leak_card)
        lc_l.setContentsMargins(20, 18, 20, 20)
        lc_l.setSpacing(10)
        lc_l.addWidget(self._section_head("LEAK ANALİZİ  ·  EV KAYBI SIRALI"))
        for leak in report.get("leaks", []):
            lc_l.addWidget(self._leak_row(leak))
        l.addWidget(leak_card)

        # ── POSITION BREAKDOWN ────────────────────────────────────────
        pos_card = QFrame()
        pos_card.setObjectName("Card")
        pc_l = QVBoxLayout(pos_card)
        pc_l.setContentsMargins(20, 18, 20, 18)
        pc_l.setSpacing(6)
        pc_l.addWidget(self._section_head("POZİSYON DETAYI"))
        hdr = QLabel(f"{'POZ':<8}{'EL':<7}{'VPIP%':<9}{'PFR%':<9}{'BB/100'}")
        hdr.setStyleSheet(
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:10px; color:#5a5e54;"
        )
        pc_l.addWidget(hdr)
        for pos, ps in sorted(report.get("position_stats", {}).items()):
            bb100_pos = ps.get("bb_per_100", 0)
            c = "#5ad17a" if bb100_pos > 0 else "#e87474"
            row_lbl = QLabel(
                f"{pos:<8}{ps['hands']:<7}{ps['vpip_pct']:<9.1f}"
                f"{ps['pfr_pct']:<9.1f}{bb100_pos:+.1f}"
            )
            row_lbl.setStyleSheet(
                f"font-family:'JetBrains Mono',Menlo,monospace; font-size:12px; color:{c};"
            )
            pc_l.addWidget(row_lbl)
        l.addWidget(pos_card)

        # ── TURNUVA GEÇMİŞİ ──────────────────────────────────────────
        try:
            history = get_tournament_history(limit=15)
        except Exception:
            history = []

        if history:
            hist_card = QFrame()
            hist_card.setObjectName("Card")
            hi_l = QVBoxLayout(hist_card)
            hi_l.setContentsMargins(20, 18, 20, 18)
            hi_l.setSpacing(6)
            hi_l.addWidget(self._section_head(f"TURNUVA GEÇMİŞİ  ·  son {len(history)} turnuva"))

            # Summary bar above table
            total_played  = len(history)
            total_itm     = sum(1 for h in history if h.get("prize_won", 0) > 0)
            total_profit  = sum(h.get("profit", 0) for h in history)
            total_invested = sum(h.get("buyin", 0) for h in history)
            overall_roi   = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
            itm_pct       = round(100 * total_itm / max(total_played, 1), 1)
            roi_c = "#5ad17a" if overall_roi >= 0 else "#e87474"

            summary = QLabel(
                f"Toplam: {total_played} turnuva  ·  "
                f"ITM: {total_itm} ({itm_pct}%)  ·  "
                f"Net P&L: {total_profit:+.2f}$  ·  "
                f"Genel ROI: {overall_roi:+.1f}%"
            )
            summary.setStyleSheet(
                f"font-family:'JetBrains Mono',Menlo,monospace; font-size:11px; "
                f"font-weight:700; color:{roi_c}; padding: 6px 0 10px 0;"
            )
            hi_l.addWidget(summary)

            # Column header
            hdr2 = QLabel(
                f"{'#':<4}{'EVENT':<22}{'FIELD':<8}{'FİNİŞ':<10}"
                f"{'ÖDÜL':>8}{'ROI':>8}{'EL':>6}"
            )
            hdr2.setStyleSheet(
                "font-family:'JetBrains Mono',Menlo,monospace; "
                "font-size:10px; color:#5a5e54;"
            )
            hi_l.addWidget(hdr2)

            sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
            sep2.setStyleSheet("background:#23271f; border:none; max-height:1px;")
            hi_l.addWidget(sep2)

            for idx, h in enumerate(history, 1):
                h_finish  = h.get("finish_position") or h.get("field_size", 0)
                h_field   = h.get("field_size", 0)
                h_prize   = h.get("prize_won", 0)
                h_profit  = h.get("profit", 0)
                h_buyin   = h.get("buyin", 0)
                h_roi     = (h_profit / h_buyin * 100) if h_buyin > 0 else 0.0
                h_hands   = h.get("hands_played", 0)
                h_name    = (h.get("name") or "—")[:20]
                h_ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
                h_fin_str = h_ordinals.get(h_finish, f"{h_finish}th")
                row_color = "#5ad17a" if h_prize > 0 else "#898d80"
                if h_finish == 1:
                    row_color = "#f5d76e"

                row_lbl = QLabel(
                    f"{idx:<4}{h_name:<22}{h_field:<8}{h_fin_str+'/' + str(h_field):<10}"
                    f"${h_prize:>6,.0f}{h_roi:>+7.0f}%{h_hands:>6}"
                )
                row_lbl.setStyleSheet(
                    f"font-family:'JetBrains Mono',Menlo,monospace; "
                    f"font-size:11px; color:{row_color}; padding: 2px 0;"
                )
                hi_l.addWidget(row_lbl)

            l.addWidget(hist_card)

        # ── BUTTONS ───────────────────────────────────────────────────
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet("background: #23271f; border: none; max-height: 1px;")
        l.addWidget(sep3)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        again_btn = QPushButton("▶  YENİ TURNUVA")
        again_btn.setObjectName("PrimaryButton")
        again_btn.setMinimumHeight(44)
        again_btn.clicked.connect(self._build_setup)
        ask_coach_btn = QPushButton("AI COACH'A SOR")
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
        field_size = self.mtt_field.field_size if self.mtt_field else self.tournament.config.field_size
        prize_pool = self.mtt_field.prize_pool  if self.mtt_field else self.tournament.config.prize_pool
        finish     = self.tournament.state.finish_position
        prize      = self.tournament.state.prize_won
        profit     = prize - self.tournament.config.buyin
        roi        = (profit / max(self.tournament.config.buyin, 1)) * 100
        lines = [
            f"Turnuva bitti: {self.tournament.config.name}",
            f"Sonuç: {finish}/{field_size} · Ödül ${prize:.2f} · ROI {roi:+.1f}% · Net {profit:+.2f}$",
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
