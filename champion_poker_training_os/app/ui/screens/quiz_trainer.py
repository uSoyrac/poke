"""Preflop Range Quiz — random spot drill ekranı.

Akış:
1. Random spot üretilir: position × stack × scenario × hand
2. Hero'ya el + bağlam gösterilir
3. 5sn geri sayım (zorluk artarsa kısalır)
4. Hero FOLD / CALL / RAISE seçer (veya süre dolar = FOLD)
5. GTO ile karşılaştırma, feedback gösterilir
6. Stats güncellenir (correct/total, streak, by-position breakdown)

Spaced repetition için yanlış yapılan spotlar bir queue'ya eklenir
ve istatistik olarak gösterilir (DB entegrasyonu sonraki iterasyonda).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QVBoxLayout, QWidget,
)

from app.poker.gto_ranges import (
    POSITIONS_6MAX, STACK_DEPTHS, get_action,
)
from app.ui.components.card_view import TwoCardHand


# ── COLOR PALETTE ────────────────────────────────────────────────────
COLOR_RAISE = "#DC2626"
COLOR_CALL  = "#10B981"
COLOR_FOLD  = "#2563EB"
COLOR_GOOD  = "#10B981"
COLOR_BAD   = "#DC2626"
COLOR_MUTED = "#94A3B8"
COLOR_INK   = "#FAFAFA"
COLOR_BG    = "#0F1419"
COLOR_CARD  = "#111827"
COLOR_LINE  = "#1F2937"


@dataclass
class QuizSpot:
    """Tek bir quiz sorusu."""
    position: str
    stack_depth: int
    scenario: str
    hand: str
    action: dict   # {"raise": pct, "call": pct, "fold": pct}
    vs_position: str | None = None   # vs-RFI / vs-3bet için opener pozisyonu

    @property
    def correct_action(self) -> str:
        """En yüksek frekanslı aksiyonu döndür."""
        r = self.action.get("raise", 0)
        c = self.action.get("call", 0)
        f = self.action.get("fold", 0)
        if r >= c and r >= f:
            return "raise"
        if c >= f:
            return "call"
        return "fold"

    @property
    def is_mixed(self) -> bool:
        """Spot mixed strategy mi?"""
        vals = [self.action.get(k, 0) for k in ("raise", "call", "fold")]
        non_zero = sum(1 for v in vals if 0 < v < 100)
        return non_zero >= 2

    def ev_loss_bb(self, user_action: str) -> float:
        """Seçilen aksiyonun tahmini EV kaybı (bb).  🟠 APPROX.

        Solver-exact EV yok → GTO frekans boşluğundan heuristik. Dominant
        aksiyonu seçersen 0; sıfır-frekanslı aksiyon seçersen aksiyon-tipine
        göre (chip-commit eden raise en pahalı) ölçeklenir.
        """
        a = self.action
        best = max(a.get("raise", 0), a.get("call", 0), a.get("fold", 0))
        chosen = a.get(user_action, 0)
        gap = max(0.0, best - chosen) / 100.0
        if gap <= 0:
            return 0.0
        # Riske atılan çip aksiyon-tipine + senaryoya bağlı.
        if user_action == "raise":
            if self.scenario in ("Push/Fold", "Jam"):
                base = min(self.stack_depth, 15.0)   # jam = stack riski
            elif self.scenario == "vs 3-bet":
                base = 4.0                            # 4-bet/jam — orta
            else:   # RFI / vs RFI — sadece açış boyutu riski
                base = 2.0
        elif user_action == "call":
            base = 2.5
        else:   # fold — +EV spot'u pas geçmek
            base = 1.5
        return round(gap * base, 2)

    def difficulty_rating(self) -> float:
        """Spot zorluğu (ELO opponent rating)."""
        d = 1450.0
        if self.is_mixed:
            d += 180
        if self.scenario == "vs 3-bet":
            d += 120
        elif self.scenario == "vs RFI":
            d += 60
        if self.stack_depth <= 20:
            d += 60
        return d


@dataclass
class QuizStats:
    """Bu seansın quiz istatistikleri."""
    total: int = 0
    correct: int = 0
    streak: int = 0
    best_streak: int = 0
    by_position: dict = field(default_factory=dict)  # pos → (total, correct)
    wrong_queue: List[QuizSpot] = field(default_factory=list)
    # PeakGTO-tarzı metrikler
    errors: int = 0
    ev_loss_total: float = 0.0       # seans toplam EV kaybı (bb)
    elo: float = 1500.0
    history: list = field(default_factory=list)  # son spotlar: dict chip'ler

    def record(self, spot: QuizSpot, is_correct: bool,
               user_action: str = "", ev_loss: float = 0.0) -> None:
        self.total += 1
        # ELO güncelle (spot zorluğuna karşı)
        D = spot.difficulty_rating()
        E = 1.0 / (1.0 + 10 ** ((D - self.elo) / 400.0))
        S = 1.0 if is_correct else 0.0
        self.elo += 24.0 * (S - E)

        if is_correct:
            self.correct += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.errors += 1
            self.streak = 0
            self.ev_loss_total += ev_loss
            # Yanlış answer queue'ya ekle (spaced repetition için)
            self.wrong_queue.append(spot)
            if len(self.wrong_queue) > 25:
                self.wrong_queue = self.wrong_queue[-20:]

        pt, pc = self.by_position.get(spot.position, (0, 0))
        self.by_position[spot.position] = (pt + 1, pc + (1 if is_correct else 0))

        # Action-history şeridi (son 16)
        self.history.append({
            "hand": spot.hand, "action": user_action,
            "correct": is_correct, "gto": spot.correct_action,
        })
        if len(self.history) > 16:
            self.history = self.history[-16:]

    @property
    def accuracy_pct(self) -> float:
        return 100 * self.correct / max(self.total, 1)


# ── MAIN SCREEN ──────────────────────────────────────────────────────
class QuizTrainerScreen(QWidget):
    """Preflop range drill — günde 15dk muscle memory training."""

    coach_message = Signal(str)

    # Zorluk seviyeleri (saniye)
    DIFFICULTY = {
        "Easy":   8,
        "Normal": 5,
        "Hard":   3,
        "Expert": 2,
    }

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.stats = QuizStats()
        self._current_spot: Optional[QuizSpot] = None
        self._answered = False
        self._countdown_remaining = 5
        self._countdown_total = 5
        self._mode_filter = {"position": "All", "scenario": "RFI",
                              "stack_depth": "All"}
        self._timer = QTimer(self)
        self._timer.setInterval(100)   # 10× per second
        self._timer.timeout.connect(self._on_tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(14)

        # Başlık + kısa açıklama
        title = QLabel("🎯  Preflop Range Quiz")
        title.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 22px; font-weight: 800;"
        )
        root.addWidget(title)
        subtitle = QLabel(
            "Random spot → 5 saniyede aksiyon seç → GTO ile karşılaştır.  "
            "Günde 15 dakika = preflop muscle memory."
        )
        subtitle.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 12px;")
        root.addWidget(subtitle)

        # Üst kontrol bar
        root.addLayout(self._build_controls())

        # PeakGTO-tarzı seans bar'ı (Hands · Correct · Errors · EV Loss · ELO)
        root.addWidget(self._build_session_bar())
        # Action-history şeridi (son spotlar, renkli chip)
        root.addWidget(self._build_history_strip())

        # Ana içerik: sol (spot card) + sağ (stats)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        splitter.addWidget(self._build_spot_card())
        splitter.addWidget(self._build_stats_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # İlk spotu hazırla ama sayacı BAŞLATMA — geri sayım yalnızca ekran
        # görünürken işler (showEvent). Aksi halde sekme arka plandayken sayaç
        # akar ve kullanıcı hep "SÜRE DOLDU"ya gelir.
        self._start_new_spot(start_timer=False)

    # ── VISIBILITY: sayaç yalnızca ekran görünürken çalışır ──────────────
    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        self._start_new_spot()           # her açılışta taze, canlı spot

    def hideEvent(self, ev) -> None:
        super().hideEvent(ev)
        self._timer.stop()

    # ── KONTROLLER ────────────────────────────────────────────────────
    def _build_controls(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(14)

        h.addWidget(self._chip_label("Difficulty"))
        self.diff_box = QComboBox()
        self.diff_box.addItems(list(self.DIFFICULTY.keys()))
        self.diff_box.setCurrentText("Normal")
        self.diff_box.currentTextChanged.connect(self._on_difficulty_changed)
        h.addWidget(self.diff_box)

        h.addWidget(self._chip_label("Position"))
        self.pos_filter = QComboBox()
        self.pos_filter.addItems(["All"] + POSITIONS_6MAX[:-1])  # exclude BB
        self.pos_filter.currentTextChanged.connect(
            lambda t: self._set_filter("position", t)
        )
        h.addWidget(self.pos_filter)

        h.addWidget(self._chip_label("Stack"))
        self.stack_filter = QComboBox()
        self.stack_filter.addItems(["All", "100bb", "60bb", "40bb", "20bb"])
        self.stack_filter.currentTextChanged.connect(
            lambda t: self._set_filter("stack_depth", t)
        )
        h.addWidget(self.stack_filter)

        h.addWidget(self._chip_label("Scenario"))
        self.scen_filter = QComboBox()
        self.scen_filter.addItems(["All", "RFI", "vs RFI", "vs 3-bet", "Push/Fold"])
        self.scen_filter.setCurrentText("RFI")   # _mode_filter default ile senkron
        self.scen_filter.currentTextChanged.connect(
            lambda t: self._set_filter("scenario", t)
        )
        h.addWidget(self.scen_filter)

        h.addStretch(1)

        # Skip butonu (cevap olmadan sonraki spot'a geç)
        skip_btn = QPushButton("⏭  Skip")
        skip_btn.setStyleSheet(self._btn_style(COLOR_MUTED, secondary=True))
        skip_btn.clicked.connect(self._start_new_spot)
        h.addWidget(skip_btn)

        return h

    def _chip_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 600; "
            f"text-transform: uppercase; letter-spacing: 1px;"
        )
        return lbl

    def _set_filter(self, key: str, val: str) -> None:
        self._mode_filter[key] = val

    def _on_difficulty_changed(self, level: str) -> None:
        self._countdown_total = self.DIFFICULTY.get(level, 5)
        if not self._answered:
            self._countdown_remaining = self._countdown_total

    # ── SESSION BAR (PeakGTO-tarzı) ───────────────────────────────────
    def _build_session_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 10px; }}"
        )
        h = QHBoxLayout(bar)
        h.setContentsMargins(18, 10, 18, 10)
        h.setSpacing(8)

        def metric(label):
            box = QVBoxLayout()
            box.setSpacing(1)
            cap = QLabel(label)
            cap.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 9px; "
                              f"font-weight: 700; letter-spacing: 1.2px;")
            val = QLabel("—")
            val.setStyleSheet(f"color: {COLOR_INK}; font-size: 17px; "
                              f"font-weight: 800; font-family: 'JetBrains Mono', monospace;")
            box.addWidget(cap)
            box.addWidget(val)
            wrap = QWidget()
            wrap.setLayout(box)
            return wrap, val

        w1, self.sb_hands = metric("HANDS")
        w2, self.sb_correct = metric("CORRECT")
        w3, self.sb_errors = metric("ERRORS")
        w4, self.sb_evloss = metric("EV LOSS")
        w5, self.sb_elo = metric("ELO")
        h.addWidget(w1)
        h.addStretch(1)
        h.addWidget(w2)
        h.addStretch(1)
        h.addWidget(w3)
        h.addStretch(1)
        h.addWidget(w4)
        h.addStretch(1)
        h.addWidget(w5)
        self._refresh_session_bar()
        return bar

    def _refresh_session_bar(self) -> None:
        s = self.stats
        self.sb_hands.setText(str(s.total))
        self.sb_correct.setText(str(s.correct))
        self.sb_correct.setStyleSheet(f"color: {COLOR_GOOD}; font-size: 17px; "
                                      f"font-weight: 800; font-family: monospace;")
        self.sb_errors.setText(str(s.errors))
        self.sb_errors.setStyleSheet(
            f"color: {COLOR_BAD if s.errors else COLOR_INK}; font-size: 17px; "
            f"font-weight: 800; font-family: monospace;")
        self.sb_evloss.setText(f"-{s.ev_loss_total:.2f}bb" if s.ev_loss_total else "0.00bb")
        self.sb_evloss.setStyleSheet(
            f"color: {COLOR_BAD if s.ev_loss_total > 0.5 else '#F59E0B' if s.ev_loss_total else COLOR_GOOD}; "
            f"font-size: 17px; font-weight: 800; font-family: monospace;")
        elo_int = int(round(s.elo))
        self.sb_elo.setText(str(elo_int))
        self.sb_elo.setStyleSheet(
            f"color: {COLOR_GOOD if elo_int >= 1500 else '#F59E0B'}; font-size: 17px; "
            f"font-weight: 800; font-family: monospace;")

    # ── ACTION HISTORY STRIP ──────────────────────────────────────────
    def _build_history_strip(self) -> QWidget:
        self._history_bar = QFrame()
        self._history_bar.setStyleSheet("QFrame { background: transparent; }")
        h = QHBoxLayout(self._history_bar)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(5)
        self._history_layout = h
        h.addStretch(1)
        self._refresh_history_strip()
        return self._history_bar

    def _refresh_history_strip(self) -> None:
        lay = self._history_layout
        # eski chip'leri temizle (son stretch hariç)
        while lay.count() > 0:
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.stats.history:
            ph = QLabel("Henüz el yok — ilk spotu oyna.")
            ph.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
            lay.addWidget(ph)
            lay.addStretch(1)
            return
        for h in self.stats.history:
            color = COLOR_GOOD if h["correct"] else COLOR_BAD
            chip = QLabel(f"{h['hand']}")
            chip.setAlignment(Qt.AlignCenter)
            chip.setFixedHeight(26)
            chip.setStyleSheet(
                f"QLabel {{ background: {COLOR_CARD}; color: {color}; "
                f"border: 1px solid {color}; border-radius: 6px; padding: 2px 8px; "
                f"font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}")
            chip.setToolTip(f"Senin: {h['action'].upper()} · GTO: {h['gto'].upper()} · "
                            + ("✓ doğru" if h["correct"] else "✗ yanlış"))
            lay.addWidget(chip)
        lay.addStretch(1)

    # ── SPOT CARD ─────────────────────────────────────────────────────
    def _build_spot_card(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 12px; padding: 24px; }}"
        )
        v = QVBoxLayout(card)
        v.setSpacing(20)
        v.setContentsMargins(28, 28, 28, 28)

        # Context bar (pos + stack + scenario)
        ctx = QHBoxLayout()
        ctx.setSpacing(20)
        self.ctx_pos = self._context_chip("Position", "—", COLOR_INK)
        self.ctx_stack = self._context_chip("Stack", "—", "#F59E0B")
        self.ctx_scenario = self._context_chip("Scenario", "RFI", "#8B5CF6")
        for w in (self.ctx_pos, self.ctx_stack, self.ctx_scenario):
            ctx.addWidget(w)
        ctx.addStretch(1)
        v.addLayout(ctx)

        # Plain-language durum cümlesi (gerçek poker bağlamı)
        self.situation_label = QLabel("")
        self.situation_label.setWordWrap(True)
        self.situation_label.setAlignment(Qt.AlignCenter)
        self.situation_label.setStyleSheet(
            f"color:{COLOR_MUTED}; font-size:13px; padding:2px 0;")
        v.addWidget(self.situation_label)

        # Hand display (ortalı)
        hand_wrap = QHBoxLayout()
        hand_wrap.addStretch(1)
        self.hand_display = TwoCardHand(size="xl")
        hand_wrap.addWidget(self.hand_display)
        hand_wrap.addStretch(1)
        v.addLayout(hand_wrap)

        self.hand_key_label = QLabel("AKs")
        self.hand_key_label.setAlignment(Qt.AlignCenter)
        self.hand_key_label.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 28px; font-weight: 800; "
            f"font-family: 'JetBrains Mono', monospace;"
        )
        v.addWidget(self.hand_key_label)

        # Geri sayım bar
        self.timer_bar = QProgressBar()
        self.timer_bar.setMaximum(100)
        self.timer_bar.setTextVisible(False)
        self.timer_bar.setFixedHeight(8)
        self.timer_bar.setStyleSheet(
            f"QProgressBar {{ background: {COLOR_LINE}; border: none; "
            f"border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: {COLOR_GOOD}; "
            f"border-radius: 4px; }}"
        )
        v.addWidget(self.timer_bar)

        self.timer_label = QLabel("5.0s")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 12px; font-family: monospace;"
        )
        v.addWidget(self.timer_label)

        # Aksiyon butonları
        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.btn_fold = QPushButton("FOLD")
        self.btn_call = QPushButton("CALL")
        self.btn_raise = QPushButton("RAISE")
        for btn, color, key in [
            (self.btn_fold, COLOR_FOLD, "fold"),
            (self.btn_call, COLOR_CALL, "call"),
            (self.btn_raise, COLOR_RAISE, "raise"),
        ]:
            btn.setFixedHeight(58)
            btn.setStyleSheet(self._btn_style(color))
            btn.clicked.connect(lambda _, k=key: self._on_answer(k))
            actions.addWidget(btn, 1)
        v.addLayout(actions)

        # Feedback panel (cevap sonrası)
        self.feedback_panel = QFrame()
        self.feedback_panel.setStyleSheet(
            f"QFrame {{ background: transparent; padding: 0; }}"
        )
        fb_v = QVBoxLayout(self.feedback_panel)
        fb_v.setContentsMargins(0, 0, 0, 0)
        self.feedback_label = QLabel("")
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 13px; padding: 12px;"
        )
        fb_v.addWidget(self.feedback_label)
        self.next_btn = QPushButton("Sıradaki Spot  →")
        self.next_btn.setFixedHeight(44)
        self.next_btn.setStyleSheet(self._btn_style("#8B5CF6"))
        self.next_btn.clicked.connect(self._start_new_spot)
        fb_v.addWidget(self.next_btn)
        self.feedback_panel.hide()
        v.addWidget(self.feedback_panel)

        return card

    def _context_chip(self, label: str, value: str, color: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            f"QFrame {{ background: {COLOR_BG}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 8px; padding: 8px 14px; }}"
        )
        h = QVBoxLayout(w)
        h.setSpacing(2)
        h.setContentsMargins(8, 4, 8, 4)
        lab = QLabel(label.upper())
        lab.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 9px; font-weight: 700; "
            f"letter-spacing: 1.5px;"
        )
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: 800; "
            f"font-family: 'JetBrains Mono', monospace;"
        )
        h.addWidget(lab)
        h.addWidget(val)
        # Public ref so we can update later
        w._value_label = val
        return w

    def _btn_style(self, color: str, secondary: bool = False) -> str:
        if secondary:
            return (
                f"QPushButton {{ background: transparent; color: {color}; "
                f"border: 1px solid {color}; border-radius: 8px; "
                f"font-size: 13px; font-weight: 700; padding: 8px 16px; }}"
                f"QPushButton:hover {{ background: {COLOR_LINE}; }}"
            )
        return (
            f"QPushButton {{ background: {color}; color: {COLOR_INK}; "
            f"border: none; border-radius: 8px; "
            f"font-size: 16px; font-weight: 800; letter-spacing: 1.5px; "
            f"padding: 10px; }}"
            f"QPushButton:hover {{ opacity: 0.9; }}"
            f"QPushButton:disabled {{ background: {COLOR_LINE}; "
            f"color: {COLOR_MUTED}; }}"
        )

    # ── STATS PANEL ───────────────────────────────────────────────────
    def _build_stats_panel(self) -> QWidget:
        panel = QFrame()
        panel.setStyleSheet(
            f"QFrame {{ background: {COLOR_CARD}; border: 1px solid {COLOR_LINE}; "
            f"border-radius: 12px; padding: 16px; }}"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(12)

        h_title = QLabel("📊  BU SEANS")
        h_title.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 12px; font-weight: 700; "
            f"letter-spacing: 1.5px;"
        )
        v.addWidget(h_title)

        # Big number: accuracy
        self.acc_label = QLabel("0%")
        self.acc_label.setStyleSheet(
            f"color: {COLOR_GOOD}; font-size: 42px; font-weight: 900; "
            f"font-family: 'JetBrains Mono', monospace;"
        )
        v.addWidget(self.acc_label)
        self.acc_sub = QLabel("0/0 doğru")
        self.acc_sub.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 12px;"
        )
        v.addWidget(self.acc_sub)

        # Streak
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet(f"background: {COLOR_LINE}; max-height: 1px;")
        v.addWidget(sep1)

        self.streak_label = QLabel("🔥  Streak: 0")
        self.streak_label.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 14px; font-weight: 700;"
        )
        v.addWidget(self.streak_label)
        self.best_streak_label = QLabel("Best: 0")
        self.best_streak_label.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px;"
        )
        v.addWidget(self.best_streak_label)

        # Position breakdown
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"background: {COLOR_LINE}; max-height: 1px;")
        v.addWidget(sep2)

        by_pos_title = QLabel("Pozisyona göre")
        by_pos_title.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            f"letter-spacing: 1px;"
        )
        v.addWidget(by_pos_title)
        self.by_pos_label = QLabel("Henüz veri yok.")
        self.by_pos_label.setStyleSheet(
            f"color: {COLOR_INK}; font-size: 11px; "
            f"font-family: 'JetBrains Mono', monospace; line-height: 1.6;"
        )
        v.addWidget(self.by_pos_label)

        v.addStretch(1)
        return panel

    # ── QUIZ FLOW ─────────────────────────────────────────────────────
    def _start_new_spot(self, start_timer: bool = True) -> None:
        """Yeni rastgele spot üret ve quiz'i başlat."""
        # Spaced repetition: %25 ihtimalle wrong queue'dan al
        if self.stats.wrong_queue and random.random() < 0.25:
            spot = random.choice(self.stats.wrong_queue)
        else:
            spot = self._random_spot()

        self._current_spot = spot
        self._answered = False
        self._countdown_remaining = self._countdown_total

        # UI güncelle
        self.ctx_pos._value_label.setText(spot.position)
        self.ctx_stack._value_label.setText(f"{spot.stack_depth}bb")
        # Scenario chip — vs_position varsa göster (örn "vs RFI (UTG)")
        scen_text = spot.scenario
        if spot.vs_position:
            scen_text = f"{spot.scenario} ({spot.vs_position})"
        self.ctx_scenario._value_label.setText(scen_text)
        self.hand_display.set_hand(spot.hand)
        self.hand_key_label.setText(spot.hand)
        self.situation_label.setText(self._situation_text(spot))

        # Aksiyon butonlarını sıfırla (text + renk) ve etkinleştir
        for btn, color, base_txt in [(self.btn_fold, COLOR_FOLD, "FOLD"),
                                      (self.btn_call, COLOR_CALL, "CALL"),
                                      (self.btn_raise, COLOR_RAISE, "RAISE")]:
            btn.setEnabled(True)
            btn.setText(base_txt)
            btn.setStyleSheet(self._btn_style(color))

        # Feedback gizle, timer başlat
        self.feedback_panel.hide()
        self._update_timer_ui()
        if start_timer:
            self._timer.start()

    @staticmethod
    def _situation_text(spot) -> str:
        """Spotu düz Türkçe poker diliyle anlat — kullanıcı kararı anlasın."""
        pos = spot.position
        opener = spot.vs_position or "rakip"
        if spot.scenario == "RFI":
            return (f"♟ {pos} pozisyonundasın, herkes sana fold etti. "
                    f"Açış kararı: raise mı, fold mu?")
        if spot.scenario == "vs RFI":
            return (f"♟ {opener} açış yaptı, sen {pos}'dasın. "
                    f"Savunma: 3-bet / call / fold?")
        if spot.scenario == "vs 3-bet":
            return (f"♟ Sen {pos}'dan açtın, {opener} 3-bet yaptı. "
                    f"4-bet / call / fold?")
        if spot.scenario == "Push/Fold":
            return (f"♟ {spot.stack_depth}bb kaldı, {pos}'dasın. "
                    f"Kısa stack: jam mı, fold mu?")
        return f"♟ {pos} · {spot.scenario}"

    # Pozisyon sıralaması (vs_position seçimi için — opener defender'dan önce)
    _POS_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "BB"]

    def _random_spot(self) -> QuizSpot:
        """Filtre'lere göre random spot oluştur (senaryo-farkında)."""
        # Scenario seç (All ise ağırlıklı random)
        scen_filter = self._mode_filter["scenario"]
        if scen_filter == "All":
            scen = random.choices(
                ["RFI", "vs RFI", "vs 3-bet", "Push/Fold"],
                weights=[45, 30, 15, 10],
            )[0]
        else:
            scen = scen_filter

        # Stack — Push/Fold otomatik kısa stack
        if scen == "Push/Fold":
            depth = random.choice([10, 12, 15, 20])
        elif self._mode_filter["stack_depth"] == "All":
            depth = random.choice([100, 100, 100, 60, 40])
        else:
            depth = int(self._mode_filter["stack_depth"].replace("bb", ""))

        # Position + vs_position senaryoya göre
        pos_filter = self._mode_filter["position"]
        vs_pos = None
        if scen == "RFI":
            pos = (pos_filter if pos_filter != "All"
                   else random.choice(["UTG", "MP", "CO", "BTN", "SB"]))
        elif scen == "vs RFI":
            # Defender pozisyonu + ondan önceki bir opener
            pos = (pos_filter if pos_filter != "All"
                   else random.choice(["BB", "SB", "BTN", "CO"]))
            pos_idx = self._POS_ORDER.index(pos) if pos in self._POS_ORDER else 5
            openers = self._POS_ORDER[:pos_idx] or ["BTN"]
            vs_pos = random.choice(openers)
        elif scen == "vs 3-bet":
            # Opener (erken-orta) + 3-bettor (sonraki pozisyon)
            pos = (pos_filter if pos_filter != "All"
                   else random.choice(["UTG", "MP", "CO", "BTN"]))
            pos_idx = self._POS_ORDER.index(pos) if pos in self._POS_ORDER else 0
            threebettors = self._POS_ORDER[pos_idx + 1:] or ["BB"]
            vs_pos = random.choice(threebettors)
        else:  # Push/Fold
            pos = (pos_filter if pos_filter != "All"
                   else random.choice(["UTG", "MP", "CO", "BTN", "SB"]))

        hand = random.choice(self._all_hand_keys())
        action = get_action(pos, hand, scen, depth, "cash", vs_position=vs_pos)
        return QuizSpot(pos, depth, scen, hand, action, vs_position=vs_pos)

    @staticmethod
    def _all_hand_keys() -> list:
        ranks = "AKQJT98765432"
        out = []
        for i, hi in enumerate(ranks):
            for j, lo in enumerate(ranks):
                if i == j:
                    out.append(hi + lo)
                elif i < j:
                    out.append(hi + lo + "s")
                else:
                    out.append(lo + hi + "o")
        return out

    def _on_tick(self) -> None:
        """Her 100ms'de bir timer tick."""
        self._countdown_remaining -= 0.1
        if self._countdown_remaining <= 0:
            # Süre doldu → otomatik FOLD
            self._timer.stop()
            self._on_answer("fold", timed_out=True)
        else:
            self._update_timer_ui()

    def _update_timer_ui(self) -> None:
        pct = max(0, int(100 * self._countdown_remaining / self._countdown_total))
        self.timer_bar.setValue(pct)
        self.timer_label.setText(f"{max(0, self._countdown_remaining):.1f}s")
        # Renk: yeşil → sarı → kırmızı
        if pct > 60:
            color = COLOR_GOOD
        elif pct > 30:
            color = "#F59E0B"
        else:
            color = COLOR_BAD
        self.timer_bar.setStyleSheet(
            f"QProgressBar {{ background: {COLOR_LINE}; border: none; "
            f"border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )

    def _on_answer(self, user_action: str, timed_out: bool = False) -> None:
        """Hero bir aksiyon seçti."""
        if self._answered or not self._current_spot:
            return
        self._answered = True
        self._timer.stop()

        spot = self._current_spot
        correct = spot.correct_action
        action = spot.action

        # Mixed strategy → birden fazla doğru cevap olabilir.
        # En az %20 frekanslı her aksiyon "kabul edilebilir"
        acceptable = {k for k in ("raise", "call", "fold")
                      if action.get(k, 0) >= 20}
        is_correct = user_action in acceptable or user_action == correct
        # Eğer sadece dominant aksiyonu istiyorsak strict:
        is_strict_correct = (user_action == correct)

        # EV kaybı (🟠 approx) — yanlışta hesapla
        ev_loss = 0.0 if is_correct else spot.ev_loss_bb(user_action)
        self.stats.record(spot, is_correct, user_action=user_action,
                          ev_loss=ev_loss)

        # Aksiyon butonlarını disable et + GTO% göster (cevap sonrası — test bütünlüğü)
        for btn, key, base_txt in [(self.btn_fold, "fold", "FOLD"),
                                    (self.btn_call, "call", "CALL"),
                                    (self.btn_raise, "raise", "RAISE")]:
            btn.setEnabled(False)
            pct = action.get(key, 0)
            btn.setText(f"{base_txt}   {pct:.0f}%")
            if key == correct:
                btn.setStyleSheet(self._btn_style(COLOR_GOOD))
            elif key == user_action and not is_correct:
                btn.setStyleSheet(self._btn_style(COLOR_BAD))

        # Feedback metni
        self.feedback_label.setText(self._build_feedback(
            spot, user_action, is_correct, is_strict_correct, timed_out
        ))
        self.feedback_panel.show()

        # Panelleri güncelle
        self._refresh_stats_panel()
        self._refresh_session_bar()
        self._refresh_history_strip()

    def _build_feedback(
        self,
        spot: QuizSpot,
        user_action: str,
        is_correct: bool,
        is_strict_correct: bool,
        timed_out: bool,
    ) -> str:
        action = spot.action
        r = action.get("raise", 0)
        c = action.get("call", 0)
        f = action.get("fold", 0)
        freq_str = []
        for label, pct in [("Raise", r), ("Call", c), ("Fold", f)]:
            if pct > 0:
                freq_str.append(f"<b>{label} %{pct}</b>")
        freq_html = "  ·  ".join(freq_str)

        # ── EQUITY FEEDBACK (Monte Carlo, ~200ms) ──────────────────────
        # Hero hand'in villain'in defend range'ine karşı preflop equity'sini hesapla
        equity_html = ""
        try:
            equity_html = self._compute_equity_html(spot)
        except Exception:
            equity_html = ""

        if timed_out:
            head = f"<span style='color:{COLOR_BAD}; font-size:18px;'>⏱  SÜRE DOLDU</span>"
            note = (
                "Otomatik FOLD oldu. Hızını artırmak için Easy mod'da başla, "
                "kasını oluşturduktan sonra Normal/Hard'a geç."
            )
        elif is_strict_correct:
            head = f"<span style='color:{COLOR_GOOD}; font-size:20px;'>✓  DOĞRU</span>"
            if spot.is_mixed:
                note = (
                    f"Mixed strategy spotunda dominant aksiyonu seçtin. "
                    f"Uzun vadede {r}/{c}/{f} oranlarına sadık kal."
                )
            else:
                note = "Pure strategy — bu spot'ta her zaman bu aksiyon."
        elif is_correct:
            head = f"<span style='color:#F59E0B; font-size:18px;'>≈  KABUL EDİLEBİLİR</span>"
            note = (
                f"Mixed spotunda alternatif frekanslı aksiyonu seçtin. "
                f"Dominant: <b>{spot.correct_action.upper()}</b>"
            )
        else:
            head = f"<span style='color:{COLOR_BAD}; font-size:20px;'>✗  YANLIŞ</span>"
            note = (
                f"Doğru aksiyon: <b>{spot.correct_action.upper()}</b><br>"
                f"Senin seçtiğin: <b>{user_action.upper()}</b>"
            )

        return (f"{head}<br><br>{freq_html}<br><br>"
                f"<span style='color:{COLOR_MUTED};'>{note}</span>"
                f"{equity_html}")

    def _compute_equity_html(self, spot: QuizSpot) -> str:
        """Hero hand'in defending opponent'a karşı equity'sini hesapla.

        Heuristic opponent range (preflop, RFI scenario):
          - Hero BTN open ediyor → varsayılan villain = BB defend range
          - Hero UTG/MP/CO RFI → villain = "average call+3-bet" range
            (top 20% pool — yaklaşık)
          - Hero SB RFI → villain = BB defend range

        2000 iter ≈ 200ms. Bloklayıcı ama küçük.
        """
        from app.poker.mc_equity import (
            equity_hand_vs_range, expand_hand_key, gto_range_for,
        )

        if spot.scenario != "RFI":
            return ""   # TODO: vs RFI / vs 3-bet için ayrı analiz

        # Hero combo seç (her hand key 4-12 combo; randevu için ilki yeterli)
        combos = expand_hand_key(spot.hand)
        if not combos:
            return ""
        hero_combo = combos[0]
        hero_str = f"{hero_combo[0].rank}{hero_combo[0].suit}{hero_combo[1].rank}{hero_combo[1].suit}"

        # Villain defending range belirle
        if spot.position == "BTN":
            villain_range = gto_range_for("BB", "vs RFI", threshold_pct=10)
            villain_label = "BB defend range"
        elif spot.position == "SB":
            villain_range = gto_range_for("BB", "vs RFI", threshold_pct=10)
            villain_label = "BB defend range"
        else:
            # UTG/MP/CO → mixed villain (use BB defend as proxy for "called")
            villain_range = gto_range_for("BB", "vs RFI", threshold_pct=10)
            villain_label = "average defend range"

        if not villain_range:
            # Fallback: top ~30% of hands
            villain_range = ["AA", "KK", "QQ", "JJ", "TT", "99", "88",
                             "AKs", "AQs", "AJs", "ATs", "KQs", "KJs",
                             "AKo", "AQo", "AJo", "KQo"]
            villain_label = "premium defending range"

        # Monte Carlo — 2K iter ≈ 200ms (UI'ye block etse de tolerable)
        result = equity_hand_vs_range(hero_str, villain_range, iterations=2000)
        eq = result.a_equity
        color = (COLOR_GOOD if eq >= 50 else
                 "#F59E0B" if eq >= 40 else COLOR_BAD)
        return (f"<br><br>"
                f"<span style='color:{COLOR_MUTED};'>📊  Equity:</span>  "
                f"<span style='color:{color}; font-weight:700;'>"
                f"{eq:.1f}%</span>  "
                f"<span style='color:{COLOR_MUTED};'>vs {villain_label}</span>")

    def _refresh_stats_panel(self) -> None:
        # Accuracy
        self.acc_label.setText(f"{self.stats.accuracy_pct:.0f}%")
        self.acc_label.setStyleSheet(
            f"color: "
            f"{COLOR_GOOD if self.stats.accuracy_pct >= 75 else '#F59E0B' if self.stats.accuracy_pct >= 50 else COLOR_BAD}; "
            f"font-size: 42px; font-weight: 900; "
            f"font-family: 'JetBrains Mono', monospace;"
        )
        self.acc_sub.setText(f"{self.stats.correct}/{self.stats.total} doğru")

        # Streak
        self.streak_label.setText(f"🔥  Streak: {self.stats.streak}")
        self.best_streak_label.setText(f"Best: {self.stats.best_streak}")

        # By position
        if not self.stats.by_position:
            self.by_pos_label.setText("Henüz veri yok.")
            return
        lines = []
        for pos in ["UTG", "MP", "CO", "BTN", "SB"]:
            t, c = self.stats.by_position.get(pos, (0, 0))
            if t > 0:
                pct = c / t * 100
                color = (COLOR_GOOD if pct >= 80
                         else "#F59E0B" if pct >= 60 else COLOR_BAD)
                lines.append(
                    f"<span style='color:{COLOR_MUTED};'>{pos:<4}</span>  "
                    f"<span style='color:{color};'>{c}/{t} ({pct:.0f}%)</span>"
                )
        self.by_pos_label.setText("<br>".join(lines))


# ── ALIAS / EXPORT ───────────────────────────────────────────────────
# main.py NAV_ITEMS için
RangeQuizScreen = QuizTrainerScreen
