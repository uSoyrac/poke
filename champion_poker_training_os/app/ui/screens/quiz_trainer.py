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
from PySide6.QtGui import QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QVBoxLayout, QWidget,
)

from app.poker.gto_ranges import (
    POSITIONS_6MAX, STACK_DEPTHS, get_action,
)


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


@dataclass
class QuizStats:
    """Bu seansın quiz istatistikleri."""
    total: int = 0
    correct: int = 0
    streak: int = 0
    best_streak: int = 0
    by_position: dict = field(default_factory=dict)  # pos → (total, correct)
    wrong_queue: List[QuizSpot] = field(default_factory=list)

    def record(self, spot: QuizSpot, is_correct: bool) -> None:
        self.total += 1
        if is_correct:
            self.correct += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0
            # Yanlış answer queue'ya ekle (spaced repetition için)
            self.wrong_queue.append(spot)
            if len(self.wrong_queue) > 25:
                self.wrong_queue = self.wrong_queue[-20:]

        pt, pc = self.by_position.get(spot.position, (0, 0))
        self.by_position[spot.position] = (pt + 1, pc + (1 if is_correct else 0))

    @property
    def accuracy_pct(self) -> float:
        return 100 * self.correct / max(self.total, 1)


# ── HAND CARD DISPLAY ────────────────────────────────────────────────
class HandDisplay(QWidget):
    """Hero'nun 2 kartını büyük format görselleştirir."""

    SUIT_CHARS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
    SUIT_COLORS = {"s": "#1F2937", "c": "#1F2937", "h": "#DC2626", "d": "#DC2626"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card1 = "A♠"
        self._card2 = "K♠"
        self._color1 = "#1F2937"
        self._color2 = "#1F2937"
        self.setFixedSize(280, 160)

    def set_hand(self, hand_key: str) -> None:
        """hand_key = AKs, QJo, 77 vb."""
        if not hand_key:
            return
        if len(hand_key) == 2:   # pair
            r1, r2 = hand_key[0], hand_key[1]
            self._card1 = f"{r1}♠"
            self._card2 = f"{r2}♥"
            self._color1 = self.SUIT_COLORS["s"]
            self._color2 = self.SUIT_COLORS["h"]
        elif hand_key.endswith("s"):
            r1, r2 = hand_key[0], hand_key[1]
            self._card1 = f"{r1}♠"
            self._card2 = f"{r2}♠"
            self._color1 = self.SUIT_COLORS["s"]
            self._color2 = self.SUIT_COLORS["s"]
        else:   # offsuit
            r1, r2 = hand_key[0], hand_key[1]
            self._card1 = f"{r1}♥"
            self._card2 = f"{r2}♣"
            self._color1 = self.SUIT_COLORS["h"]
            self._color2 = self.SUIT_COLORS["c"]
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        card_w = w // 2 - 6
        card_h = h
        font = QFont("Inter, Helvetica, sans-serif")
        font.setPixelSize(46)
        font.setBold(True)
        for i, (text, color) in enumerate([(self._card1, self._color1),
                                            (self._card2, self._color2)]):
            x = i * (card_w + 12)
            p.setBrush(QColor("#FAFAFA"))
            p.setPen(QColor(color))
            p.drawRoundedRect(x, 0, card_w, card_h, 10, 10)
            p.setFont(font)
            p.drawText(x, 0, card_w, card_h, Qt.AlignCenter, text)


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

        # Ana içerik: sol (spot card) + sağ (stats)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        splitter.addWidget(self._build_spot_card())
        splitter.addWidget(self._build_stats_panel())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self._start_new_spot()

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

        # Hand display (ortalı)
        hand_wrap = QHBoxLayout()
        hand_wrap.addStretch(1)
        self.hand_display = HandDisplay()
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
    def _start_new_spot(self) -> None:
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
        self.ctx_scenario._value_label.setText(spot.scenario)
        self.hand_display.set_hand(spot.hand)
        self.hand_key_label.setText(spot.hand)

        # Aksiyon butonlarını etkinleştir
        for btn in (self.btn_fold, self.btn_call, self.btn_raise):
            btn.setEnabled(True)

        # Feedback gizle, timer başlat
        self.feedback_panel.hide()
        self._update_timer_ui()
        self._timer.start()

    def _random_spot(self) -> QuizSpot:
        """Filtre'lere göre random spot oluştur."""
        # Position seç
        if self._mode_filter["position"] == "All":
            pos = random.choice(["UTG", "MP", "CO", "BTN", "SB"])
        else:
            pos = self._mode_filter["position"]
        # Stack
        if self._mode_filter["stack_depth"] == "All":
            depth = random.choice([100, 100, 100, 60, 40])  # 100bb ağırlıklı
        else:
            depth = int(self._mode_filter["stack_depth"].replace("bb", ""))
        # Scenario
        scen = self._mode_filter["scenario"]
        # Hand — 169 elden weighted random:
        # Premium ve mixed'i daha sık göster (eğitim değeri yüksek)
        all_hands = self._all_hand_keys()
        hand = random.choice(all_hands)
        action = get_action(pos, hand, scen, depth, "cash")
        return QuizSpot(pos, depth, scen, hand, action)

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

        self.stats.record(spot, is_correct)

        # Aksiyon butonlarını disable et + doğru olanı yeşil yap
        for btn, key in [(self.btn_fold, "fold"),
                          (self.btn_call, "call"),
                          (self.btn_raise, "raise")]:
            btn.setEnabled(False)
            if key == correct:
                btn.setStyleSheet(self._btn_style(COLOR_GOOD))
            elif key == user_action and not is_correct:
                btn.setStyleSheet(self._btn_style(COLOR_BAD))

        # Feedback metni
        self.feedback_label.setText(self._build_feedback(
            spot, user_action, is_correct, is_strict_correct, timed_out
        ))
        self.feedback_panel.show()

        # Stats panelini güncelle
        self._refresh_stats_panel()

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
