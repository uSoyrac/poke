"""Play Session — cash game, MTT ve Sit & Go drill modu.

Format seçici (CASH GAME / MTT / SIT & GO) ile farklı yapılar aynı
tab sistemi içinde oynanabilir. Her format kendi preset'leri ve ayarları
ile gelir; FieldPicker tüm formatlarda ortaktır.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
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
from app.core.live_hud import LiveHUD
from app.engine.game_loop import PokerGame, HandResult
from app.engine.hand_state import ActionType, Street
from app.engine.bot_brain import BOT_ARCHETYPES
from app.simulator.tournament_runner import Tournament, TournamentConfig
from app.ui.components.card_view import CardView, CardBackView, CardPlaceholder
from app.ui.components.field_picker import FieldPicker
from app.ui.components.gto_range_dialog import show_gto_dialog
from app.ui.components.gto_range_widget import GTORangeWidget, GTODecisionReveal
from app.ui.components.metric_card import MetricCard
from app.ui.components.poker_table import LivePokerTable, SeatState, seats_from_hand


def _format_actions_for_coach(actions: list, hero_idx: int = 0) -> str:
    """Format hand actions street-by-street for Gemini context."""
    from app.engine.hand_state import Street
    street_names = {
        Street.PREFLOP: "Preflop",
        Street.FLOP: "Flop",
        Street.TURN: "Turn",
        Street.RIVER: "River",
    }
    by_street: dict[str, list[str]] = {}
    for a in actions:
        s = street_names.get(a.street, str(a.street))
        actor = "Hero" if a.player_idx == hero_idx else f"Villain{a.player_idx}"
        if s not in by_street:
            by_street[s] = []
        by_street[s].append(f"{actor}: {a}")
    return "  |  ".join(f"{s}: {', '.join(acts)}" for s, acts in by_street.items()) or "Bilgi yok"


# ── Format toggle styles ───────────────────────────────────────────────
_FMT_ACTIVE = (
    "QPushButton { background:#11241a; border:1px solid #5ad17a; color:#5ad17a; "
    "font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; "
    "letter-spacing:1.6px; padding:7px 20px; }"
)
_FMT_INACTIVE = (
    "QPushButton { background:#0f1210; border:1px solid #23271f; color:#5a5e54; "
    "font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; "
    "letter-spacing:1.6px; padding:7px 20px; }"
    "QPushButton:hover { color:#c8cabe; border-color:#3a3f30; }"
)


class PlaySessionScreen(QWidget):
    coach_message = Signal(str)
    hand_completed = Signal(dict)   # rich hand data for Gemini

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.game: PokerGame | None = None
        self.tournament: Tournament | None = None
        self.live_hud = LiveHUD()
        self._format: str = "cash"   # "cash" | "mtt" | "sng"
        self._in_mtt: bool = False   # True while MTT/SNG hand is running
        self._shortcuts: list = []

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

    def _clear_shortcuts(self):
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

    # ── SETUP ─────────────────────────────────────────────────────

    def _build_setup(self):
        self._clear_stack()
        self._in_mtt = False

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
        self._title_label = _big_title("Cash game — drill mode")
        sub = QLabel("Format seç, alan oluştur, oyna. Her el DB'ye kaydedilir ve sızıntı analizine gider.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        l.addWidget(num)
        l.addWidget(self._title_label)
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

        # ── FORMAT TOGGLE ──────────────────────────────────────────
        fmt_hdr = QHBoxLayout()
        fmt_hdr.setSpacing(0)
        self._format_btns: dict[str, QPushButton] = {}
        for key, label in [("cash", "CASH GAME"), ("mtt", "MTT"), ("sng", "SIT && GO")]:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(_FMT_ACTIVE if key == self._format else _FMT_INACTIVE)
            b.clicked.connect(lambda _, k=key: self._switch_format(k))
            self._format_btns[key] = b
            fmt_hdr.addWidget(b)
        fmt_hdr.addStretch(1)
        c_l.addLayout(fmt_hdr)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("background: #1e2420; border: none; max-height: 1px;")
        c_l.addWidget(sep2)

        # ── FORMAT-SPECIFIC PANELS (stacked) ──────────────────────
        self._fmt_stack = QStackedWidget()

        # ── Panel 0: CASH ──────────────────────────────────────────
        cash_w = QWidget()
        cash_g = QGridLayout(cash_w)
        cash_g.setContentsMargins(0, 4, 0, 4)
        cash_g.setSpacing(14)

        self.stack_combo = QComboBox()
        self.stack_combo.addItems(["20bb (Short)", "50bb", "100bb", "150bb", "200bb (Deep)"])
        self.stack_combo.setCurrentIndex(2)
        cash_g.addWidget(self._label("EFFECTIVE STACK"), 0, 0)
        cash_g.addWidget(self.stack_combo, 1, 0)

        self.cash_preset_combo = QComboBox()
        self.cash_preset_combo.addItems(list(self._CASH_PRESETS.keys()) + ["Custom"])
        for key, tip in self._CASH_PRESET_TIPS.items():
            idx = self.cash_preset_combo.findText(key)
            if idx >= 0:
                self.cash_preset_combo.setItemData(idx, tip, Qt.ToolTipRole)
        self.cash_preset_combo.currentTextChanged.connect(self._apply_preset)
        cash_g.addWidget(self._label("QUICK PRESET"), 0, 1)
        cash_g.addWidget(self.cash_preset_combo, 1, 1)

        # Ante — default 0 (no ante), range 0–10 bb, step 0.25
        self.cash_ante_spin = QDoubleSpinBox()
        self.cash_ante_spin.setRange(0.0, 10.0)
        self.cash_ante_spin.setSingleStep(0.25)
        self.cash_ante_spin.setValue(0.0)
        self.cash_ante_spin.setDecimals(2)
        self.cash_ante_spin.setSuffix(" bb")
        self.cash_ante_spin.setToolTip(
            "Per-player ante posted before the blinds each hand (0 = no ante). "
            "Common live values: 1bb big-blind ante."
        )
        cash_g.addWidget(self._label("ANTE (per player)"), 0, 2)
        cash_g.addWidget(self.cash_ante_spin, 1, 2)
        self._fmt_stack.addWidget(cash_w)   # idx 0

        # ── Panel 1: MTT ──────────────────────────────────────────
        mtt_w = QWidget()
        mtt_g = QGridLayout(mtt_w)
        mtt_g.setContentsMargins(0, 4, 0, 4)
        mtt_g.setSpacing(14)

        self.mtt_chips_combo = QComboBox()
        for label, chips in [("1,500 chips", 1500), ("3,000 chips", 3000),
                              ("5,000 chips", 5000), ("10,000 chips", 10000),
                              ("20,000 chips", 20000), ("50,000 chips", 50000)]:
            self.mtt_chips_combo.addItem(label, chips)
        self.mtt_chips_combo.setCurrentIndex(2)  # 5,000 default
        mtt_g.addWidget(self._label("STARTING CHIPS"), 0, 0)
        mtt_g.addWidget(self.mtt_chips_combo, 1, 0)

        self.mtt_structure_combo = QComboBox()
        self.mtt_structure_combo.addItems(["regular", "turbo", "hyper"])
        self.mtt_structure_combo.setItemData(0, "Yavaş yükselen blindler — derin stack oyunu", Qt.ToolTipRole)
        self.mtt_structure_combo.setItemData(1, "Hızlı yapı — daha az el, daha fazla push/fold", Qt.ToolTipRole)
        self.mtt_structure_combo.setItemData(2, "Çok hızlı — neredeyse her el push/fold stack", Qt.ToolTipRole)
        mtt_g.addWidget(self._label("BLIND STRUCTURE"), 0, 1)
        mtt_g.addWidget(self.mtt_structure_combo, 1, 1)

        self.mtt_type_combo = QComboBox()
        self.mtt_type_combo.addItems(["Standard MTT", "Bounty / PKO", "Deepstack", "Hyper Turbo"])
        mtt_g.addWidget(self._label("FORMAT TYPE"), 0, 2)
        mtt_g.addWidget(self.mtt_type_combo, 1, 2)

        self.mtt_preset_combo = QComboBox()
        self.mtt_preset_combo.addItems(list(self._MTT_PRESETS.keys()) + ["Custom"])
        self.mtt_preset_combo.currentTextChanged.connect(self._apply_preset)
        mtt_g.addWidget(self._label("FIELD PRESET"), 2, 0)
        mtt_g.addWidget(self.mtt_preset_combo, 3, 0, 1, 2)
        self._fmt_stack.addWidget(mtt_w)   # idx 1

        # ── Panel 2: SIT & GO ──────────────────────────────────────
        sng_w = QWidget()
        sng_g = QGridLayout(sng_w)
        sng_g.setContentsMargins(0, 4, 0, 4)
        sng_g.setSpacing(14)

        self.sng_format_combo = QComboBox()
        self.sng_format_combo.addItems(["9-man", "6-max", "Heads-Up"])
        self.sng_format_combo.currentTextChanged.connect(self._sng_format_changed)
        sng_g.addWidget(self._label("FORMAT"), 0, 0)
        sng_g.addWidget(self.sng_format_combo, 1, 0)

        self.sng_structure_combo = QComboBox()
        self.sng_structure_combo.addItems(["turbo", "hyper"])
        sng_g.addWidget(self._label("BLIND STRUCTURE"), 0, 1)
        sng_g.addWidget(self.sng_structure_combo, 1, 1)

        self.sng_chips_combo = QComboBox()
        for label, chips in [("1,500 chips", 1500), ("3,000 chips", 3000), ("5,000 chips", 5000)]:
            self.sng_chips_combo.addItem(label, chips)
        self.sng_chips_combo.setCurrentIndex(1)  # 3,000 default
        sng_g.addWidget(self._label("STARTING CHIPS"), 0, 2)
        sng_g.addWidget(self.sng_chips_combo, 1, 2)

        self.sng_preset_combo = QComboBox()
        self.sng_preset_combo.addItems(list(self._SNG_PRESETS.keys()) + ["Custom"])
        self.sng_preset_combo.currentTextChanged.connect(self._apply_preset)
        sng_g.addWidget(self._label("FIELD PRESET"), 2, 0)
        sng_g.addWidget(self.sng_preset_combo, 3, 0, 1, 2)
        self._fmt_stack.addWidget(sng_w)   # idx 2

        self._fmt_stack.setCurrentIndex({"cash": 0, "mtt": 1, "sng": 2}[self._format])
        c_l.addWidget(self._fmt_stack)

        # ── SHARED: FieldPicker ────────────────────────────────────
        c_l.addSpacing(6)
        self.field_picker = FieldPicker(default_bots=5)
        c_l.addWidget(self.field_picker)

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

    # ── PRESETS ───────────────────────────────────────────────────

    _CASH_PRESETS = {
        "Karma 5-bot (Random)": ["Random (Karma)"] * 5,
        "TAG-heavy":            ["TAG", "TAG", "Reg", "TAG", "Tight Passive"],
        "LAG-heavy":            ["LAG", "Maniac", "LAG", "Aggro Fish", "LAG"],
        "Recreational (Fishy)": ["Fish", "Calling Station", "Aggro Fish", "Fish", "Tight Passive"],
        "Tough Regs":           ["TAG", "Reg", "Shark", "TAG", "Reg"],
        "Solver Field":         ["Solver Bot", "GTO Expert", "Solver Bot", "GTO Expert", "Shark"],
        "HU (1v1)":             ["LAG"],
        "6-max Balanced":       ["TAG", "Reg", "LAG", "Fish", "Tight Passive"],
        "9-max Deep":           ["TAG", "Reg", "LAG", "Fish", "Tight Passive", "Reg", "TAG", "Fish"],
    }
    _CASH_PRESET_TIPS = {
        "Karma 5-bot (Random)": "5 oyuncu, hepsi her elde KARMA havuzundan random tarz",
        "TAG-heavy":            "Tight Aggressive ağırlıklı — disiplinli rakipler",
        "LAG-heavy":            "Loose Aggressive — çok agresif ve geniş range",
        "Recreational (Fishy)": "Fish + Stations — softest field, geniş edge",
        "Tough Regs":           "TAG + Reg + Shark — derin postflop oyun",
        "Solver Field":         "Solver Bot + GTO Expert — en zor field",
        "HU (1v1)":             "Heads-up: sadece 1 rakip (LAG)",
        "6-max Balanced":       "6-max dengeli alan — gerçekçi mid-stakes hissi",
        "9-max Deep":           "9-max 200bb derin stack — postflop yeteneği şart",
    }

    _MTT_PRESETS = {
        "Full Ring Random":      ["Random (Karma)"] * 8,
        "Recreational MTT":      ["Fish", "Calling Station", "Aggro Fish", "Tight Passive",
                                  "Fish", "Maniac", "LAG", "Reg"],
        "Reg-heavy MTT":         ["TAG", "Reg", "LAG", "Reg", "Shark", "TAG", "Reg", "Reg"],
        "Bounty Hunter Field":   ["LAG", "Maniac", "Aggro Fish", "LAG", "Fish",
                                  "LAG", "Maniac", "LAG"],
        "Online MTT (Balanced)": ["TAG", "Reg", "LAG", "Fish", "Tight Passive",
                                  "Reg", "Aggro Fish", "TAG"],
        "High Roller Field":     ["Shark", "Solver Bot", "GTO Expert", "Shark",
                                  "TAG", "Solver Bot", "Reg", "Shark"],
    }

    _SNG_PRESETS = {
        "9-man Random":       ["Random (Karma)"] * 8,
        "9-man Tough":        ["TAG", "Reg", "Shark", "TAG", "Reg", "LAG", "Tight Passive", "TAG"],
        "6-max Hyper Random": ["Random (Karma)"] * 5,
        "6-max Balanced":     ["TAG", "Reg", "LAG", "Fish", "Tight Passive"],
        "HU Turbo":           ["LAG"],
    }

    # Backward-compat alias (used by old test code that checks _PRESETS)
    _PRESETS = _CASH_PRESETS

    def _switch_format(self, key: str) -> None:
        self._format = key
        idx = {"cash": 0, "mtt": 1, "sng": 2}[key]
        self._fmt_stack.setCurrentIndex(idx)
        for k, b in self._format_btns.items():
            b.setStyleSheet(_FMT_ACTIVE if k == key else _FMT_INACTIVE)
        # Update page title
        titles = {
            "cash": "Cash game — drill mode",
            "mtt":  "MTT — real chips, real blinds",
            "sng":  "Sit & Go — quick tournament",
        }
        if hasattr(self, "_title_label"):
            self._title_label.setText(titles[key])
        # SNG: auto-size field to match format selection
        if key == "sng":
            self._sng_format_changed(self.sng_format_combo.currentText())

    def _sng_format_changed(self, fmt: str) -> None:
        """Auto-populate FieldPicker when SNG format changes."""
        sizes = {"9-man": 8, "6-max": 5, "Heads-Up": 1}
        n = sizes.get(fmt, 8)
        if hasattr(self, "field_picker"):
            self.field_picker.set_composition(["Random (Karma)"] * n)

    def _apply_preset(self, name: str) -> None:
        if self._format == "cash":
            comp = self._CASH_PRESETS.get(name)
        elif self._format == "mtt":
            comp = self._MTT_PRESETS.get(name)
        else:
            comp = self._SNG_PRESETS.get(name)
        if comp and hasattr(self, "field_picker"):
            self.field_picker.set_composition(comp)

    # ── START (routes by format) ──────────────────────────────────

    def _start(self):
        if self._format == "cash":
            self._start_cash()
        else:
            self._start_mtt()

    def _start_cash(self):
        stack_map = {
            "20bb (Short)": 20, "50bb": 50, "100bb": 100,
            "150bb": 150, "200bb (Deep)": 200,
        }
        stack_bb = stack_map.get(self.stack_combo.currentText(), 100)
        archetypes = self.field_picker.get_archetypes()
        num = len(archetypes) + 1
        ante_bb = self.cash_ante_spin.value()

        self.game = PokerGame(
            num_players=num,
            starting_stack=float(stack_bb),
            small_blind=0.5, big_blind=1.0,
            ante=ante_bb,
            hero_seat=0,
            bot_archetypes=archetypes,
            paced_bots=True,
        )
        self._cash_ante_bb = ante_bb
        self.live_hud.reset(num)
        self._build_play()
        composition = ", ".join(archetypes)
        ante_str = f" · Ante {ante_bb:.2g}bb" if ante_bb > 0 else ""
        self.coach_message.emit(
            f"Yeni session: {num}-max, {stack_bb}bb{ante_str} · Field: {composition}. İyi eller."
        )

    def _start_mtt(self):
        archetypes = self.field_picker.get_archetypes()
        size = len(archetypes) + 1

        if self._format == "mtt":
            starting_chips = self.mtt_chips_combo.currentData() or 5000
            structure = self.mtt_structure_combo.currentText()
            fmt_type = self.mtt_type_combo.currentText()
            hands_per_level = 5 if structure == "hyper" else 8 if structure == "turbo" else 12
            name = f"{fmt_type} ({size}-handed, {structure})"
        else:  # sng
            starting_chips = self.sng_chips_combo.currentData() or 3000
            structure = self.sng_structure_combo.currentText()
            sng_fmt = self.sng_format_combo.currentText()
            hands_per_level = 4 if structure == "hyper" else 6
            name = f"SNG {sng_fmt} {structure.title()}"

        payout_key = "Heads-Up" if size == 2 else ("6-max" if size <= 6 else "9-max")

        config = TournamentConfig(
            name=name,
            field_size=size,
            starting_chips=starting_chips,
            structure=structure,
            buyin=0.0,
            payout_key=payout_key,
            hands_per_level=hands_per_level,
            bot_mix=archetypes,
        )
        self.tournament = Tournament(config)
        self.tournament.game.paced_bots = True
        self.live_hud.reset(size)
        self._build_mtt_play()

        comp_str = ", ".join(archetypes[:5]) + ("…" if len(archetypes) > 5 else "")
        self.coach_message.emit(
            f"Yeni {self._format.upper()}: {name} · {size} oyuncu · "
            f"{starting_chips:,} chips · Field: {comp_str}"
        )
        self._deal_next_mtt()

    # ── CASH PLAY UI ──────────────────────────────────────────────

    def _build_play(self):
        self._clear_stack()
        self._clear_shortcuts()
        self._in_mtt = False

        page = QFrame()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        # Stats bar — wrapped in horizontal scroll so it never clips at narrow widths
        stats_bar = QFrame()
        stats_bar.setStyleSheet("background: #131613;")
        sb_l = QHBoxLayout(stats_bar)
        sb_l.setContentsMargins(16, 8, 16, 8)
        sb_l.setSpacing(0)

        self.stat_hands = MetricCard("HANDS", "0", "played")
        self.stat_profit = MetricCard("PROFIT", "+0bb", "session", accent="Green")
        self.stat_vpip = MetricCard("VPIP", "—", "voluntary")
        self.stat_winrate = MetricCard("WIN RATE", "—", "won", accent="Green")
        for w in (self.stat_hands, self.stat_profit, self.stat_vpip, self.stat_winrate):
            sb_l.addWidget(w, 1)
        # Blinds / ante meta chip — right side of stats bar
        ante_bb = getattr(self, "_cash_ante_bb", 0.0)
        blind_txt = "SB 0.5 / BB 1"
        if ante_bb > 0:
            blind_txt += f" / ANTE {ante_bb:.2g}"
        self._blind_meta = QLabel(blind_txt)
        self._blind_meta.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:10px; "
            "letter-spacing:1.2px; color:#5a5e54; padding:4px 10px; "
            "border:1px solid #23271f; background:#0f1210;"
        )
        sb_l.addStretch(1)
        sb_l.addWidget(self._blind_meta)

        stats_scroll = QScrollArea()
        stats_scroll.setWidget(stats_bar)
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setFrameShape(QFrame.NoFrame)
        stats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        stats_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        stats_scroll.setMaximumHeight(82)
        stats_scroll.setStyleSheet(
            "QScrollArea { background:#131613; border:1px solid #23271f; "
            "border-left:none; border-right:none; }"
        )
        pl.addWidget(stats_scroll)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 18, 22, 22)
        cl.setSpacing(16)

        self.table = LivePokerTable()
        self.table.set_unit("bb")
        self.table.setMinimumHeight(380)
        cl.addWidget(self.table)

        self.feedback = QLabel("Dealing first hand...")
        self.feedback.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; color: #898d80; padding: 6px 0;"
        )
        self.feedback.setWordWrap(True)
        cl.addWidget(self.feedback)

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

        ctrl = QHBoxLayout()
        next_btn = QPushButton("DEAL NEXT HAND  ⎵")
        next_btn.setObjectName("PrimaryButton")
        next_btn.setToolTip("Deal next hand (Space)")
        next_btn.clicked.connect(self._deal_next)
        self.next_btn = next_btn
        next_btn.hide()

        self.review_btn = QPushButton("REVIEW LAST")
        self.review_btn.setObjectName("GhostButton")
        self.review_btn.clicked.connect(self._review_last)
        self.review_btn.setEnabled(False)
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
        deck_v = QVBoxLayout(deck)
        deck_v.setContentsMargins(22, 8, 22, 12)
        deck_v.setSpacing(6)

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

        # El-sonu GTO reveal — oyun sırasında gizli, el bitince optimal karar
        self.gto_reveal = GTODecisionReveal()
        deck_v.addWidget(self.gto_reveal)

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

        # Deck bottom row: sizing controls + action buttons
        # Wrapped in a horizontal QScrollArea so narrow windows never clip buttons
        dl_container = QWidget()
        dl_container.setStyleSheet("background:transparent;")
        dl = QHBoxLayout(dl_container)
        dl.setSpacing(12)
        dl.setContentsMargins(0, 0, 0, 0)

        sizing = QVBoxLayout()
        sizing.setSpacing(3)
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
            b.setMinimumWidth(64)   # was 150 — shrinks gracefully at narrow widths
            b.setMinimumHeight(38)  # was 48
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            acts.addWidget(b, 1)
        dl.addLayout(acts, 4)

        dl_scroll = QScrollArea()
        dl_scroll.setWidget(dl_container)
        dl_scroll.setWidgetResizable(True)
        dl_scroll.setFrameShape(QFrame.NoFrame)
        dl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        dl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dl_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        deck_v.addWidget(dl_scroll, 1)
        pl.addWidget(deck)

        self.stack_layout.addWidget(page)

        # Register shortcuts — stored so we can clear on mode switch
        self._shortcuts = [
            QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space_pressed),
            QShortcut(QKeySequence("F"), self, activated=lambda: self._key_action("F")),
            QShortcut(QKeySequence("C"), self, activated=lambda: self._key_action("C")),
            QShortcut(QKeySequence("R"), self, activated=lambda: self._key_action("R")),
            QShortcut(QKeySequence("A"), self, activated=lambda: self._key_action("A")),
            QShortcut(QKeySequence("G"), self, activated=self._show_gto_popup),
        ]

        # Start game timer (must happen after _build_play so buttons exist)
        self._bot_timer = QTimer(self)
        self._bot_timer.setInterval(450)
        self._bot_timer.timeout.connect(self._tick_bot)
        self._deal_next()

    def _sect(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setObjectName("TLabel")
        return l

    # ── MTT PLAY UI ───────────────────────────────────────────────

    def _build_mtt_play(self):
        self._clear_stack()
        self._clear_shortcuts()
        self._in_mtt = True

        page = QFrame()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)

        # ── META BAR ──────────────────────────────────────────────
        meta_bar = QFrame()
        meta_bar.setStyleSheet(
            "background: #131613; border-bottom: 1px solid #23271f;"
        )
        meta_l = QHBoxLayout(meta_bar)
        meta_l.setContentsMargins(22, 0, 22, 0)
        meta_l.setSpacing(0)

        self.mtt_meta: dict[str, MetricCard] = {}
        for key, label, sub in [
            ("event",   "EVENT",   "name"),
            ("level",   "LEVEL",   "blinds"),
            ("players", "PLAYERS", "alive"),
            ("hero",    "MY CHIPS","stack"),
            ("avg",     "AVG",     "chips"),
            ("next",    "NEXT LVL","hands"),
        ]:
            mc = MetricCard(label, "—", sub)
            self.mtt_meta[key] = mc
            meta_l.addWidget(mc, 1)

        # END MTT button
        end_mtt_btn = QPushButton("✕  END MTT")
        end_mtt_btn.setObjectName("GhostButton")
        end_mtt_btn.setToolTip("Bu turnuvayı bitir ve setup'a dön (Esc)")
        end_mtt_btn.clicked.connect(self._end_mtt)
        end_mtt_btn.setMinimumHeight(34)
        meta_l.addWidget(end_mtt_btn)
        pl.addWidget(meta_bar)

        # ── SCROLL BODY ───────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 18, 22, 22)
        cl.setSpacing(16)

        self.mtt_table = LivePokerTable()
        self.mtt_table.set_unit("bb")   # tournament simulator displays in bb too
        self.mtt_table.setMinimumHeight(380)
        cl.addWidget(self.mtt_table)

        self.mtt_feedback = QLabel("Dealing first hand...")
        self.mtt_feedback.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 12px; color: #898d80; padding: 6px 0;"
        )
        self.mtt_feedback.setWordWrap(True)
        cl.addWidget(self.mtt_feedback)

        hist = QFrame()
        hist.setObjectName("Card")
        hist_l = QVBoxLayout(hist)
        hist_l.setContentsMargins(16, 14, 16, 14)
        hist_l.setSpacing(6)
        hist_l.addWidget(self._sect("HAND HISTORY"))
        self.mtt_history_layout = QVBoxLayout()
        self.mtt_history_layout.setSpacing(2)
        hist_l.addLayout(self.mtt_history_layout)
        cl.addWidget(hist)

        ctrl = QHBoxLayout()
        self.mtt_next_btn = QPushButton("DEAL NEXT HAND  ⎵")
        self.mtt_next_btn.setObjectName("PrimaryButton")
        self.mtt_next_btn.setMinimumHeight(38)
        self.mtt_next_btn.clicked.connect(self._deal_next_mtt)
        self.mtt_next_btn.hide()
        ctrl.addWidget(self.mtt_next_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        cl.addStretch(1)
        pl.addWidget(scroll, 1)

        # ── ACTION DECK (shared style with cash) ──────────────────
        deck = QFrame()
        deck.setStyleSheet("background: #0f1210; border-top: 2px solid #23271f;")
        deck_v = QVBoxLayout(deck)
        deck_v.setContentsMargins(22, 8, 22, 12)
        deck_v.setSpacing(6)

        self.mtt_to_call_banner = QLabel("")
        self.mtt_to_call_banner.setAlignment(Qt.AlignCenter)
        self.mtt_to_call_banner.setStyleSheet(
            "font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1.4px; color: #5ad17a; "
            "padding: 4px 12px; border: 1px solid #2a4a30; background: #0f1d11;"
        )
        self.mtt_to_call_banner.hide()
        banner_row = QHBoxLayout()
        banner_row.addStretch(1); banner_row.addWidget(self.mtt_to_call_banner); banner_row.addStretch(1)
        deck_v.addLayout(banner_row)

        # El-sonu GTO reveal (turnuva) — oyun sırasında gizli
        self.mtt_gto_reveal = GTODecisionReveal()
        deck_v.addWidget(self.mtt_gto_reveal)

        # MTT deck row — same horizontal-scroll pattern as cash game
        mtt_dl_container = QWidget()
        mtt_dl_container.setStyleSheet("background:transparent;")
        dl = QHBoxLayout(mtt_dl_container)
        dl.setSpacing(12)
        dl.setContentsMargins(0, 0, 0, 0)

        sizing = QVBoxLayout()
        sizing.setSpacing(3)
        sl = QLabel("RAISE SIZE")
        sl.setObjectName("TLabel")
        sizing.addWidget(sl)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(0)
        for pct, label in [(33, "33%"), (50, "50%"), (66, "66%"), (75, "75%"), (100, "POT"), (150, "1.5x")]:
            b = QPushButton(label)
            b.setObjectName("PresetButton")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, p=pct: self.mtt_size_slider.setValue(p))
            preset_row.addWidget(b)
        sizing.addLayout(preset_row)

        self.mtt_size_slider = QSlider(Qt.Horizontal)
        self.mtt_size_slider.setRange(1, 300)
        self.mtt_size_slider.setValue(66)
        self.mtt_size_slider.valueChanged.connect(self._refresh_mtt_size)
        sizing.addWidget(self.mtt_size_slider)
        self.mtt_size_label = QLabel("—")
        self.mtt_size_label.setStyleSheet("font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px;")
        sizing.addWidget(self.mtt_size_label)
        dl.addLayout(sizing, 2)

        acts = QHBoxLayout()
        acts.setSpacing(6)
        self.mtt_fold_btn  = QPushButton("FOLD");   self.mtt_fold_btn.setObjectName("ActionFold")
        self.mtt_check_btn = QPushButton("CHECK");  self.mtt_check_btn.setObjectName("ActionCheck")
        self.mtt_call_btn  = QPushButton("CALL");   self.mtt_call_btn.setObjectName("ActionCall")
        self.mtt_raise_btn = QPushButton("RAISE");  self.mtt_raise_btn.setObjectName("ActionRaise")
        self.mtt_allin_btn = QPushButton("ALL-IN"); self.mtt_allin_btn.setObjectName("ActionAllin")

        self.mtt_fold_btn.clicked.connect(lambda: self._hero_action_mtt(ActionType.FOLD))
        self.mtt_check_btn.clicked.connect(lambda: self._hero_action_mtt(ActionType.CHECK))
        self.mtt_call_btn.clicked.connect(lambda: self._hero_action_mtt(ActionType.CALL))
        self.mtt_raise_btn.clicked.connect(lambda: self._hero_action_mtt(ActionType.RAISE))
        self.mtt_allin_btn.clicked.connect(lambda: self._hero_action_mtt(ActionType.ALL_IN))

        for b in (self.mtt_fold_btn, self.mtt_check_btn, self.mtt_call_btn,
                  self.mtt_raise_btn, self.mtt_allin_btn):
            b.setMinimumWidth(64)   # was 150
            b.setMinimumHeight(38)  # was 48
            b.setCursor(Qt.PointingHandCursor)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            acts.addWidget(b, 1)
        dl.addLayout(acts, 4)

        mtt_dl_scroll = QScrollArea()
        mtt_dl_scroll.setWidget(mtt_dl_container)
        mtt_dl_scroll.setWidgetResizable(True)
        mtt_dl_scroll.setFrameShape(QFrame.NoFrame)
        mtt_dl_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        mtt_dl_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        mtt_dl_scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        deck_v.addWidget(mtt_dl_scroll, 1)
        pl.addWidget(deck)

        self.stack_layout.addWidget(page)

        # MTT shortcuts
        self._shortcuts = [
            QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._space_pressed_mtt),
            QShortcut(QKeySequence("F"), self, activated=lambda: self._key_action_mtt("F")),
            QShortcut(QKeySequence("C"), self, activated=lambda: self._key_action_mtt("C")),
            QShortcut(QKeySequence("R"), self, activated=lambda: self._key_action_mtt("R")),
            QShortcut(QKeySequence("A"), self, activated=lambda: self._key_action_mtt("A")),
            QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self._end_mtt),
        ]

        # Bot timer for MTT
        self._mtt_bot_timer = QTimer(self)
        self._mtt_bot_timer.setInterval(450)
        self._mtt_bot_timer.timeout.connect(self._tick_bot_mtt)

    # ── CASH GAME LOOP ────────────────────────────────────────────

    def _deal_next(self):
        if not self.game:
            return
        if self.next_btn:
            self.next_btn.hide()
        self._decision_log = []
        self._captured_keys = set()
        if hasattr(self, "gto_reveal"):
            self.gto_reveal.hide_panel()
        self.game.start_hand()
        self._refresh()
        if not self.game.is_waiting_for_hero and not self.game.current_hand.is_complete:
            self._bot_timer.start()

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
        self._record_hero_decision(action_type, amount)
        self.game.hero_act(action_type, amount)
        self._refresh()
        if hand.is_complete:
            self._on_complete()
        else:
            self._bot_timer.start()

    def _tick_bot(self):
        if not self.game or not self.game.current_hand:
            self._bot_timer.stop()
            return
        keep_going = self.game.step_action()
        self._refresh()
        if not keep_going:
            self._bot_timer.stop()
            if self.game.current_hand.is_complete:
                self._on_complete()

    def _space_pressed(self):
        if hasattr(self, "next_btn") and self.next_btn and self.next_btn.isVisible():
            self._deal_next()
            return
        # Fold ettiysen el bitmeyi bekleme — botları anında ileri sar.
        if self._hero_folded_midhand():
            _real_xp = bool(getattr(self.state, "real_experience", False)) if self.state else False
            if _real_xp:
                # Real Experience: hızlı-ileri sar + notlandırılmış reveal göster,
                # ama sonraki ele GEÇME — kullanıcı karneyi görsün, tekrar SPACE.
                self._fast_forward_then_next(None)
            else:
                # Eğitim modu: fold → anında sonraki el (hızlı, #41).
                self._fast_forward_then_next(self._deal_next)

    def apply_experience_mode(self, real: bool) -> None:
        """Real Experience Mode toggle'ı — GTO panel görünürlüğünü tazele."""
        if hasattr(self, "gto_range"):
            self.gto_range.setVisible(not real)
        try:
            self._refresh()
        except Exception:
            pass

    def _hero_folded_midhand(self) -> bool:
        if not self.game or not self.game.current_hand:
            return False
        h = self.game.current_hand
        if h.is_complete or self.game.is_waiting_for_hero:
            return False
        hero = h.hero
        return bool(hero and hero.is_folded)

    def _fast_forward_then_next(self, deal_fn) -> None:
        """Kalan bot aksiyonlarını anında oyna, eli tamamla, sonraki ele geç."""
        if hasattr(self, "_bot_timer"):
            self._bot_timer.stop()
        guard = 0
        while (self.game.current_hand and not self.game.current_hand.is_complete
               and not self.game.is_waiting_for_hero and guard < 400):
            self.game.step_action()
            guard += 1
        if self.game.current_hand and self.game.current_hand.is_complete:
            self._refresh()
            self._on_complete()
        if deal_fn is not None:
            deal_fn()

    def _key_action(self, key: str) -> None:
        if not self.game or not self.game.is_waiting_for_hero:
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

    def _size_amount_bb(self) -> float:
        hand = self.game.current_hand
        hero = hand.hero
        pct = self.size_slider.value() / 100.0
        if hand.street == Street.PREFLOP and hand.pot <= hand.big_blind * 3:
            target = hand.big_blind * (2.0 + pct * 1.5)
        else:
            target = hand.pot * pct
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
        self.size_label.setText(f"{chips:.1f} bb  ·  {pct}% pot")

    def _refresh(self):
        if not self.game or not self.game.current_hand:
            return
        hand = self.game.current_hand
        hero = hand.hero

        action_top = self.game._action_queue[0] if self.game._action_queue else -1
        raw_profiles = self.game.get_bot_profiles()
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
            bot_profiles=merged_profiles,
        )

        _real_xp = bool(getattr(self.state, "real_experience", False)) if self.state else False
        if hasattr(self, "gto_range"):
            # Real Experience Mode: TÜM GTO bağlamı gizli (gerçek deneyim).
            self.gto_range.setVisible(not _real_xp)
        if hasattr(self, "gto_range") and not _real_xp and hero and not hand.is_complete:
            pos = getattr(hero, "position", "") or ""
            hero_hk = None
            if hero.hole_cards and len(hero.hole_cards) >= 2:
                try:
                    from app.engine.bot_brain import hand_key
                    hero_hk = hand_key(hero.hole_cards[0], hero.hole_cards[1])
                except Exception:
                    hero_hk = None
            _adv = None
            try:
                from app.poker.gto_live_advice import live_gto_advice
                _adv = live_gto_advice(hand, hand.hero_idx, mode="cash")
            except Exception:
                _adv = None
            self.gto_range.update_range(
                pos, float(hero.stack),
                game_type="cash",
                hero_hand=hero_hk,
                reveal_action=False,   # eğitim modu: cevabı el sonunda göster
                advice=_adv,           # gerçek senaryo (RFI/vs-RFI/vs-3bet…)
            )

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

        hero_cards = [c.display for c in hero.hole_cards] if (hero and hero.hole_cards) else None
        board = [c.display for c in hand.community]
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
            big_pot=(hand.street == Street.PREFLOP),
            show_opponent_backs=not hand.is_complete,
            to_call=hero_to_call,
        )

        if self.game.is_waiting_for_hero and hero_to_call > 0 and hand.pot > 0:
            pct = int(round(100 * hero_to_call / hand.pot))
            self.to_call_banner.setText(f"TO CALL  {hero_to_call:.1f} bb  ·  {pct}% POT")
            self.to_call_banner.show()
        else:
            self.to_call_banner.hide()

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
        for b in (self.fold_btn, self.check_btn, self.call_btn, self.raise_btn, self.allin_btn):
            b.hide()
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
        stack_meaningful = (hero and hero.stack >= 0.05)

        # ── Canlı GTO advice — hesapla ama EKRANDA GÖSTERME ──
        # Eğitim modu: önce sen karar ver. Optimal karar el sonunda reveal
        # panelinde açıklanır. Burada sadece snapshot alıp koça veriyoruz.
        gto = self._gto_pct(hand, hero_idx, mode="cash")
        self._capture_decision(hand, gto, to_call)

        def lbl(base: str, atype) -> str:
            return base   # canlı oyunda cevabı sızdırma

        if ActionType.FOLD in valid_types:
            self.fold_btn.setText(lbl("FOLD", ActionType.FOLD))
            self.fold_btn.show()
        if ActionType.CHECK in valid_types:
            self.check_btn.setText(lbl("CHECK", ActionType.CHECK))
            self.check_btn.show()
        if ActionType.CALL in valid_types:
            self.call_btn.setText(lbl(f"CALL  {to_call:.1f} bb", ActionType.CALL))
            self.call_btn.show()
        elif (to_call > 0 and ActionType.ALL_IN in valid_types and stack_meaningful):
            self.call_btn.setText(f"CALL ALL-IN  {hero.stack:.1f}")
            self.call_btn.show()
        if ActionType.BET in valid_types:
            self.raise_btn.setText(lbl("BET", ActionType.BET))
            self.raise_btn.show()
        if ActionType.RAISE in valid_types:
            self.raise_btn.setText(lbl("RAISE", ActionType.RAISE))
            self.raise_btn.show()
        if stack_meaningful and to_call < hero.stack:
            self.allin_btn.setText(lbl(f"ALL-IN  {hero.stack:.1f}", ActionType.ALL_IN))
            self.allin_btn.show()

    def _gto_pct(self, hand, hero_idx, mode="cash"):
        """Canlı GTO advice (hata güvenli) + AI koç için state'e yaz."""
        try:
            from app.poker.gto_live_advice import live_gto_advice
            adv = live_gto_advice(hand, hero_idx, mode=mode)
            # AI koçun 'kararım doğru mu' sorusuna cevap verebilmesi için state'e koy
            if adv and adv.available and self.state is not None:
                # Somut pot-matematiği için pot/to_call'ı da sakla (AI koç)
                try:
                    to_call = float(hand.to_call(hero_idx))
                    pot = float(hand.pot)
                    street = hand.street_name
                except Exception:
                    to_call, pot, street = 0.0, 0.0, ""
                self.state.live_gto = {
                    "scenario": adv.scenario, "hand": adv.hand_key,
                    "stack_bb": adv.stack_bb, "tier": adv.tier_label,
                    "fold": adv.fold, "call": adv.call,
                    "raise": adv.raise_, "allin": adv.allin,
                    "pot_bb": pot, "to_call_bb": to_call, "street": street,
                }
                self._attach_sizing(hand, hero_idx, mode)
            elif self.state is not None:
                self.state.live_gto = None
            return adv
        except Exception:
            return None

    def _attach_sizing(self, hand, hero_idx, mode="cash"):
        """Bet-sizing önerisini state.live_gto'ya ekle (AI koç leak analizi için)."""
        try:
            from app.poker.sizing_advice import sizing_advice
            sz = sizing_advice(hand, hero_idx, mode=mode)
            if sz and sz.available and self.state and self.state.live_gto:
                self.state.live_gto["sizing"] = {
                    "label": sz.label, "rec_bb": sz.recommended_bb,
                    "frac": sz.recommended_frac, "note": sz.note,
                }
        except Exception:
            pass

    @staticmethod
    def _spot_context(hand, hero_idx, bb=1.0) -> dict:
        """Postflop EXACT solver için spot bağlamı (board/hero/stack/IP)."""
        ctx = {"board": "", "hero_combo": "", "hero_cards_disp": "",
               "hero_position": "", "n_active": 2, "raiser_pos": "",
               "villain_position": "",
               "eff_stack_bb": 0.0, "in_position": True, "pot_type": "SRP"}
        try:
            comm = getattr(hand, "community", []) or []
            ctx["board"] = " ".join(c.code for c in comm)
            hero = hand.players[hero_idx]
            ctx["hero_position"] = getattr(hero, "position", "") or ""
            if getattr(hero, "hole_cards", None) and len(hero.hole_cards) >= 2:
                ctx["hero_combo"] = hero.hole_cards[0].code + hero.hole_cards[1].code
                ctx["hero_cards_disp"] = " ".join(c.display for c in hero.hole_cards[:2])
            ctx["eff_stack_bb"] = round((hero.stack + hero.current_bet) / max(bb, 1e-9), 1)
            ctx["n_active"] = int(getattr(hand, "active_count", 2) or 2)
            from app.poker.gto_live_advice import (
                _hero_in_position, _count_preflop_raises_before_hero)
            from app.poker.decision_capture import preflop_pot_type
            ctx["in_position"] = _hero_in_position(hand, hero_idx)
            ctx["pot_type"] = preflop_pot_type(hand)
            _, _rp = _count_preflop_raises_before_hero(hand, hero_idx)
            ctx["raiser_pos"] = _rp or ""
            others = [p for i, p in enumerate(hand.players)
                      if i != hero_idx and not getattr(p, "is_folded", False)
                      and not getattr(p, "is_eliminated", False)]
            if len(others) == 1:
                ctx["villain_position"] = getattr(others[0], "position", "") or ""
        except Exception:
            pass
        return ctx

    def _mtt_stage(self) -> str:
        """Turnuva aşaması — kalan oyuncu oranı + bubble yakınlığı.

        cash/sng-dışı veya turnuva yoksa "" döner. Aşamalar segment
        analizinde 'MTT · orta aşama · ...' etiketine girer.
        """
        if self._format == "cash" or not getattr(self, "tournament", None):
            return ""
        try:
            t = self.tournament
            field = max(int(getattr(t.config, "field_size", 0) or 0), 1)
            left = int(getattr(t, "players_remaining", field) or field)
            paid = int(getattr(t.config, "paid_places", 0) or 0)
            if left <= max(1, min(9, paid)):
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

    def _capture_decision(self, hand, gto, to_call) -> None:
        """Hero'nun bu karar noktasındaki GTO-optimal dağılımını sakla.

        El bitince ``gto_reveal`` panelinde gösterilir. Street başına bir kez
        (to_call seviyesi değişirse yeni karar) — re-render'da tekrar eklemez.
        """
        log = getattr(self, "_decision_log", None)
        if log is None:
            self._decision_log = log = []
            self._captured_keys = set()
        key = (hand.street_name, round(to_call, 1))
        if key in self._captured_keys:
            return
        self._captured_keys.add(key)
        snap = {
            "street": hand.street_name,
            "scenario": getattr(gto, "scenario", "") if gto else "",
            "tier": getattr(gto, "tier_label", "") if gto else "",
            "available": bool(getattr(gto, "available", False)) if gto else False,
            "note": getattr(gto, "note", "") if gto else "",
            "fold": getattr(gto, "fold", 0) if gto else 0,
            "call": getattr(gto, "call", 0) if gto else 0,
            "raise": getattr(gto, "raise_", 0) if gto else 0,
            "allin": getattr(gto, "allin", 0) if gto else 0,
            "equity": getattr(gto, "equity", 0) if gto else 0,
            "pot_bb": float(getattr(hand, "pot", 0) or 0),
            "to_call_bb": float(to_call or 0),
            "hero_action": None, "hero_amount": None,
            "format": self._format, "stage": self._mtt_stage(),
            **self._spot_context(hand, hand.hero_idx, bb=1.0),
        }
        sz = (self.state.live_gto or {}).get("sizing") if (self.state and self.state.live_gto) else None
        if sz:
            snap["sizing_label"] = sz.get("label")
            snap["sizing_bb"] = sz.get("rec_bb")
        self._decision_log.append(snap)

    def _record_hero_decision(self, action_type, amount) -> None:
        """Hero'nun gerçek kararını son karar snapshot'ına ekle."""
        log = getattr(self, "_decision_log", None)
        if not log:
            return
        last = log[-1]
        if last.get("hero_action") is None:
            last["hero_action"] = action_type.name
            last["hero_amount"] = float(amount or 0)

    def _capture_decision_mtt(self, hand, gto, to_call, bb) -> None:
        """Turnuva karar noktası snapshot'ı (chip → bb dönüşümlü)."""
        log = getattr(self, "_decision_log_mtt", None)
        if log is None:
            self._decision_log_mtt = log = []
            self._captured_keys_mtt = set()
        key = (hand.street_name, round(to_call / max(bb, 1), 1))
        if key in self._captured_keys_mtt:
            return
        self._captured_keys_mtt.add(key)
        snap = {
            "street": hand.street_name,
            "scenario": getattr(gto, "scenario", "") if gto else "",
            "tier": getattr(gto, "tier_label", "") if gto else "",
            "available": bool(getattr(gto, "available", False)) if gto else False,
            "note": getattr(gto, "note", "") if gto else "",
            "fold": getattr(gto, "fold", 0) if gto else 0,
            "call": getattr(gto, "call", 0) if gto else 0,
            "raise": getattr(gto, "raise_", 0) if gto else 0,
            "allin": getattr(gto, "allin", 0) if gto else 0,
            "equity": getattr(gto, "equity", 0) if gto else 0,
            "pot_bb": float(getattr(hand, "pot", 0) or 0) / max(bb, 1),
            "to_call_bb": float(to_call or 0) / max(bb, 1),
            "format": self._format, "stage": self._mtt_stage(),
            **self._spot_context(hand, hand.hero_idx, bb=bb),
            "hero_action": None, "hero_amount": None, "_bb": bb,
        }
        sz = (self.state.live_gto or {}).get("sizing") if (self.state and self.state.live_gto) else None
        if sz:
            snap["sizing_label"] = sz.get("label")
            snap["sizing_bb"] = sz.get("rec_bb")
        self._decision_log_mtt.append(snap)

    def _record_hero_decision_mtt(self, action_type, amount) -> None:
        log = getattr(self, "_decision_log_mtt", None)
        if not log:
            return
        last = log[-1]
        if last.get("hero_action") is None:
            last["hero_action"] = action_type.name
            bb = last.get("_bb", 1)
            last["hero_amount"] = float(amount or 0) / max(bb, 1)

    def _on_complete(self):
        _real_xp = bool(getattr(self.state, "real_experience", False)) if self.state else False
        log = getattr(self, "_decision_log", [])
        # Oturum karnesini güncelle
        if not hasattr(self, "_session_score"):
            from app.poker.session_score import SessionScore
            self._session_score = SessionScore()
        self._session_score.add_hand(log)
        if hasattr(self, "gto_reveal"):
            self.gto_reveal.show_decisions(
                log, graded=_real_xp,
                session_summary=self._session_score.summary())
        try:
            from app.db.repository import record_decision_log
            record_decision_log(log)
        except Exception:
            pass
        if not self.game or not self.game.hand_history:
            return
        if self.game.current_hand:
            self.live_hud.update_from_hand(self.game.current_hand)
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

        if hasattr(self, "review_btn"):
            self.review_btn.setEnabled(True)

        session_stats = self.game.get_session_stats() if self.game else {}
        hero_stack = self.game.players[0].stack if self.game and self.game.players else 0.0
        hand_data = {
            "hand_id": r.hand_id, "hero_cards": r.hero_cards, "community": r.community or "—",
            "hero_position": r.hero_position, "hero_stack_bb": round(hero_stack, 1),
            "pot": round(r.pot, 1), "hero_invested": round(r.hero_invested, 1),
            "hero_profit": round(r.hero_profit, 1), "hero_won": r.hero_won,
            "winner_hand_name": r.winner_hand_name, "streets_seen": r.streets_seen,
            "actions": _format_actions_for_coach(r.actions), "session": session_stats,
            "source": "play_session",
        }
        self.hand_completed.emit(hand_data)
        self.next_btn.show()

    def _review_last(self):
        if not self.game or not self.game.hand_history:
            return
        r = self.game.hand_history[-1]
        hero_stack = self.game.players[0].stack if self.game.players else 0.0
        hand_data = {
            "hand_id": r.hand_id, "hero_cards": r.hero_cards, "community": r.community or "—",
            "hero_position": r.hero_position, "hero_stack_bb": round(hero_stack, 1),
            "pot": round(r.pot, 1), "hero_invested": round(r.hero_invested, 1),
            "hero_profit": round(r.hero_profit, 1), "hero_won": r.hero_won,
            "winner_hand_name": r.winner_hand_name, "streets_seen": r.streets_seen,
            "actions": _format_actions_for_coach(r.actions),
            "session": self.game.get_session_stats(), "source": "review_request",
        }
        self.hand_completed.emit(hand_data)

    def _show_gto_popup(self) -> None:
        pos, stack_bb, hero_cards, street, pot, players = "", 100.0, "", "preflop", 0.0, 6
        if self.game and self.game.current_hand:
            hand = self.game.current_hand
            hero = hand.hero
            if hero:
                pos = getattr(hero, "position", "") or ""
                stack_bb = float(hero.stack)
                if hero.hole_cards:
                    hero_cards = " ".join(c.display for c in hero.hole_cards[:2])
            street = getattr(hand, "street_name", "preflop")
            pot = float(hand.pot)
            players = sum(1 for p in hand.players
                          if not getattr(p, "is_eliminated", False)
                          and not getattr(p, "is_folded", False))
        elif self.game:
            players = self.game.active_players_count

        show_gto_dialog(
            parent=self, position=pos, stack_bb=stack_bb,
            players_active=players, game_type="cash",
            hero_cards=hero_cards, street=street, pot_bb=pot,
        )

    def _end_session(self):
        if not self.game:
            return
        stats = self.game.get_session_stats()
        data = [
            {"hero_profit": h.hero_profit, "hero_won": h.hero_won, "streets_seen": h.streets_seen}
            for h in self.game.hand_history
        ]
        self.coach_message.emit(session_summary(stats, data))
        self.game = None
        self._build_setup()

    # ── MTT GAME LOOP ─────────────────────────────────────────────

    def _deal_next_mtt(self):
        if not self.tournament:
            return
        if self.tournament.is_complete:
            self._mtt_tournament_over()
            return
        if hasattr(self, "mtt_next_btn"):
            self.mtt_next_btn.hide()
        self._decision_log_mtt = []
        self._captured_keys_mtt = set()
        if hasattr(self, "mtt_gto_reveal"):
            self.mtt_gto_reveal.hide_panel()
        self.tournament.start_hand()
        self._refresh_mtt()
        game = self.tournament.game
        if (not game.is_waiting_for_hero
                and game.current_hand
                and not game.current_hand.is_complete):
            self._mtt_bot_timer.start()

    def _hero_action_mtt(self, action_type: ActionType):
        if not self.tournament or self.tournament.is_complete:
            return
        if not self.tournament.game.is_waiting_for_hero:
            return

        hand = self.tournament.game.current_hand
        hero = hand.hero
        amount = 0.0

        if action_type in (ActionType.BET, ActionType.RAISE):
            amount = self._mtt_size_chips()
        elif action_type == ActionType.CALL:
            amount = hand.to_call(hand.hero_idx)
        elif action_type == ActionType.ALL_IN:
            amount = hero.stack if hero else 0.0

        self._record_hero_decision_mtt(action_type, amount)
        self.tournament.hero_act(action_type, amount)
        self._refresh_mtt()

        if hand.is_complete:
            self.tournament.advance_after_hand_complete()
            self._on_complete_mtt()
        else:
            self._mtt_bot_timer.start()

    def _tick_bot_mtt(self):
        if not self.tournament or not self.tournament.game.current_hand:
            self._mtt_bot_timer.stop()
            return
        keep_going = self.tournament.game.step_action()
        self._refresh_mtt()
        if not keep_going:
            self._mtt_bot_timer.stop()
            if self.tournament.game.current_hand.is_complete:
                self.tournament.advance_after_hand_complete()
                self._on_complete_mtt()

    def _space_pressed_mtt(self):
        if hasattr(self, "mtt_next_btn") and self.mtt_next_btn and self.mtt_next_btn.isVisible():
            self._deal_next_mtt()
            return
        # Fold sonrası anında ileri sar + sonraki el (turnuva)
        g = self.tournament.game if self.tournament else None
        if (g and g.current_hand and not g.current_hand.is_complete
                and not g.is_waiting_for_hero):
            hero = g.current_hand.hero
            if hero and hero.is_folded:
                if hasattr(self, "_mtt_bot_timer"):
                    self._mtt_bot_timer.stop()
                guard = 0
                while (g.current_hand and not g.current_hand.is_complete
                       and not g.is_waiting_for_hero and guard < 400):
                    g.step_action()
                    guard += 1
                if g.current_hand and g.current_hand.is_complete:
                    self.tournament.advance_after_hand_complete()
                    self._refresh_mtt()
                    self._on_complete_mtt()
                self._deal_next_mtt()

    def _key_action_mtt(self, key: str) -> None:
        if not self.tournament or not self.tournament.game.is_waiting_for_hero:
            return
        if key == "F" and self.mtt_fold_btn.isVisible():
            self.mtt_fold_btn.click()
        elif key == "C":
            if self.mtt_call_btn.isVisible():
                self.mtt_call_btn.click()
            elif self.mtt_check_btn.isVisible():
                self.mtt_check_btn.click()
        elif key == "R" and self.mtt_raise_btn.isVisible():
            self.mtt_raise_btn.click()
        elif key == "A" and self.mtt_allin_btn.isVisible():
            self.mtt_allin_btn.click()

    def _mtt_size_chips(self) -> float:
        """Slider → legal bet/raise in tournament chips."""
        hand = self.tournament.game.current_hand
        hero = hand.hero
        pct = self.mtt_size_slider.value() / 100.0
        if hand.street == Street.PREFLOP and hand.pot <= hand.big_blind * 3:
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

    def _refresh_mtt_size(self):
        if not self.tournament or not self.tournament.game.current_hand:
            return
        hand = self.tournament.game.current_hand
        chips = self._mtt_size_chips()
        bb = max(hand.big_blind, 1)
        bb_eq = chips / bb
        pot = max(hand.pot, 0.01)
        pct = int(round(100 * chips / pot))
        self.mtt_size_label.setText(f"{bb_eq:.1f}bb  ·  {pct}% pot  ·  {int(chips):,}")

    def _refresh_mtt(self):
        if not self.tournament:
            return
        t = self.tournament
        game = t.game
        hand = game.current_hand
        if not hand:
            return

        state = t.state
        level = state.current_level
        hero = hand.hero

        remaining = t.players_remaining
        total = t.config.field_size
        alive_stacks = [p.stack for p in game.players if not p.is_eliminated]
        avg_chips = int(sum(alive_stacks) / max(len(alive_stacks), 1))
        hero_chips = int(hero.stack) if hero else 0
        hands_left = state.hands_until_next_level

        ante_str = f"/{level.ante:,}" if level.ante else ""
        self.mtt_meta["event"].set_value(t.config.name[:16])
        self.mtt_meta["level"].set_value(f"L{state.level_idx + 1}")
        self.mtt_meta["level"].set_detail(f"{level.sb:,}/{level.bb:,}{ante_str}")
        self.mtt_meta["players"].set_value(f"{remaining}")
        self.mtt_meta["players"].set_detail(f"of {total}")
        self.mtt_meta["hero"].set_value(f"{hero_chips:,}")
        self.mtt_meta["hero"].set_detail(f"{hero_chips // max(level.bb, 1):.0f}bb" if hero else "—")
        self.mtt_meta["avg"].set_value(f"{avg_chips:,}")
        self.mtt_meta["next"].set_value(str(hands_left))
        self.mtt_meta["next"].set_detail("hands left")

        # Poker table
        action_top = game._action_queue[0] if game._action_queue else -1
        seats, hero_slot, dealer_slot = seats_from_hand(
            hand.players, hand.hero_idx,
            action_queue_top=action_top, unit="bb", hand=hand,
        )
        hero_to_call = hand.to_call(hand.hero_idx) if hero else 0.0
        board = [c.display for c in hand.community]
        hero_cards = [c.display for c in hero.hole_cards] if (hero and hero.hole_cards) else None
        note = f"L{state.level_idx + 1} · {level.sb:,}/{level.bb:,}"
        if level.ante:
            note += f"/{level.ante:,}"

        self.mtt_table.render_state(
            seats=seats,
            hero_slot_idx=hero_slot,
            dealer_slot_idx=dealer_slot,
            street=hand.street_name,
            board=board,
            pot=hand.pot,
            hero_cards=hero_cards,
            note=note,
            big_pot=(hand.street == Street.PREFLOP),
            show_opponent_backs=not hand.is_complete,
            to_call=hero_to_call,
        )

        if game.is_waiting_for_hero and hero_to_call > 0 and hand.pot > 0:
            bb = max(level.bb, 1)
            self.mtt_to_call_banner.setText(
                f"TO CALL  {int(hero_to_call):,}  ·  {hero_to_call/bb:.1f}bb"
            )
            self.mtt_to_call_banner.show()
        else:
            self.mtt_to_call_banner.hide()

        self._update_mtt_action_buttons()
        self._refresh_mtt_size()

    def _update_mtt_action_buttons(self):
        for b in (self.mtt_fold_btn, self.mtt_check_btn, self.mtt_call_btn,
                  self.mtt_raise_btn, self.mtt_allin_btn):
            b.hide()
        if not self.tournament or not self.tournament.game.is_waiting_for_hero:
            return
        hand = self.tournament.game.current_hand
        if not hand or hand.is_complete:
            return
        hero_idx = hand.hero_idx
        hero = hand.hero
        valid = hand.get_valid_actions(hero_idx)
        valid_types = {v[0] for v in valid}
        to_call = hand.to_call(hero_idx)
        stack_meaningful = (hero and hero.stack >= 1)
        level = self.tournament.state.current_level
        bb = max(level.bb, 1)

        # GTO snapshot al (gösterme — el sonunda reveal'da açılacak)
        gto = self._gto_pct(hand, hero_idx, mode="MTT")
        self._capture_decision_mtt(hand, gto, to_call, bb)

        if ActionType.FOLD in valid_types:
            self.mtt_fold_btn.show()
        if ActionType.CHECK in valid_types:
            self.mtt_check_btn.show()
        if ActionType.CALL in valid_types:
            self.mtt_call_btn.setText(f"CALL  {to_call/bb:.1f}bb  ({int(to_call):,})")
            self.mtt_call_btn.show()
        elif (to_call > 0 and ActionType.ALL_IN in valid_types and stack_meaningful):
            self.mtt_call_btn.setText(f"CALL ALL-IN  {hero.stack/bb:.1f}bb")
            self.mtt_call_btn.show()
        if ActionType.BET in valid_types:
            self.mtt_raise_btn.setText("BET")
            self.mtt_raise_btn.show()
        if ActionType.RAISE in valid_types:
            self.mtt_raise_btn.setText("RAISE")
            self.mtt_raise_btn.show()
        if stack_meaningful and to_call < hero.stack:
            self.mtt_allin_btn.setText(f"ALL-IN  {hero.stack/bb:.1f}bb  ({int(hero.stack):,})")
            self.mtt_allin_btn.show()

    def _on_complete_mtt(self):
        _real_xp = bool(getattr(self.state, "real_experience", False)) if self.state else False
        log = getattr(self, "_decision_log_mtt", [])
        if not hasattr(self, "_session_score_mtt"):
            from app.poker.session_score import SessionScore
            self._session_score_mtt = SessionScore()
        self._session_score_mtt.add_hand(log)
        if hasattr(self, "mtt_gto_reveal"):
            self.mtt_gto_reveal.show_decisions(
                log, graded=_real_xp,
                session_summary=self._session_score_mtt.summary())
        try:
            from app.db.repository import record_decision_log
            record_decision_log(log)
        except Exception:
            pass
        if not self.tournament:
            return
        t = self.tournament
        game = t.game

        if not game or not game.hand_history:
            return

        # Update live HUD
        if game.current_hand:
            self.live_hud.update_from_hand(game.current_hand)

        r = game.hand_history[-1]
        color = "#5ad17a" if r.hero_won else "#e87474" if r.hero_invested > 0 else "#898d80"
        outcome = "✓  WON" if r.hero_won else ("✗  LOST" if r.hero_invested > 0 else "—  FOLDED")
        level = t.state.current_level
        bb = max(level.bb, 1)

        self.mtt_feedback.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 13px; "
            f"font-weight: 600; color: {color}; padding: 6px 0;"
        )
        self.mtt_feedback.setText(
            f"HAND #{r.hand_id}  ·  {outcome}  ·  Pot {r.pot/bb:.1f}bb ({int(r.pot):,})  ·  "
            f"Net {r.hero_profit/bb:+.1f}bb  ·  {r.winner_hand_name}"
        )
        row = QLabel(
            f"#{r.hand_id:>3}  {r.hero_cards:<8}  →  {r.community:<20}  "
            f"{'W' if r.hero_won else 'L'}  {r.hero_profit/bb:+.1f}bb  {r.winner_hand_name}"
        )
        row.setStyleSheet(
            f"font-family: 'JetBrains Mono', Menlo, monospace; font-size: 11px; "
            f"color: {'#5ad17a' if r.hero_won else '#898d80'};"
        )
        self.mtt_history_layout.addWidget(row)
        while self.mtt_history_layout.count() > 8:
            it = self.mtt_history_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        # Hand data for coach
        hand_data = {
            "hand_id": r.hand_id, "hero_cards": r.hero_cards, "community": r.community or "—",
            "hero_position": r.hero_position,
            "hero_stack_bb": round(game.players[0].stack / bb, 1) if game.players else 0,
            "pot": round(r.pot / bb, 1), "hero_invested": round(r.hero_invested / bb, 1),
            "hero_profit": round(r.hero_profit / bb, 1), "hero_won": r.hero_won,
            "winner_hand_name": r.winner_hand_name, "streets_seen": r.streets_seen,
            "actions": _format_actions_for_coach(r.actions), "source": "mtt_play_session",
        }
        self.hand_completed.emit(hand_data)

        # Check tournament end conditions
        if t.is_complete:
            self._mtt_tournament_over()
            return

        # Check hero elimination
        hero_player = game.players[0] if game.players else None
        if hero_player and hero_player.is_eliminated:
            placement = t.players_remaining + 1
            self.mtt_feedback.setText(
                f"Hero elendi! Bitiriş yeri: #{placement}. Esc ile yeni setup."
            )
            self.coach_message.emit(
                f"MTT/SNG bitti — Hero #{placement} bitirdi. Yeni turnuva için Esc'ye bas."
            )
            if hasattr(self, "mtt_next_btn"):
                self.mtt_next_btn.hide()
            return

        self.mtt_next_btn.show()

    def _mtt_tournament_over(self):
        if not self.tournament:
            return
        remaining = self.tournament.players_remaining
        self.mtt_feedback.setText(
            f"Turnuva bitti! Kalan oyuncu: {remaining}. Yeni turnuva için Esc."
        )
        self.coach_message.emit(
            f"Turnuva tamamlandı ({self._format.upper()}). "
            "Yeni bir turnuva için ESC ile setup'a dön."
        )

    def _end_mtt(self):
        if not self.tournament and not self._in_mtt:
            return
        timer = getattr(self, "_mtt_bot_timer", None)
        if timer is not None:
            timer.stop()
        self.tournament = None
        self.live_hud = LiveHUD()
        self._build_setup()
        self.coach_message.emit(
            f"{self._format.upper()} bitirildi. Yeni format veya ayar için setup'ta değişiklik yap."
        )


def _clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w:
            w.deleteLater()
