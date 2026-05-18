"""Tournament Play Mode — gerçek turnuva simülasyonu + GTO analizi + hata log.

Özellikler:
  • Oyuncu sayısı (2-11), stack, hız seç
  • ▶ Start Tournament → gerçek eller (game engine)
  • FOLD / CALL / RAISE / ALL-IN butonları
  • Karar sonrası GTO % görünür + neden hatalı açıklaması
  • Sağ panel: canlı hata log + session stats
  • "Drill My Mistakes" → hataları Spot Trainer kuyruğuna atar
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.db.tournament_archive import (
    TournamentRecord, save_tournament, load_archive,
    derive_leak_summary, new_id,
)
from app.db.mistakes_queue import (
    MistakeEntry as MqEntry, add_mistake, new_id as new_mistake_id,
)
from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType, HandState, Street, positions_for
from app.solver.mock_solver import compare_action, solve_spot
from app.training.trainer_scoring import score_decision, skill_label
from app.ui.components.card_view import CardView
from app.ui.components.live_poker_table import LivePokerTable
from app.simulator.field_simulator import FieldSimulator
from app.ui.components.mtt_setup_dialog import MttConfig, MttSetupDialog
from app.ui.components.tournament_result_dialog import TournamentResultDialog

# ── colour constants ───────────────────────────────────────────────────────
_C_BG     = "#0C1117"
_C_CARD   = "#131A24"
_C_BORDER = "#1E2733"
_C_MUTED  = "#6B7280"
_C_TEXT   = "#E5E7EB"
_C_CYAN   = "#22D3EE"
_C_GREEN  = "#10B981"
_C_RED    = "#EF4444"
_C_AMBER  = "#F59E0B"

# Blind structures: list of (level, sb, bb, ante)
BLIND_STRUCTURES: dict[str, list[tuple]] = {
    "regular": [
        (1, 50, 100, 0),   (2, 75, 150, 0),   (3, 100, 200, 0),
        (4, 150, 300, 25), (5, 200, 400, 50),  (6, 300, 600, 75),
        (7, 400, 800, 100),(8, 500,1000, 150), (9, 750,1500, 200),
        (10,1000,2000, 300),
    ],
    "turbo": [
        (1, 100, 200, 0),  (2, 150, 300, 25), (3, 200, 400, 50),
        (4, 300, 600, 75), (5, 500,1000, 150),(6, 750,1500, 200),
        (7,1000,2000, 300),(8,1500,3000, 400),
    ],
    "hyper": [
        (1, 200, 400, 50), (2, 400, 800, 100),(3, 600,1200, 150),
        (4,1000,2000, 300),(5,1500,3000, 400),
    ],
}


def _blind_at(
    level: int,
    speed: str,
    starting_stack: int = 20_000,
    bb_ante: bool = True,
) -> tuple[int, int, int]:
    """Get (sb, bb, ante) — auto-scaled so L1 BB ≈ starting_stack / 100.

    Reference (APT-style): for starting_stack=1000 → L1 = 10/20 (50bb), or
    for starting_stack=2000 → L1 = 20/40 (50bb). The fixed BLIND_STRUCTURES
    table was hard-wired for ~20k starting stacks; we rescale it.

    When bb_ante is True the ante grows the same as BB (modern online
    structure). When False the ante stays zero — the BB still pays the
    big blind but no extra orbit cost.
    """
    struct = BLIND_STRUCTURES.get(speed, BLIND_STRUCTURES["regular"])
    idx = min(level - 1, len(struct) - 1)
    _, sb, bb, ante = struct[idx]
    # Reference: original table assumes 20,000 starting stack
    scale = max(0.005, starting_stack / 20_000)
    sb   = max(1, int(round(sb * scale)))
    bb   = max(2, int(round(bb * scale)))
    ante = max(0, int(round(ante * scale)))
    if not bb_ante:
        ante = 0
    return sb, bb, ante


def _action_display(action_type: ActionType, hand: HandState) -> str:
    hero = hand.hero
    if hero is None:
        return action_type.value.upper()
    to_call = max(0.0, hand.current_bet - hero.current_bet)
    pot     = hand.pot + sum(p.current_bet for p in hand.players)
    if action_type == ActionType.FOLD:   return "FOLD"
    if action_type == ActionType.CHECK:  return "CHECK"
    if action_type == ActionType.CALL:   return f"CALL  {to_call:.0f}"
    if action_type == ActionType.BET:    return f"BET  {pot * 0.66:.0f}"
    if action_type == ActionType.RAISE:  return f"RAISE  {(hand.current_bet * 2.5):.0f}"
    if action_type == ActionType.ALL_IN: return f"ALL-IN  {hero.stack:.0f}"
    return action_type.value.upper()


def _btn_qss(action_type: ActionType) -> str:
    palettes = {
        ActionType.FOLD:   ("#1B2D4A", "#3B82F6", "#93C5FD"),
        ActionType.CHECK:  ("#0E2A1E", "#10B981", "#6EE7B7"),
        ActionType.CALL:   ("#0E2A1E", "#10B981", "#6EE7B7"),
        ActionType.BET:    ("#2A1B1B", "#EF4444", "#FCA5A5"),
        ActionType.RAISE:  ("#2A1B1B", "#EF4444", "#FCA5A5"),
        ActionType.ALL_IN: ("#1A0E0E", "#7F1D1D", "#FCA5A5"),
    }
    bg, border, fg = palettes.get(action_type, (_C_CARD, _C_BORDER, _C_TEXT))
    return (
        f"QPushButton{{background:{bg};border:2px solid {border};"
        f"border-radius:10px;color:{fg};font-size:15px;font-weight:800;"
        f"padding:10px 20px;min-height:60px;min-width:110px;}}"
        f"QPushButton:hover{{background:{bg}dd;}}"
    )


# ── session state ─────────────────────────────────────────────────────────

@dataclass
class MistakeEntry:
    hand_no:    int
    street:     str
    hero_action: str
    gto_action:  str
    ev_loss:    float
    why:        str


@dataclass
class TournamentSession:
    num_players:    int   = 9
    starting_stack: int   = 20_000
    speed:          str   = "regular"
    hero_stack:     int   = 20_000
    field_size:     int   = 9
    players_left:   int   = 9
    level:          int   = 1
    hands_this_level:int  = 0
    hands_per_level: int  = 10
    hands_played:   int   = 0
    decisions:      int   = 0
    correct:        int   = 0
    icm_punts:      int   = 0
    total_ev_loss:  float = 0.0
    mistakes:       list  = field(default_factory=list)
    running:        bool  = False
    busted:         bool  = False
    # ── full MTT config used to spawn realistic bots & later archive ──
    config:         object = None      # MttConfig | None
    tournament_id:  str    = ""
    started_at:     str    = ""
    bot_mix:        list   = field(default_factory=list)
    buyin:          float  = 0.0
    # Real hand-by-hand state: background field + per-hand history
    field_sim:      object = None      # FieldSimulator | None
    hand_history:   list   = field(default_factory=list)   # list of HandRecord dicts


# ── main screen ───────────────────────────────────────────────────────────

class TournamentPlayScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state   = state
        self.session = TournamentSession()
        self.game: PokerGame | None = None
        self._drills = generate_spot_drills(120)
        self._action_btns: list[tuple[QPushButton, ActionType]] = []
        self._answered_this_hand = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top setup bar ──────────────────────────────────────────────
        setup = QFrame()
        setup.setFixedHeight(56)
        setup.setStyleSheet(f"background:{_C_CARD};border-bottom:1px solid {_C_BORDER};")
        sr = QHBoxLayout(setup)
        sr.setContentsMargins(16, 8, 16, 8)
        sr.setSpacing(10)

        title = QLabel("🏆  Tournament Play Mode")
        title.setStyleSheet(f"color:{_C_TEXT};font-size:16px;font-weight:700;")
        sr.addWidget(title)
        sr.addSpacing(20)

        # Current tournament summary (filled after Start)
        self._tour_summary = QLabel("Henüz başlatılmadı.")
        self._tour_summary.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        sr.addWidget(self._tour_summary)
        sr.addStretch(1)

        self.start_btn = QPushButton("▶  New Tournament…")
        self.start_btn.setFixedHeight(36)
        self.start_btn.setStyleSheet(
            f"QPushButton{{background:{_C_GREEN};color:#061018;border-radius:8px;"
            "font-weight:800;font-size:13px;padding:4px 18px;border:none;}"
            f"QPushButton:hover{{background:#0EA371;}}"
        )
        self.start_btn.clicked.connect(self._open_setup)
        sr.addWidget(self.start_btn)

        # Auto-advance toggle — when ON, 'Sonraki El →' fires automatically
        # after the configured delay so the tournament flows without clicks.
        self._auto_advance = False
        self._auto_delay_ms = 2000
        self.auto_btn = QPushButton("⏵  Auto: KAPALI")
        self.auto_btn.setFixedHeight(36)
        self.auto_btn.setCheckable(True)
        self.auto_btn.setStyleSheet(
            f"QPushButton{{background:{_C_CARD};color:{_C_MUTED};"
            f"border:1px solid {_C_BORDER};border-radius:8px;font-size:12px;"
            f"padding:4px 14px;font-weight:700;}}"
            f"QPushButton:checked{{background:#0D2030;color:{_C_CYAN};border-color:{_C_CYAN};}}"
        )
        self.auto_btn.clicked.connect(self._toggle_auto)
        sr.addWidget(self.auto_btn)

        self.archive_btn = QPushButton("📁  Past")
        self.archive_btn.setFixedHeight(36)
        self.archive_btn.setStyleSheet(
            f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            "border-radius:8px;font-size:12px;padding:4px 14px;}"
            f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        )
        self.archive_btn.clicked.connect(self._open_archive)
        sr.addWidget(self.archive_btn)

        self.reset_btn = QPushButton("↺  Bust Out")
        self.reset_btn.setFixedHeight(36)
        self.reset_btn.setVisible(False)
        self.reset_btn.setStyleSheet(
            f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            "border-radius:8px;font-size:12px;padding:4px 12px;}"
            f"QPushButton:hover{{border-color:{_C_RED};color:{_C_RED};}}"
        )
        self.reset_btn.clicked.connect(self._reset)
        sr.addWidget(self.reset_btn)
        root.addWidget(setup)

        # ── Context strip ──────────────────────────────────────────────
        ctx = QFrame()
        ctx.setFixedHeight(48)
        ctx.setStyleSheet(f"background:#0A0F16;border-bottom:1px solid {_C_BORDER};")
        cr = QHBoxLayout(ctx)
        cr.setContentsMargins(16, 0, 16, 0)
        cr.setSpacing(22)
        self._ctx: dict[str, QLabel] = {}
        for key, default in [("Level","L1"),("Blinds","100/200"),
                              ("Hero Stack","20,000"),("Stack bb","100bb"),
                              ("M-ratio","67"),("Players","9/9"),("Hands","0")]:
            col = QWidget()
            cv  = QVBoxLayout(col); cv.setContentsMargins(0,3,0,3); cv.setSpacing(0)
            k_lbl = QLabel(key); k_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:10px;")
            v_lbl = QLabel(default); v_lbl.setStyleSheet(f"color:{_C_TEXT};font-size:13px;font-weight:700;")
            cv.addWidget(k_lbl); cv.addWidget(v_lbl)
            cr.addWidget(col)
            self._ctx[key] = v_lbl
        cr.addStretch(1)
        root.addWidget(ctx)

        # ── Body split: table + log ────────────────────────────────────
        body = QHBoxLayout()
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(0)

        # LEFT — table, cards, actions, feedback
        left = QWidget()
        left.setStyleSheet(f"background:{_C_BG};")
        lv = QVBoxLayout(left); lv.setContentsMargins(0,0,0,0); lv.setSpacing(0)

        self.live_table = LivePokerTable()
        self.live_table.setMinimumHeight(360)
        lv.addWidget(self.live_table, 1)

        # Cards bar: hero hole cards (CardView) + community + context
        cards_bar = QFrame()
        cards_bar.setFixedHeight(96)
        cards_bar.setStyleSheet(f"background:#0A0F16;border-top:1px solid {_C_BORDER};")
        cbr = QHBoxLayout(cards_bar); cbr.setContentsMargins(16,8,16,8); cbr.setSpacing(12)

        # Hero cards on the left
        hero_block = QVBoxLayout(); hero_block.setSpacing(2)
        hero_lbl = QLabel("Your hand"); hero_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:10px;")
        hero_block.addWidget(hero_lbl)
        self._hero_cards_row = QHBoxLayout(); self._hero_cards_row.setSpacing(4)
        hero_cards_w = QWidget(); hero_cards_w.setLayout(self._hero_cards_row)
        hero_block.addWidget(hero_cards_w)
        cbr.addLayout(hero_block)

        # Vertical separator
        sep = QFrame(); sep.setFixedWidth(1); sep.setStyleSheet(f"background:{_C_BORDER};")
        cbr.addWidget(sep)

        # Board cards
        board_block = QVBoxLayout(); board_block.setSpacing(2)
        board_lbl = QLabel("Board"); board_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:10px;")
        board_block.addWidget(board_lbl)
        self._board_row = QHBoxLayout(); self._board_row.setSpacing(4)
        board_w = QWidget(); board_w.setLayout(self._board_row)
        board_block.addWidget(board_w)
        cbr.addLayout(board_block)

        # Context label on the right
        cbr.addStretch(1)
        self._spot_ctx = QLabel()
        self._spot_ctx.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._spot_ctx.setStyleSheet(f"color:{_C_MUTED};font-size:11px;")
        cbr.addWidget(self._spot_ctx)
        lv.addWidget(cards_bar)

        # Action buttons row
        self._act_frame = QFrame()
        self._act_frame.setFixedHeight(90)
        self._act_frame.setStyleSheet(
            f"QFrame{{background:{_C_BG};border-top:2px solid {_C_BORDER};}}"
        )
        self._act_layout = QHBoxLayout(self._act_frame)
        self._act_layout.setContentsMargins(16,10,16,10)
        self._act_layout.setSpacing(10)
        lv.addWidget(self._act_frame)

        # Feedback — clickable: anywhere on the panel advances to next hand
        self._fb = QFrame()
        self._fb.setObjectName("FeedbackPanel")
        self._fb.setStyleSheet(
            f"QFrame#FeedbackPanel{{background:{_C_CARD};border-top:1px solid {_C_BORDER};}}"
            f"QFrame#FeedbackPanel:hover{{background:#1A2230;}}"
        )
        self._fb.setCursor(Qt.PointingHandCursor)
        # Mouse click anywhere on the feedback panel → next hand
        self._fb.mousePressEvent = lambda ev: (
            self._next_hand() if self._fb.maximumHeight() > 0 else None
        )
        self._fb_layout = QVBoxLayout(self._fb)
        self._fb_layout.setContentsMargins(16,10,16,10)
        self._fb.setMaximumHeight(0)
        lv.addWidget(self._fb)

        # ── Multi-modal 'next hand' keyboard shortcuts ──────────────
        # Space / Enter / N — fire next hand
        from PySide6.QtGui import QShortcut, QKeySequence
        for keyseq in ("Space", "Return", "Enter", "N"):
            sc = QShortcut(QKeySequence(keyseq), self)
            sc.activated.connect(self._kbd_next_hand)
        body.addWidget(left, 3)

        # RIGHT — stats + mistake log
        right = QWidget()
        right.setFixedWidth(300)
        right.setStyleSheet(f"background:{_C_CARD};border-left:1px solid {_C_BORDER};")
        rv = QVBoxLayout(right); rv.setContentsMargins(12,12,12,12); rv.setSpacing(8)

        stats_f = QFrame()
        stats_f.setStyleSheet(f"background:{_C_BG};border-radius:8px;")
        sv = QVBoxLayout(stats_f); sv.setContentsMargins(10,8,10,8); sv.setSpacing(3)
        sv.addWidget(_section("Session Stats"))
        self._stat: dict[str, QLabel] = {}
        for key, default, color in [
            ("Decisions","0",  _C_TEXT),
            ("Accuracy","—",   _C_GREEN),
            ("Avg EV Loss","—",_C_AMBER),
            ("ICM Punts","0",  _C_RED),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(key+":"))
            val = QLabel(default)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"color:{color};font-weight:700;")
            row.addWidget(val)
            sv.addLayout(row)
            self._stat[key] = val
        rv.addWidget(stats_f)

        # ── Coach tip — bot tipine özel exploit önerisi ─────────────
        rv.addWidget(_section("💭  Coach Tavsiyesi"))
        self._coach_tip = QLabel(
            "Turnuva başlatıldığında bot mix'e göre exploit önerisi gelecek."
        )
        self._coach_tip.setWordWrap(True)
        self._coach_tip.setStyleSheet(
            f"QLabel{{background:#0F1E2A;color:{_C_TEXT};font-size:11px;"
            f"padding:10px 12px;border-radius:6px;border-left:3px solid {_C_CYAN};"
            f"font-weight:500;}}"
        )
        rv.addWidget(self._coach_tip)
        rv.addSpacing(8)

        rv.addWidget(_section("🔴  Mistake Log"))
        log_scroll = QScrollArea()
        log_scroll.setWidgetResizable(True)
        log_scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{_C_BG};}}"
            "QScrollBar:vertical{width:5px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:2px;}"
        )
        self._log_w = QWidget()
        self._log_w.setStyleSheet(f"background:{_C_BG};")
        self._log_vbox = QVBoxLayout(self._log_w)
        self._log_vbox.setContentsMargins(0,0,0,0)
        self._log_vbox.setSpacing(4)
        log_scroll.setWidget(self._log_w)
        rv.addWidget(log_scroll, 1)

        drill_btn = QPushButton("📋  Drill My Mistakes")
        drill_btn.setFixedHeight(36)
        drill_btn.setStyleSheet(
            f"QPushButton{{background:{_C_AMBER};color:#000;border-radius:8px;"
            "font-weight:700;font-size:12px;border:none;}"
        )
        drill_btn.clicked.connect(self._queue_mistakes)
        rv.addWidget(drill_btn)
        body.addWidget(right, 0)

        root.addLayout(body, 1)
        self._show_waiting()

    # ── waiting placeholder ────────────────────────────────────────────────
    def _show_waiting(self) -> None:
        _clear_layout(self._act_layout)
        w = QLabel("Ayarları seç → ▶ Start Tournament")
        w.setStyleSheet(f"color:{_C_MUTED};font-size:14px;")
        w.setAlignment(Qt.AlignCenter)
        self._act_layout.addWidget(w)

    # ── start / reset ──────────────────────────────────────────────────────
    def _open_setup(self) -> None:
        """Open the MTT setup dialog and start a tournament with that config."""
        from datetime import datetime
        dlg = MttSetupDialog(self)
        if dlg.exec() != dlg.Accepted:
            return
        cfg: MttConfig = dlg.config
        # Use MttConfig's derived speed_class (also factors in tournament_name)
        speed = cfg.speed_class
        n_table = cfg.table_size
        bot_mix = cfg.make_bot_mix(n_table)
        field_sim = FieldSimulator(
            field_size     = cfg.field_size,
            starting_stack = cfg.starting_stack,
            skill_style    = cfg.skill_style,
            skill_level    = cfg.skill_level,
        )
        self.session = TournamentSession(
            num_players    = n_table,
            starting_stack = cfg.starting_stack,
            speed          = speed,
            hero_stack     = cfg.starting_stack,
            field_size     = cfg.field_size,
            players_left   = cfg.field_size,
            config         = cfg,
            tournament_id  = new_id(),
            started_at     = datetime.now().isoformat(timespec="seconds"),
            bot_mix        = bot_mix,
            buyin          = cfg.buyin,
            field_sim      = field_sim,
            hand_history   = [],
        )
        self.session.running = True
        self._tour_summary.setText(
            f"{cfg.tournament_name}  ·  {cfg.field_size} oyuncu  ·  ${cfg.buyin:.0f} "
            f"·  {cfg.starting_stack:,} chip  ·  {cfg.skill_style}/{cfg.skill_level}"
        )
        # ── Coach tip: bot mix'e göre exploit önerisi ─────────────
        self._coach_tip.setText(self._coach_tip_for_mix(bot_mix, cfg))
        self.start_btn.setVisible(False)
        self.reset_btn.setVisible(True)
        _clear_layout(self._log_vbox)
        self._fb.setMaximumHeight(0)
        self._deal_hand()

    @staticmethod
    def _coach_tip_for_mix(bot_mix: list[str], cfg) -> str:
        """Bot mix dağılımına göre master-coach tavsiye üretir."""
        if not bot_mix:
            return "Bot mix tanımlanmadı."
        from collections import Counter
        counts = Counter(bot_mix)
        most_common = counts.most_common(1)[0][0]
        # Bot tipine özel exploit
        tips = {
            "Fish": (
                "🎣 FISH-HEAVY MASA\n"
                "Loose-passive oyuncular. Value-bet thin (top pair iyi kicker yeterli), "
                "büyük sizing (2/3-pot+) — onlar pot odds anlamaz. "
                "Bluff'tan kaçın — onlar bet'ine inanır, fold etmez."
            ),
            "Calling Station": (
                "🪨 CALLING STATION'lar\n"
                "Asla bluff yapma — her şey call'lanır. "
                "Value-heavy line, sizing'i büyüt (1.5x pot bile OK). "
                "Showdown'a getir, draws/marginal eller fold."
            ),
            "Aggro Fish": (
                "🦊 AGGRO FISH\n"
                "Loose + agresif ama unbalanced. Bluff frekansları yüksek — hero call "
                "frekansını artır. Premium eller trap için ideal (slow-play TT+). "
                "Onların aggresion'u senin value."
            ),
            "Maniac": (
                "🌀 MANIAC OYUNCULAR\n"
                "Her şey raise/jam — variance fıçısı. Sıkı tight range bekle, "
                "QQ+ ile light call. Bluff yapma — onlar her şey call'lar. "
                "Bankroll bb-fonlu olmalı, swing'ler büyük."
            ),
            "Tight Passive": (
                "🐢 TIGHT-PASSIVE\n"
                "Premium beklerler. Onlar bet attığında inan — bluff nadir. "
                "Sen geniş steal et — blind'ları çal. Onlara karşı 3-bet "
                "frequency artır, fold'a yüksek."
            ),
            "TAG": (
                "🎯 TAG (Tight-Aggressive)\n"
                "Solid winning reg profili. Standart GTO oyna — exploit zor. "
                "3-bet'lerine fazla fold ediyorlar (overfold leak) — light 3-bet bluff +EV. "
                "Postflop tight, c-bet'lere normal MDF."
            ),
            "LAG": (
                "⚔️ LAG (Loose-Aggressive)\n"
                "Geniş range, agresif. 4-bet bluff frequency yüksek olabilir — light "
                "5-bet jam (AKs+, QQ+). Postflop hero call'lar ödüllü, multi-street "
                "bluff catch için sabırlı ol."
            ),
            "Reg": (
                "♟️ REG (Düzenli oyuncu)\n"
                "TAG-LAG arası. GTO baseline'a yakın oynarlar. Exploit zor — büyük "
                "leaks için 1000+ el sample gerek. Disipline kal, marginal spotları fold."
            ),
            "Balanced Reg": (
                "⚖️ BALANCED REG\n"
                "GTO frequency'lere yakın oynar — exploit çok zor. Standart GTO ile "
                "savaş, marginal spotları premium spotlara çevirmeye çalışma. "
                "Variance düşürmek odak."
            ),
            "Shark": (
                "🦈 SHARK (Pro seviye)\n"
                "GTO + exploit ikisini de bilen pro. Exploit attempt ters tepebilir. "
                "Sadece premium spotları savaş, bluff frequency'leri düşür, "
                "thin value spotları skip — variance riski yüksek."
            ),
            "Nit": (
                "🐌 NIT (Çok sıkı)\n"
                "Premium only. Bluff sıklığı düşür (onların fold range'i geniş = "
                "bluff +EV). Bet attıklarında inan — sadece premium ile aggression. "
                "Blind'larından çal — defend frequency düşük."
            ),
            "Rock": (
                "🪨 ROCK\n"
                "Çok dar, çok agresif değil. Sürekli baskı kur — fold frekansları "
                "yüksek. Bet attığında stop ve düşün — sadece premium."
            ),
        }
        primary = tips.get(most_common, f"Karışık masa ({most_common} ağırlıklı).")
        # Compose multi-bot insight
        unique = len(set(bot_mix))
        summary = (
            f"📊 Masada {len(bot_mix)} bot, {unique} farklı arketip.  "
            f"Ana tip: **{most_common}**.\n\n{primary}"
        )
        # ICM context if applicable
        if cfg.field_size >= 100:
            summary += (
                f"\n\n💰 {cfg.field_size}-player MTT — bubble/FT yaklaştıkça ICM "
                f"premium ekle, kısa stack'lere maksimum baskı kur."
            )
        return summary

    def _reset(self) -> None:
        """Bust out / end current tournament → save record + show result dialog."""
        if self.session.running and self.session.config is not None:
            self._archive_current()
            self._show_result()
        self.session = TournamentSession()
        self.game    = None
        self._tour_summary.setText("Henüz başlatılmadı.")
        self._coach_tip.setText(
            "Turnuva başlatıldığında bot mix'e göre exploit önerisi gelecek."
        )
        self.start_btn.setVisible(True)
        self.reset_btn.setVisible(False)
        _clear_layout(self._log_vbox)
        self._fb.setMaximumHeight(0)
        self._show_waiting()
        self._update_ctx()
        self._update_stats()

    def _archive_current(self) -> None:
        """Persist the just-finished tournament to ~/.champion_poker_os/."""
        from datetime import datetime
        s = self.session
        cfg: MttConfig = s.config  # type: ignore
        if cfg is None:
            return
        # Finish position from FieldSimulator (real, derived from simulated play)
        sim: FieldSimulator | None = s.field_sim
        if sim is not None:
            finish = sim.finish_for_hero()
        elif s.busted:
            finish = max(1, int(s.field_size * 0.5))
        elif s.hero_stack >= 2 * s.starting_stack:
            finish = max(1, int(s.field_size * 0.15))
        else:
            finish = max(1, int(s.field_size * 0.35))
        paid_places = max(2, int(s.field_size * 0.15))
        cashed      = finish <= paid_places
        # Pool 7% rake
        pool   = cfg.buyin * cfg.field_size * 0.93
        payout = 0.0
        if cashed:
            # Simple pyramid: top1=22%, 2nd=15%, 3rd=11%, ...
            pcts = [0.22, 0.15, 0.11, 0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.02]
            idx = min(finish - 1, len(pcts) - 1)
            payout = round(pool * pcts[idx], 2)
        record = TournamentRecord(
            id                = s.tournament_id,
            started_at        = s.started_at,
            ended_at          = datetime.now().isoformat(timespec="seconds"),
            tournament_name   = cfg.tournament_name,
            field_size        = cfg.field_size,
            buyin             = cfg.buyin,
            starting_stack    = cfg.starting_stack,
            skill_style       = cfg.skill_style,
            skill_level       = cfg.skill_level,
            finish_position   = finish,
            hands_played      = s.hands_played,
            decisions         = s.decisions,
            correct_decisions = s.correct,
            total_ev_loss     = s.total_ev_loss,
            icm_punts         = s.icm_punts,
            cashed            = cashed,
            payout            = payout,
            notable_mistakes  = [
                {"street": m.street, "hero_action": m.hero_action,
                 "gto_action": m.gto_action, "ev_loss": m.ev_loss}
                for m in (s.mistakes or [])[:10]
            ],
            leak_summary      = derive_leak_summary([
                {"street": m.street, "hero_action": m.hero_action} for m in (s.mistakes or [])
            ]),
            hand_history      = list(s.hand_history or []),
        )
        try:
            save_tournament(record)
        except Exception:
            pass

    def _show_result(self) -> None:
        """Pop the APT-style tournament result dialog after bust-out."""
        s = self.session
        cfg: MttConfig = s.config  # type: ignore
        if cfg is None:
            return
        # Derive finish position from FieldSimulator if available
        sim: FieldSimulator | None = s.field_sim
        if sim is not None:
            finish = sim.finish_for_hero()
        elif s.busted:
            finish = max(1, int(s.field_size * 0.5))
        elif s.hero_stack >= 2 * s.starting_stack:
            finish = max(1, int(s.field_size * 0.15))
        else:
            finish = max(1, int(s.field_size * 0.35))
        paid_places = max(2, int(s.field_size * 0.15))
        cashed = finish <= paid_places
        pool   = cfg.buyin * cfg.field_size * 0.93
        payout = 0.0
        if cashed:
            pcts = [0.22, 0.15, 0.11, 0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.02]
            idx  = min(finish - 1, len(pcts) - 1)
            payout = round(pool * pcts[idx], 2)
        # Pick luck rating from how many ICM punts (proxy for variance)
        luck = "unlucky" if s.icm_punts >= 2 else \
               "lucky"   if (s.correct / max(1, s.decisions)) > 0.7 else "neutral"
        dlg = TournamentResultDialog(
            self,
            tournament_name = cfg.tournament_name,
            final_place     = finish,
            field_size      = cfg.field_size,
            skill_level     = cfg.skill_level,
            skill_style     = cfg.skill_style,
            buyin           = cfg.buyin,
            starting_stack  = cfg.starting_stack,
            time_per_level  = cfg.minutes_per_level,
            hero_payout     = payout,
            prize_pool      = pool,
            all_in_luck     = luck,
            hero_name       = "uygar",
        )
        dlg.view_report_requested.connect(self._on_view_report)
        dlg.exec()

    def _on_view_report(self) -> None:
        """Bridge: 'Session Report' button → navigate to Reports screen."""
        # Find the parent main window's navigate function
        win = self.window()
        if hasattr(win, "navigate"):
            win.navigate("Reports")

    def _open_archive(self) -> None:
        """Pop a simple list of past tournaments."""
        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem
        records = load_archive()
        dlg = QDialog(self)
        dlg.setWindowTitle("📁  Past Tournaments")
        dlg.setMinimumSize(640, 480)
        dlg.setStyleSheet(f"QDialog{{background:#0A0E14;}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 14, 16, 14)
        hdr = QLabel(f"♠ {len(records)} kayıtlı turnuva")
        hdr.setStyleSheet(f"color:{_C_TEXT};font-size:16px;font-weight:800;")
        lay.addWidget(hdr)
        lst = QListWidget()
        lst.setStyleSheet(
            f"QListWidget{{background:{_C_CARD};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;font-size:12px;}}"
            f"QListWidget::item{{padding:8px 10px;border-bottom:1px solid {_C_BORDER};}}"
            f"QListWidget::item:selected{{background:#0D2030;color:{_C_CYAN};}}"
        )
        if not records:
            placeholder = QLabel("Henüz bir turnuva tamamlanmamış. ▶ New Tournament ile başla.")
            placeholder.setStyleSheet(f"color:{_C_MUTED};font-size:13px;padding:24px;")
            placeholder.setAlignment(Qt.AlignCenter)
            lay.addWidget(placeholder)
        else:
            for r in records:
                tag = "💰 ITM" if r.cashed else "❌ Bust"
                hh_count = len(r.hand_history) if r.hand_history else 0
                line = (
                    f"{r.ended_at[:16]}  ·  {r.tournament_name}  ·  "
                    f"{r.field_size} oyuncu / ${r.buyin:.0f}  ·  "
                    f"{r.skill_style}/{r.skill_level}\n"
                    f"   {tag}  finish #{r.finish_position}  "
                    f"·  payout ${r.payout:.0f}  ROI {r.roi_pct:+.1f}%  "
                    f"·  accuracy {r.accuracy}%  ·  {hh_count} el oynandı  ·  {r.leak_summary}"
                )
                item = QListWidgetItem(line)
                item.setData(Qt.UserRole, r)
                lst.addItem(item)
            lst.itemDoubleClicked.connect(self._open_hand_history)
            lay.addWidget(lst)
            hint = QLabel("💡 Bir turnuvanın detaylı el geçmişini görmek için satıra çift tıkla.")
            hint.setStyleSheet(f"color:{_C_MUTED};font-size:11px;padding:4px;")
            lay.addWidget(hint)
        close = QPushButton("Kapat")
        close.setFixedHeight(34)
        close.setStyleSheet(
            f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            f"border-radius:6px;padding:0 18px;}}"
        )
        close.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        dlg.exec()

    def _open_hand_history(self, item) -> None:
        """Phase 3 — open a detailed hand-history viewer for a saved tournament."""
        from PySide6.QtWidgets import QDialog, QListWidget, QListWidgetItem
        r = item.data(Qt.UserRole)
        if r is None or not r.hand_history:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{r.tournament_name} — El Geçmişi ({len(r.hand_history)} el)")
        dlg.setMinimumSize(820, 560)
        dlg.setStyleSheet(f"QDialog{{background:#0A0E14;}}")
        v = QVBoxLayout(dlg); v.setContentsMargins(16, 14, 16, 14); v.setSpacing(8)

        hdr = QLabel(
            f"{r.tournament_name}  ·  finish #{r.finish_position}/{r.field_size}  ·  "
            f"payout ${r.payout:.0f}  ·  ROI {r.roi_pct:+.1f}%"
        )
        hdr.setStyleSheet(f"color:{_C_TEXT};font-size:14px;font-weight:700;")
        v.addWidget(hdr)

        lst = QListWidget()
        lst.setStyleSheet(
            f"QListWidget{{background:{_C_CARD};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;font-size:12px;"
            f"font-family:'SF Mono', Monaco, monospace;}}"
            f"QListWidget::item{{padding:6px 10px;border-bottom:1px solid {_C_BORDER};}}"
            f"QListWidget::item:selected{{background:#0D2030;color:{_C_CYAN};}}"
        )
        for h in r.hand_history:
            delta = h.get("hero_stack_out", 0) - h.get("hero_stack_in", 0)
            sign  = "+" if delta >= 0 else ""
            won   = "🏆" if h.get("hero_won") else "  "
            line = (
                f"#{h.get('hand_no', 0):>3}  L{h.get('level', 1):<2}  "
                f"{h.get('blinds', ''):<10}  {h.get('hero_pos', '??'):<4}  "
                f"{h.get('hero_cards', '????'):<6}  "
                f"board: {(h.get('board') or '—'):<14}  "
                f"pot {h.get('pot_final', 0):>5.0f}  "
                f"stack {h.get('hero_stack_out', 0):>7,.0f}  "
                f"{sign}{delta:>7,.0f}  {won}"
            )
            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, h)
            lst.addItem(item)
        # Double-click a hand line → open detailed Hand Review dialog
        lst.itemDoubleClicked.connect(
            lambda it, tn=r.tournament_name: self._open_hand_review(it, tn)
        )
        v.addWidget(lst, 1)
        # Hint
        hint = QLabel("💡 Bir ele çift tıkla → kart-kart detaylı review")
        hint.setStyleSheet(f"color:{_C_MUTED};font-size:11px;padding:4px;")
        v.addWidget(hint)

        close = QPushButton("Kapat")
        close.setFixedHeight(34)
        close.setStyleSheet(
            f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:6px;padding:0 18px;}}"
        )
        close.clicked.connect(dlg.accept)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(close)
        v.addLayout(row)
        dlg.exec()

    def _open_hand_review(self, item, tournament_name: str = "") -> None:
        """Drill-down review for a single hand (per-hand replay equivalent)."""
        from app.ui.components.hand_review_dialog import HandReviewDialog
        hand_record = item.data(Qt.UserRole)
        if not hand_record:
            return
        dlg = HandReviewDialog(self, hand_record, tournament_name=tournament_name)
        dlg.drill_requested.connect(self._drill_from_hand)
        dlg.exec()

    def _drill_from_hand(self, hand_record: dict) -> None:
        """User clicked 'Bu Spotu Drill Et' in HandReviewDialog → Spot Trainer."""
        pos = hand_record.get("hero_pos", "BTN")
        # Build a synthetic leak signature so Spot Trainer picks up the spot
        sig = f"{pos} / SRP / call"   # generic fallback
        self.state.active_leak_signature = sig
        win = self.window()
        if hasattr(win, "navigate"):
            win.navigate("Spot Practice Trainer")

    # ── blind helpers ──────────────────────────────────────────────────────
    def _blinds(self) -> tuple[int, int, int]:
        cfg = self.session.config
        bb_ante = bool(cfg.bb_ante) if cfg is not None else True
        return _blind_at(self.session.level, self.session.speed,
                         starting_stack=self.session.starting_stack or 20_000,
                         bb_ante=bb_ante)

    def _advance_level(self) -> None:
        self.session.hands_this_level += 1
        if self.session.hands_this_level >= self.session.hands_per_level:
            self.session.hands_this_level = 0
            self.session.level += 1

    # ── deal hand ─────────────────────────────────────────────────────────
    def _deal_hand(self) -> None:
        if self.session.busted:
            return
        sb, bb, ante = self._blinds()
        n = self.session.num_players
        # Reuse the same PokerGame instance across hands so dealer_idx
        # auto-rotates and hero plays every position. Only re-create on
        # player-count change, level change (blinds update) or first hand.
        recreate = (
            self.game is None
            or getattr(self, "_last_blinds", None) != (sb, bb)
            or self.game.num_players != n
        )
        if recreate:
            # Preserve hero's actual stack and dealer rotation across recreation
            prev_dealer = getattr(self.game, "dealer_idx", -1) if self.game else -1
            # Build per-seat archetype map from configured bot mix (seat 0 = hero)
            bot_mix = self.session.bot_mix or []
            per_seat = {}
            for seat_idx in range(1, n):
                if bot_mix:
                    per_seat[seat_idx] = bot_mix[(seat_idx - 1) % len(bot_mix)]
            default_arch = bot_mix[0] if bot_mix else "Balanced Reg"
            # Pull APT-style names from the field simulator's name pool
            bot_names: dict[int, str] = {}
            sim: FieldSimulator | None = self.session.field_sim
            if sim is not None and sim.players:
                for seat_idx in range(1, n):
                    vp = sim.players[(seat_idx - 1) % len(sim.players)]
                    bot_names[seat_idx] = vp.name
            self.game = PokerGame(
                num_players      = n,
                starting_stack   = float(self.session.hero_stack),
                small_blind      = float(sb),
                big_blind        = float(bb),
                hero_seat        = 0,
                bot_archetype    = default_arch,
                bot_archetypes   = per_seat,
                bot_names        = bot_names,
            )
            # If we're recreating mid-tournament (blinds change), advance dealer
            # to where it left off + 1, otherwise random start so first hand isn't always SB
            import random
            if prev_dealer >= 0:
                self.game.dealer_idx = (prev_dealer + 1) % n
            else:
                # Pick a random starting button so the first hand isn't always BTN→SB hero
                self.game.dealer_idx = random.randint(0, n - 1)
            self._last_blinds = (sb, bb)
        hand = self.game.start_hand()
        self.session.hands_played += 1
        self._advance_level()
        self._answered_this_hand = False
        self._fb.setMaximumHeight(0)
        self._update_ctx()
        self._refresh_table(hand)
        self._show_hand_cards(hand)
        self._render_actions(hand)

    # ── table + cards ──────────────────────────────────────────────────────
    def _refresh_table(self, hand: HandState) -> None:
        self.live_table.update_state(hand)
        # Push live tournament status (field simulator) to the table overlay
        sim: FieldSimulator | None = self.session.field_sim
        if sim is not None:
            leader_name, leader_stack = sim.chip_leader
            self.live_table.update_field_status(
                players_left=sim.players_left,
                total=self.session.field_size,
                avg_stack=sim.avg_stack,
                leader_name=leader_name,
                leader_stack=leader_stack,
            )

    def _show_hand_cards(self, hand: HandState) -> None:
        # Hero hole cards
        _clear_layout(self._hero_cards_row)
        hero = hand.hero
        if hero and hero.hole_cards:
            for c in hero.hole_cards:
                self._hero_cards_row.addWidget(CardView(c.display))
        else:
            for _ in range(2):
                self._hero_cards_row.addWidget(CardView("", face_down=True))

        # Board / community cards
        _clear_layout(self._board_row)
        community = list(hand.community) if hand.community else []
        for c in community:
            self._board_row.addWidget(CardView(c.display))
        # Pad with placeholders so the board area shows what's coming
        for _ in range(5 - len(community)):
            placeholder = QLabel("⬚")
            placeholder.setFixedSize(52, 72)
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color:#374151;font-size:28px;background:#0A0F16;border:1px dashed #1F2937;border-radius:6px;")
            self._board_row.addWidget(placeholder)

        # Context label
        sb, bb, _ = self._blinds()
        hero_pos = hand.hero.position if hand.hero else "??"
        self._spot_ctx.setText(
            f"L{self.session.level} · {sb}/{bb}  ·  {hero_pos}  ·  "
            f"Stack {self.session.hero_stack:,}  ·  Hand #{self.session.hands_played}\n"
            f"Street: {hand.street.name.title()}  ·  Pot: {hand.pot:.0f}"
        )

    # ── action buttons ─────────────────────────────────────────────────────
    def _render_actions(self, hand: HandState) -> None:
        _clear_layout(self._act_layout)
        self._action_btns = []
        if hand.is_complete or not self.game.is_waiting_for_hero:
            # Hand ended without hero needing to act — next hand
            self._on_hand_done(hand)
            return
        hero_idx = hand.hero_idx
        valid = hand.get_valid_actions(hero_idx)
        for action_type, min_amt, max_amt in valid:
            label = _action_display(action_type, hand)
            btn   = QPushButton(label)
            btn.setStyleSheet(_btn_qss(action_type))
            btn.clicked.connect(lambda _, at=action_type: self._hero_acts(at))
            self._act_layout.addWidget(btn)
            self._action_btns.append((btn, action_type))

    # ── hero decision ──────────────────────────────────────────────────────
    def _hero_acts(self, action_type: ActionType) -> None:
        if not self.game or self._answered_this_hand:
            return
        self._answered_this_hand = True
        hand = self.game.current_hand

        # Build pseudo-spot for GTO analysis
        spot    = self._hand_to_spot(hand)
        act_str = action_type.value
        gto     = compare_action(spot, act_str)
        self.session.decisions += 1
        is_ok   = gto["is_correct"]
        ev_loss = gto["ev_loss"]
        best    = gto["best_action"]

        if is_ok:
            self.session.correct += 1
        else:
            self.session.total_ev_loss += ev_loss
            why = self._why(hand, act_str, gto)
            m   = MistakeEntry(
                hand_no    = self.session.hands_played,
                street     = hand.street.name.lower(),
                hero_action= act_str,
                gto_action = best,
                ev_loss    = ev_loss,
                why        = why,
            )
            self.session.mistakes.append(m)
            if ev_loss > 1.0 and self.session.players_left <= self.session.field_size * 0.15:
                self.session.icm_punts += 1
            self._add_to_log(m)
            # Persist to global My Mistakes queue
            try:
                from datetime import datetime
                hero = hand.hero
                hero_cards = "".join(c.display for c in hero.hole_cards) if hero and hero.hole_cards else ""
                sb, bb, _ = self._blinds()
                stack_bb = hero.stack / bb if hero else 0
                add_mistake(MqEntry(
                    id           = new_mistake_id(),
                    logged_at    = datetime.now().isoformat(timespec="seconds"),
                    context      = "tournament",
                    position     = hero.position if hero else "",
                    stack_bb     = round(stack_bb, 1),
                    pot_type     = "3BP" if hand.current_bet > 3 * bb else "SRP",
                    hero_cards   = hero_cards,
                    hero_action  = act_str.lower(),
                    gto_action   = best.lower(),
                    ev_loss      = round(ev_loss, 2),
                    why          = why,
                ))
            except Exception:
                pass

        # Show GTO % on buttons
        freq_map = {a["action"]: a["frequency"] for a in gto["solver"]["actions"]}
        for btn, at in self._action_btns:
            btn.setEnabled(False)
            freq = 0.0
            for ak, fv in freq_map.items():
                if ak.lower()[:4] == at.value.lower()[:4]:
                    freq = fv; break
            old = btn.text().split("\n")[0]
            btn.setText(f"{old}\n{freq*100:.1f}%")

        # Feedback panel
        self._fb.setMaximumHeight(9999)
        _clear_layout(self._fb_layout)
        self._draw_feedback(gto, act_str, hand)
        self._update_stats()

        # Apply action to engine and finish hand
        hand_after = self.game.hero_act(action_type)
        self._refresh_table(hand_after)
        # Refresh hero cards + board after streets advance so flop/turn/river show up
        self._show_hand_cards(hand_after)

        if hand_after.is_complete or not self.game.is_waiting_for_hero:
            self._on_hand_done(hand_after)

    def _on_hand_done(self, hand: HandState) -> None:
        hero = hand.hero
        if hero:
            self.session.hero_stack = max(0, int(hero.stack))

        # Capture hand record for archive (Phase 3)
        try:
            self._record_hand(hand)
        except Exception:
            pass

        # Background field simulation (Phase 2) — real eliminations
        sim: FieldSimulator | None = self.session.field_sim
        if sim is not None:
            sim.update_hero_stack(self.session.hero_stack)
            # Advance field every 10 hero hands (≈ 1 round of the rest of the field)
            if self.session.hands_played % 10 == 0:
                _, bb, _ = self._blinds()
                busted = sim.advance_round(big_blind=float(bb), hands_in_round=10)
                if busted:
                    self._log_elimination(len(busted), sim.players_left)
            self.session.players_left = sim.players_left
            # Table consolidation — as field shrinks, hero's table also
            # consolidates: 9-handed → 6-max → 4-max → 3-max → HU.
            # Real MTTs balance like this. Doesn't change hero's stack;
            # adjusts num_players for next deal.
            self._maybe_consolidate_table(sim.players_left)
            # Winner detection — if hero is the last one
            if sim.players_left <= 1 and self.session.hero_stack > 0:
                self._log_event("🏆  Turnuvayı kazandın!")
                QTimer.singleShot(600, self._bust)
                return

        self._update_ctx()
        if self.session.hero_stack <= 0:
            if sim is not None:
                sim.hero_busted_at(self.session.hands_played)
            QTimer.singleShot(400, self._bust)
        elif not self._answered_this_hand:
            QTimer.singleShot(300, self._deal_hand)

    def _record_hand(self, hand: HandState) -> None:
        """Append a HandRecord-shaped dict to the session history."""
        hero = hand.hero
        if hero is None:
            return
        sb, bb, _ = self._blinds()
        hero_cards = "".join(c.display for c in hero.hole_cards) if hero.hole_cards else ""
        board      = "".join(c.display for c in (hand.community or []))
        # Build a compact per-street action log from hand.actions
        actions_log = []
        for a in (getattr(hand, "actions", None) or []):
            atype = getattr(a, "action_type", None)
            verb  = getattr(atype, "value", str(atype)) if atype else "?"
            seat_idx = getattr(a, "player_idx", -1)
            seat_name = hand.players[seat_idx].name if 0 <= seat_idx < len(hand.players) else "?"
            seat_pos  = hand.players[seat_idx].position if 0 <= seat_idx < len(hand.players) else "?"
            street    = getattr(getattr(a, "street", None), "name", "?")
            amount    = getattr(a, "amount", 0)
            actions_log.append({
                "street": street, "pos": seat_pos, "name": seat_name,
                "action": verb, "amount": float(amount or 0),
            })
        record = {
            "hand_no":        self.session.hands_played,
            "level":          self.session.level,
            "blinds":         f"{sb}/{bb}",
            "hero_pos":       hero.position,
            "hero_cards":     hero_cards,
            "board":          board,
            "pot_final":      float(hand.pot),
            "hero_stack_in":  float(self.session.hero_stack) + float(hero.invested_this_hand or 0),
            "hero_stack_out": float(hero.stack),
            "hero_won":       hero.stack > self.session.hero_stack,
            "actions":        actions_log,
            "showdown":       hand.winner_hand_name or "",
        }
        self.session.hand_history.append(record)

    def _maybe_consolidate_table(self, players_left: int) -> None:
        """As the field shrinks, reduce hero's table size to match real MTT
        balancing. Triggers a recreate of the PokerGame on next deal.

        Bands:
          >= 60 players left → 9-max
          25 to 59           → 6-max
          10 to 24           → 4-max
          ≤ 9                → final table 9-max (hero is at final)
          ≤ 4 (with hero)    → 3-max / HU as needed
        """
        if players_left >= 60:
            target = 9
        elif players_left >= 25:
            target = 6
        elif players_left > 9:
            target = 4
        elif players_left >= 4:
            target = min(9, players_left)
        else:
            target = max(2, players_left)
        current = self.session.num_players
        if target != current and target >= 2:
            old = current
            self.session.num_players = target
            # Notify via log + toast (only once per consolidation step)
            self._log_event(
                f"🔀 Masa birleşmesi: {old}-max → {target}-max (kalan: {players_left})"
            )
            try:
                from app.ui.components.toast import Toast
                Toast.show_info(
                    self.window(),
                    f"🔀 Masa {old}-max → {target}-max  ·  Kalan oyuncu: {players_left}"
                )
            except Exception:
                pass

    def _log_elimination(self, count: int, players_left: int) -> None:
        """Emit an entry into the live log when virtual players bust.

        Includes up to 3 example names (sampled from the field) so the user
        sees real eliminations like 'Jim Spears, Lena Voss out — 76 left'.
        """
        sim: FieldSimulator | None = self.session.field_sim
        sample_names: list[str] = []
        if sim is not None:
            # Recently busted players (highest bust_hand first)
            busted_recent = sorted(
                [p for p in sim.players if not p.alive],
                key=lambda p: -p.bust_hand,
            )[:count]
            sample_names = [p.name for p in busted_recent[:3]]
        names_part = ", ".join(sample_names) if sample_names else f"{count} oyuncu"
        suffix = "" if count <= 3 else f" (+{count-3} more)"
        msg = f"💥  {names_part}{suffix} elendi  ·  kalan: {players_left:,}"
        self._log_event(msg, accent="#F87171")

    def _log_event(self, text: str, accent: Optional[str] = None) -> None:
        """Insert an event line at the TOP of the mistake log panel."""
        if not hasattr(self, "_log_vbox"):
            return
        from PySide6.QtWidgets import QLabel
        lbl = QLabel(text)
        color = accent or _C_MUTED
        lbl.setStyleSheet(
            f"QLabel{{color:{color};font-size:11px;font-weight:600;"
            f"padding:6px 10px;background:{_C_CARD};border-radius:5px;"
            f"border-left:3px solid {color};}}"
        )
        # Newest event on top
        self._log_vbox.insertWidget(0, lbl)

    # ── feedback panel ─────────────────────────────────────────────────────
    def _draw_feedback(self, gto: dict, hero_action: str, hand: HandState) -> None:
        is_ok   = gto["is_correct"]
        ev_loss = gto["ev_loss"]
        best    = gto["best_action"]

        # Verdict row
        row = QHBoxLayout()
        icon = QLabel("✅" if is_ok else "❌")
        icon.setStyleSheet("font-size:18px;")
        if is_ok:
            msg = QLabel(f"Doğru!  EV kayıp: {ev_loss:.2f}bb")
            msg.setStyleSheet(f"color:{_C_GREEN};font-size:13px;font-weight:700;")
        else:
            msg = QLabel(f"Hatalı  —  Sen: {hero_action}  |  GTO: {best}  |  EV kayıp: {ev_loss:.2f}bb")
            msg.setStyleSheet(f"color:{_C_RED};font-size:13px;font-weight:700;")
        next_btn = QPushButton("Sonraki El →")
        next_btn.setFixedHeight(32)
        next_btn.setCursor(Qt.PointingHandCursor)
        next_btn.setToolTip("Klavye: Space / Enter / N — veya panele tıkla")
        next_btn.setStyleSheet(
            f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:7px;"
            "font-weight:800;font-size:12px;padding:4px 14px;border:none;}"
        )
        next_btn.clicked.connect(self._next_hand)
        row.addWidget(icon); row.addWidget(msg, 1); row.addWidget(next_btn)
        self._fb_layout.addLayout(row)

        # Subtle hint about multi-modal input
        hint = QLabel("⌨  Space / Enter / N  ·  veya panele tıkla  ·  veya butona bas")
        hint.setStyleSheet(
            f"color:{_C_MUTED};font-size:10px;font-style:italic;padding:2px 4px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        self._fb_layout.addWidget(hint)

        if not is_ok:
            why_lbl = QLabel(self._why(hand, hero_action, gto))
            why_lbl.setWordWrap(True)
            why_lbl.setStyleSheet(
                f"QLabel{{background:{_C_BG};color:{_C_TEXT};font-size:12px;"
                f"padding:8px 12px;border-radius:7px;border:1px solid {_C_BORDER};}}"
            )
            self._fb_layout.addWidget(why_lbl)

        # GTO frequency pills
        freq_row = QHBoxLayout()
        for a_dict in gto["solver"]["actions"]:
            freq  = a_dict["frequency"]
            act   = a_dict["action"]
            ev    = a_dict["ev"]
            pct   = f"{freq*100:.1f}%"
            color = _C_GREEN if freq >= 0.5 else (_C_AMBER if freq >= 0.2 else _C_MUTED)
            pill  = QLabel(f"{act.upper()}\n{pct}\nEV {ev:+.2f}bb")
            pill.setAlignment(Qt.AlignCenter)
            pill.setStyleSheet(
                f"QLabel{{background:{_C_BG};border:1.5px solid {color};"
                f"color:{color};border-radius:7px;padding:5px 10px;"
                "font-size:11px;font-weight:700;}"
            )
            freq_row.addWidget(pill)
        self._fb_layout.addLayout(freq_row)

        # Auto-advance: if toggle is ON, schedule the next hand automatically
        if getattr(self, "_auto_advance", False):
            QTimer.singleShot(self._auto_delay_ms, self._next_hand)

    def _next_hand(self) -> None:
        self._fb.setMaximumHeight(0)
        if self.session.busted or not self.session.running:
            return
        if self.session.hero_stack <= 0:
            self._bust(); return
        self._deal_hand()

    def _kbd_next_hand(self) -> None:
        """Keyboard shortcut → next hand. Only fires when feedback panel is
        visible (otherwise Space/Enter shouldn't deal a hand)."""
        if self._fb.maximumHeight() > 0:
            self._next_hand()

    def _toggle_auto(self) -> None:
        """Auto-advance mode — hero feedback shows briefly then 'Sonraki El' fires."""
        self._auto_advance = self.auto_btn.isChecked()
        self.auto_btn.setText("⏵  Auto: AÇIK" if self._auto_advance else "⏵  Auto: KAPALI")
        if self._auto_advance and self._answered_this_hand:
            # If we're idle on a feedback panel right now, schedule advance
            QTimer.singleShot(self._auto_delay_ms, self._next_hand)

    # ── helpers ────────────────────────────────────────────────────────────
    def _hand_to_spot(self, hand: HandState) -> dict:
        """Build a pseudo-spot dict for GTO analysis."""
        sb, bb, ante = self._blinds()
        hero     = hand.hero
        hero_pos = hero.position if hero else "BTN"
        stack_bb = int(self.session.hero_stack / max(bb, 1))
        street   = hand.street.name.lower()
        pot_bb   = round((hand.pot + sum(p.current_bet for p in hand.players)) / max(bb, 1), 1)
        cards    = " ".join(c.display for c in hero.hole_cards) if (hero and hero.hole_cards) else "?? ??"
        board    = " ".join(c.display for c in hand.community) if hand.community else ""

        # Try to find matching drill for richer GTO data
        for d in self._drills:
            if (d.get("street") == street
                    and d.get("position") == hero_pos
                    and abs(d.get("stack_bb", 100) - stack_bb) < 25):
                return d

        # Generic fallback
        return {
            "id":           f"live-{self.session.hands_played}",
            "title":        f"Live {hero_pos} {stack_bb}bb {street}",
            "format":       "MTT",
            "table":        f"{self.session.num_players}-max",
            "street":       street,
            "position":     hero_pos,
            "stack_bb":     stack_bb,
            "pot_bb":       pot_bb,
            "hero_cards":   cards,
            "board":        board,
            "board_texture":"dynamic",
            "pot_type":     "SRP",
            "action_history": f"L{self.session.level} · {sb}/{bb}",
            "options":      ("fold", "call", "raise", "jam"),
            "best_action":  "call",
            "base_ev":      1.0,
            "range_advantage": "Neutral ranges",
            "nut_advantage":   "Shared nut density",
            "icm":          "bubble" if self.session.players_left <= max(1, self.session.field_size // 10) else "off",
            "source_confidence": "Mock/demo solver",
        }

    def _why(self, hand: HandState, hero_action: str, gto: dict) -> str:
        best      = gto["best_action"]
        ev_loss   = gto["ev_loss"]
        best_freq = gto["best_frequency"]
        hero_ev   = gto["hero_ev"]
        best_ev   = gto["best_ev"]
        sb, bb, _ = self._blinds()
        stack_bb  = self.session.hero_stack / max(bb, 1)
        icm_near  = self.session.players_left <= max(1, self.session.field_size // 7)

        lines = [f"💡 El #{self.session.hands_played} — GTO Analiz"]
        ha = hero_action.lower(); ba = best.lower()

        if "fold" in ha and "fold" not in ba:
            lines.append(f"• Aşırı fold: GTO burada {ba.upper()} diyor ({best_freq*100:.0f}%).")
            lines.append(f"  {stack_bb:.0f}bb stack ile bu elde devam etmek gerekiyor.")
        elif ha in ("call",) and ba in ("raise","bet","jam","all_in","3bet","4bet"):
            lines.append(f"• Çok pasif: GTO {ba.upper()} tercih ediyor ({best_freq*100:.0f}%).")
            lines.append("  Pot inşa et ve daha az öngörülebilir ol.")
        elif ha in ("raise","bet","jam","all_in") and ba in ("check","call","fold"):
            lines.append(f"• Fazla agresif: GTO {ba.upper()} diyor ({best_freq*100:.0f}%).")
            lines.append("  Bu elde range avantajı yok veya fold equity yetersiz.")
        else:
            lines.append(f"• GTO optimal: '{best.upper()}' ({best_freq*100:.0f}%)")

        lines.append(f"• EV: Seçimin {hero_ev:+.2f}bb | GTO {best_ev:+.2f}bb | Fark: {ev_loss:.2f}bb kayıp")

        if icm_near:
            lines.append(f"⚠️  ICM: {self.session.players_left} oyuncu kaldı. Para sırası yakın — cEV değil $EV hesapla!")

        if ev_loss > 1.5:
            lines.append("🔴 Yüksek kayıp — bu spot'u drill queue'ya ekle.")

        return "\n".join(lines)

    def _accuracy(self) -> int:
        if not self.session.decisions:
            return 0
        return int(100 * self.session.correct / self.session.decisions)

    def _bust(self) -> None:
        self.session.busted  = True
        self.session.running = False
        _clear_layout(self._act_layout)
        finish = QLabel(
            f"💀  Bust!  —  {self.session.players_left}. sıra\n"
            f"Eller: {self.session.hands_played}  ·  Kararlar: {self.session.decisions}  ·  "
            f"Doğruluk: {self._accuracy()}%  ·  Hatalar: {len(self.session.mistakes)}"
        )
        finish.setStyleSheet(f"color:{_C_AMBER};font-size:14px;font-weight:700;")
        finish.setAlignment(Qt.AlignCenter)
        self._act_layout.addWidget(finish)
        again = QPushButton("🔄  Tekrar Oyna")
        again.setStyleSheet(
            f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:8px;"
            "font-weight:800;font-size:13px;padding:6px 20px;border:none;}"
        )
        again.clicked.connect(self._reset)
        self._act_layout.addWidget(again)
        self.coach_message.emit(
            f"Turnuva bitti: {self.session.players_left}. yer. "
            f"{len(self.session.mistakes)} hata, {self._accuracy()}% doğruluk. "
            "'Drill My Mistakes' ile çalış!"
        )

    # ── context + stats ────────────────────────────────────────────────────
    def _update_ctx(self) -> None:
        s = self.session
        sb, bb, ante = self._blinds()
        m = int(s.hero_stack / max(sb + bb + ante * s.num_players, 1))
        self._ctx["Level"].setText(f"L{s.level}")
        self._ctx["Blinds"].setText(f"{sb}/{bb}" + (f"/a{ante}" if ante else ""))
        self._ctx["Hero Stack"].setText(f"{s.hero_stack:,}")
        self._ctx["Stack bb"].setText(f"{int(s.hero_stack / max(bb, 1))}bb")
        self._ctx["M-ratio"].setText(str(m))
        self._ctx["Players"].setText(f"{s.players_left}/{s.field_size}")
        self._ctx["Hands"].setText(str(s.hands_played))

    def _update_stats(self) -> None:
        s = self.session
        self._stat["Decisions"].setText(str(s.decisions))
        self._stat["Accuracy"].setText(f"{self._accuracy()}%")
        avg = (s.total_ev_loss / max(len(s.mistakes), 1)) if s.mistakes else 0.0
        self._stat["Avg EV Loss"].setText(f"{avg:.2f}bb")
        self._stat["ICM Punts"].setText(str(s.icm_punts))

    # ── mistake log ───────────────────────────────────────────────────────
    def _add_to_log(self, m: MistakeEntry) -> None:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{_C_CARD};border-radius:6px;border:1px solid {_C_BORDER};}}"
        )
        cv = QVBoxLayout(card); cv.setContentsMargins(8,5,8,5); cv.setSpacing(2)
        hdr = QHBoxLayout()
        hdr.addWidget(_small(f"El #{m.hand_no}  ·  {m.street.title()}"))
        hdr.addStretch(1)
        hdr.addWidget(_small_colored(f"-{m.ev_loss:.2f}bb", _C_RED))
        cv.addLayout(hdr)
        cv.addWidget(_bold(f"Sen: {m.hero_action.upper()}  →  GTO: {m.gto_action.upper()}"))
        short = m.why.split("\n")[1].lstrip("•").strip() if "\n" in m.why else ""
        if short:
            lbl = QLabel(short); lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color:{_C_MUTED};font-size:11px;")
            cv.addWidget(lbl)
        self._log_vbox.insertWidget(0, card)

    # ── drill queue ────────────────────────────────────────────────────────
    def _queue_mistakes(self) -> None:
        if not self.session.mistakes:
            self.coach_message.emit("Hata yok — mükemmel oyun! 🎉"); return
        ids = []
        for m in self.session.mistakes[-5:]:
            for d in self._drills:
                if d.get("street") == m.street:
                    ids.append(d["id"]); break
        if ids:
            if not hasattr(self.state, "pending_spot_queue"):
                self.state.pending_spot_queue = []
            self.state.pending_spot_queue = ids + list(self.state.pending_spot_queue)
            self.coach_message.emit(
                f"{len(ids)} hatalı spot Spot Trainer kuyruğuna eklendi. "
                "Sol menüden 'Spot Practice Trainer' → Devam et!"
            )


# ── tiny helpers ──────────────────────────────────────────────────────────

def _lbl(text: str) -> QLabel:
    l = QLabel(text); l.setStyleSheet(f"color:{_C_MUTED};font-size:12px;"); return l

def _section(text: str) -> QLabel:
    l = QLabel(text); l.setStyleSheet(f"color:{_C_TEXT};font-weight:700;font-size:13px;"); return l

def _small(text: str) -> QLabel:
    l = QLabel(text); l.setStyleSheet(f"color:{_C_MUTED};font-size:10px;"); return l

def _small_colored(text: str, color: str) -> QLabel:
    l = QLabel(text); l.setStyleSheet(f"color:{color};font-size:10px;font-weight:700;"); return l

def _bold(text: str) -> QLabel:
    l = QLabel(text); l.setStyleSheet(f"color:{_C_TEXT};font-size:12px;font-weight:600;"); return l

def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w  = item.widget(); cl = item.layout()
        if w:  w.deleteLater()
        if cl: _clear_layout(cl)
