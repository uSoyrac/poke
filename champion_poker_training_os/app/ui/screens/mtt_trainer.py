"""MTT Trainer — turnuva oyuncusu için stack-depth-aware GTO eğitmeni.

İki mod:
  1. PUSH/FOLD DRILL: random spot (pozisyon × stack 8-25bb) → jam/fold seç
     → Nash ile karşılaştır + ICM riski göster
  2. STACK EXPLORER: stack derinliği seç (20-200bb) → o derinliğin
     RFI/jam range'ini 13×13 grid'de gör

MTT-spesifik özellikler:
  - Stack depth selector: 20/40/60/80/100/150/200bb
  - Nash push/fold (8-25bb)
  - ICM bubble factor uyarısı
  - Tournament coach (ICM-aware Gemini prompt)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from app.poker.mtt_ranges import (
    build_mtt_push_fold, build_mtt_rfi, mtt_jam_pct,
)


COLOR_INK = "#FAFAFA"
COLOR_MUTED = "#94A3B8"
COLOR_BG = "#0F1419"
COLOR_CARD = "#111827"
COLOR_LINE = "#1F2937"
COLOR_JAM = "#DC2626"
COLOR_FOLD = "#2563EB"
COLOR_GOOD = "#10B981"
COLOR_BAD = "#DC2626"
COLOR_AMBER = "#F59E0B"
COLOR_ACCENT = "#8B5CF6"

STACK_DEPTHS = [20, 40, 60, 80, 100, 150, 200]
PF_STACKS = [8, 10, 12, 15, 20]
POSITIONS = ["UTG", "MP", "CO", "BTN", "SB"]


@dataclass
class MTTStats:
    total: int = 0
    correct: int = 0
    streak: int = 0
    best: int = 0
    by_stack: dict = field(default_factory=dict)

    def record(self, stack: int, ok: bool) -> None:
        self.total += 1
        if ok:
            self.correct += 1
            self.streak += 1
            self.best = max(self.best, self.streak)
        else:
            self.streak = 0
        t, c = self.by_stack.get(stack, (0, 0))
        self.by_stack[stack] = (t + 1, c + (1 if ok else 0))

    @property
    def acc(self) -> float:
        return 100 * self.correct / max(self.total, 1)


# ── 13×13 mini grid (read-only, range display) ────────────────────────
class MiniRangeGrid(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._table = {}
        self.setMinimumSize(560, 380)

    def set_range(self, table: dict) -> None:
        self._table = table or {}
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        ranks = "AKQJT98765432"
        n = 13
        w = self.width() / n
        h = self.height() / n
        font = QFont("JetBrains Mono, monospace")
        font.setPixelSize(int(min(w, h) * 0.30))
        font.setBold(True)
        p.setFont(font)
        for i, hi in enumerate(ranks):
            for j, lo in enumerate(ranks):
                if i == j:
                    hk = hi + lo
                elif i < j:
                    hk = hi + lo + "s"
                else:
                    hk = lo + hi + "o"
                a = self._table.get(hk, {"raise": 0, "call": 0, "fold": 100})
                r = a.get("raise", 0)
                c = a.get("call", 0)
                f = a.get("fold", 100)
                x, y = j * w, i * h
                # Yatay action split: raise(kırmızı) | call(yeşil) | fold(mavi)
                xx = x
                for pct, col in [(r, COLOR_JAM), (c, COLOR_GOOD), (f, COLOR_FOLD)]:
                    if pct <= 0:
                        continue
                    seg = w * pct / 100
                    p.fillRect(int(xx), int(y), int(seg) + 1, int(h) + 1, QColor(col))
                    xx += seg
                p.setPen(QColor(COLOR_BG))
                p.drawRect(int(x), int(y), int(w), int(h))
                p.setPen(QColor("#FAFAFA"))
                p.drawText(int(x), int(y), int(w), int(h), Qt.AlignCenter, hk)


class MTTTrainerScreen(QWidget):
    coach_message = Signal(str)
    analysis_requested = Signal(str)

    DIFFICULTY = {"Easy": 8, "Normal": 5, "Hard": 3}

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self.stats = MTTStats()
        self._spot = None
        self._mode = "pf"
        self._answered = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(12)

        title = QLabel("🏆  MTT Trainer — Turnuva GTO Eğitmeni")
        title.setStyleSheet(f"color:{COLOR_INK}; font-size:22px; font-weight:800;")
        root.addWidget(title)
        sub = QLabel("Stack-depth-aware push/fold + range explorer.  "
                     "Nash chart'ları (8-25bb) + ante-aware açış (20-200bb).")
        sub.setStyleSheet(f"color:{COLOR_MUTED}; font-size:12px;")
        root.addWidget(sub)

        # Mode tabs
        mode_bar = QHBoxLayout()
        self.mode_pf = QPushButton("🎯  Push/Fold Drill")
        self.mode_ex = QPushButton("📊  Stack Explorer")
        for b in (self.mode_pf, self.mode_ex):
            b.setCheckable(True)
            b.setFixedHeight(36)
            b.setStyleSheet(self._tab_style())
        self.mode_pf.setChecked(True)
        self.mode_pf.clicked.connect(lambda: self._set_mode("pf"))
        self.mode_ex.clicked.connect(lambda: self._set_mode("ex"))
        mode_bar.addWidget(self.mode_pf)
        mode_bar.addWidget(self.mode_ex)
        mode_bar.addStretch(1)
        root.addLayout(mode_bar)

        # Stacked content
        self.content = QVBoxLayout()
        root.addLayout(self.content, 1)

        self._pf_widget = self._build_push_fold()
        self._ex_widget = self._build_explorer()
        self.content.addWidget(self._pf_widget)
        self.content.addWidget(self._ex_widget)
        self._ex_widget.hide()

        self._new_pf_spot()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        # Ekran açılınca taze spot (yalnızca cevaplanmışsa / spot yoksa)
        if self._mode == "pf" and (self._answered or self._spot is None):
            self._new_pf_spot()

    def _tab_style(self) -> str:
        return (
            f"QPushButton {{ background:{COLOR_BG}; color:{COLOR_MUTED}; "
            f"border:1px solid {COLOR_LINE}; border-radius:8px; padding:6px 18px; "
            f"font-size:13px; font-weight:700; }} "
            f"QPushButton:checked {{ background:{COLOR_ACCENT}; color:white; }}"
        )

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self.mode_pf.setChecked(mode == "pf")
        self.mode_ex.setChecked(mode == "ex")
        self._pf_widget.setVisible(mode == "pf")
        self._ex_widget.setVisible(mode == "ex")
        if mode == "ex":
            self._refresh_explorer()
        else:
            self._new_pf_spot()         # drill'e dönünce taze spot + sayaç

    # ── PUSH/FOLD DRILL ───────────────────────────────────────────────
    def _build_push_fold(self) -> QWidget:
        w = QWidget()
        split = QHBoxLayout(w)
        split.setSpacing(14)

        # Left: spot card
        card = QFrame()
        # ÖNEMLİ: selektör objectName ile sınırlanmalı. Çıplak 'QFrame{...}'
        # yazılırsa stil TÜM torun QFrame'lere (gömülü LivePokerTable'ın
        # _Seat'lerine) sızar → seat'ler kartın bg/border/padding'ini alıp dev
        # kutular olur ve üst üste biner (push/fold masası kaosu).
        card.setObjectName("PfCard")
        card.setStyleSheet(f"QFrame#PfCard{{background:{COLOR_CARD}; border:1px solid "
                           f"{COLOR_LINE}; border-radius:12px; padding:20px;}}")
        v = QVBoxLayout(card)
        v.setSpacing(16)

        # Difficulty
        ctrl = QHBoxLayout()
        ctrl.addWidget(self._lbl("Difficulty"))
        self.diff = QComboBox()
        self.diff.addItems(list(self.DIFFICULTY.keys()))
        self.diff.setCurrentText("Normal")
        # Zaman kısıtı kaldırıldı; zorluk seçimi bilgilendirme amaçlı
        self.diff.currentTextChanged.connect(
            lambda t: setattr(self, "_difficulty", t))
        ctrl.addWidget(self.diff)
        ctrl.addStretch(1)
        skip = QPushButton("⏭ Skip")
        skip.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR_MUTED};"
                          f"border:1px solid {COLOR_LINE};border-radius:6px;padding:4px 12px;}}")
        skip.clicked.connect(self._new_pf_spot)
        ctrl.addWidget(skip)
        v.addLayout(ctrl)

        # GERÇEK POKER MASASI — hero koltukta, kartları, pozisyon, rakipler, pot
        from app.ui.components.poker_table import LivePokerTable
        self.pf_table = LivePokerTable()
        self.pf_table.setMinimumHeight(440)   # koltuklar üst üste binmesin
        v.addWidget(self.pf_table, 1)

        # Plain-language durum cümlesi (gerçek turnuva bağlamı)
        self.pf_situation = QLabel("")
        self.pf_situation.setWordWrap(True)
        self.pf_situation.setAlignment(Qt.AlignCenter)
        self.pf_situation.setStyleSheet(f"color:{COLOR_MUTED}; font-size:13px;")
        v.addWidget(self.pf_situation)

        # Jam / Fold buttons — zaman kısıtı YOK
        btns = QHBoxLayout()
        btns.setSpacing(12)
        self.btn_fold = QPushButton("FOLD")
        self.btn_jam = QPushButton("JAM  (all-in)")
        for b, col, key in [(self.btn_fold, COLOR_FOLD, "fold"),
                            (self.btn_jam, COLOR_JAM, "raise")]:
            b.setFixedHeight(56)
            b.setStyleSheet(self._action_style(col))
            b.clicked.connect(lambda _, k=key: self._pf_answer(k))
            btns.addWidget(b, 1)
        v.addLayout(btns)

        # Feedback
        self.pf_fb = QLabel("")
        self.pf_fb.setWordWrap(True)
        self.pf_fb.setAlignment(Qt.AlignCenter)
        self.pf_fb.setStyleSheet(f"color:{COLOR_INK}; font-size:13px; padding:10px;")
        v.addWidget(self.pf_fb)
        self.pf_next = QPushButton("Sıradaki Spot →")
        self.pf_next.setFixedHeight(40)
        self.pf_next.setStyleSheet(self._action_style(COLOR_ACCENT))
        self.pf_next.clicked.connect(self._new_pf_spot)
        self.pf_next.hide()
        v.addWidget(self.pf_next)

        split.addWidget(card, 1)

        # Right: stats — DAR sabit kenar çubuğu (masaya tam genişlik kalsın →
        # koltuklar üst üste binmez, gerçek poker masası deneyimi)
        stats = self._build_stats()
        stats.setFixedWidth(190)
        split.addWidget(stats, 0)
        return w

    def _build_stats(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("PfStats")
        panel.setStyleSheet(f"QFrame#PfStats{{background:{COLOR_CARD};border:1px solid "
                           f"{COLOR_LINE};border-radius:12px;padding:16px;}}")
        v = QVBoxLayout(panel)
        v.setSpacing(10)
        h = QLabel("📊  BU SEANS")
        h.setStyleSheet(f"color:{COLOR_INK};font-size:12px;font-weight:700;letter-spacing:1.5px;")
        v.addWidget(h)
        self.st_acc = QLabel("0%")
        self.st_acc.setStyleSheet(f"color:{COLOR_GOOD};font-size:40px;font-weight:900;font-family:monospace;")
        v.addWidget(self.st_acc)
        self.st_sub = QLabel("0/0 doğru")
        self.st_sub.setStyleSheet(f"color:{COLOR_MUTED};font-size:12px;")
        v.addWidget(self.st_sub)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{COLOR_LINE};max-height:1px;")
        v.addWidget(sep)
        self.st_streak = QLabel("🔥 Streak: 0")
        self.st_streak.setStyleSheet(f"color:{COLOR_INK};font-size:14px;font-weight:700;")
        v.addWidget(self.st_streak)
        self.st_bystack = QLabel("Stack bazında:\nHenüz veri yok.")
        self.st_bystack.setStyleSheet(f"color:{COLOR_INK};font-size:11px;font-family:monospace;line-height:1.6;")
        v.addWidget(self.st_bystack)
        v.addStretch(1)
        return panel

    # ── STACK EXPLORER ────────────────────────────────────────────────
    def _build_explorer(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(12)
        ctrl.addWidget(self._lbl("Position"))
        self.ex_pos = QComboBox()
        self.ex_pos.addItems(POSITIONS)
        self.ex_pos.setCurrentText("BTN")
        self.ex_pos.currentTextChanged.connect(self._refresh_explorer)
        ctrl.addWidget(self.ex_pos)
        ctrl.addWidget(self._lbl("Stack"))
        self.ex_stack = QComboBox()
        # Kısa stack'ler (push/fold + ICM/PKO için) + derin stack'ler (RFI)
        self.ex_stack.addItems([f"{d}bb" for d in [10, 12, 15] + STACK_DEPTHS])
        self.ex_stack.setCurrentText("100bb")
        self.ex_stack.currentTextChanged.connect(self._refresh_explorer)
        ctrl.addWidget(self.ex_stack)
        ctrl.addWidget(self._lbl("Scenario"))
        self.ex_scen = QComboBox()
        self.ex_scen.addItems([
            "Auto (RFI/Push)", "ICM Bubble", "ICM Final Table",
            "Satellite", "PKO Bounty", "Squeeze",
        ])
        self.ex_scen.currentTextChanged.connect(self._refresh_explorer)
        ctrl.addWidget(self.ex_scen)
        ctrl.addStretch(1)
        self.ex_stats_lbl = QLabel("")
        self.ex_stats_lbl.setStyleSheet(f"color:{COLOR_MUTED};font-size:12px;font-family:monospace;")
        ctrl.addWidget(self.ex_stats_lbl)
        v.addLayout(ctrl)

        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch(1)
        self.ex_grid = MiniRangeGrid()
        grid_wrap.addWidget(self.ex_grid)
        grid_wrap.addStretch(1)
        v.addLayout(grid_wrap, 1)

        # legend
        leg = QHBoxLayout()
        leg.addStretch(1)
        for txt, col in [("JAM/Raise", COLOR_JAM), ("Call", COLOR_GOOD), ("Fold", COLOR_FOLD)]:
            sw = QLabel("  "); sw.setFixedSize(14, 14)
            sw.setStyleSheet(f"background:{col};border-radius:2px;")
            lb = QLabel(txt); lb.setStyleSheet(f"color:{COLOR_MUTED};font-size:11px;")
            leg.addWidget(sw); leg.addWidget(lb); leg.addSpacing(12)
        leg.addStretch(1)
        v.addLayout(leg)

        self.ex_note = QLabel("")
        self.ex_note.setWordWrap(True)
        self.ex_note.setStyleSheet(f"color:{COLOR_AMBER};font-size:12px;padding:6px;")
        v.addWidget(self.ex_note)
        return w

    def _refresh_explorer(self, *_) -> None:
        from app.poker.mtt_ranges import (
            build_icm_push_fold, build_pko_jam, build_squeeze,
        )
        pos = self.ex_pos.currentText()
        stack = int(self.ex_stack.currentText().replace("bb", ""))
        scen = self.ex_scen.currentText() if hasattr(self, "ex_scen") else "Auto (RFI/Push)"

        if scen == "ICM Bubble":
            table = build_icm_push_fold(pos, stack, "bubble")
            mode_note = (f"BUBBLE — ICM baskısı jam'i daraltır. {pos} {stack}bb. "
                         f"Her chip kaybı kazançtan pahalı → tighter jam.")
        elif scen == "ICM Final Table":
            table = build_icm_push_fold(pos, stack, "final table")
            mode_note = (f"FINAL TABLE — pay jump'lar büyük, ICM ağır. "
                         f"{pos} {stack}bb jam range daralır.")
        elif scen == "Satellite":
            table = build_icm_push_fold(pos, stack, "satellite")
            mode_note = (f"SATELLITE — sadece hayatta kalmak yeter (seat win). "
                         f"En sıkı jam — sadece premium + sağlam value.")
        elif scen == "PKO Bounty":
            table = build_pko_jam(pos, stack, 0.5)
            mode_note = (f"PKO — bounty (0.5× stack) jam'i genişletir. {pos} {stack}bb. "
                         f"Rakibi elersen bounty alırsın → biraz daha agresif.")
        elif scen == "Squeeze":
            table = build_squeeze(pos, stack, 1)
            mode_note = (f"SQUEEZE — open + caller'a karşı 3-bet. {pos}. "
                         f"Polarized: value + A5s/A4s bluff. Multiway daralır.")
        elif stack <= 15:
            table = build_mtt_push_fold(pos, stack)
            mode_note = (f"≤15bb → PUSH/FOLD modu. {pos} {stack}bb jam range "
                         f"~%{mtt_jam_pct(pos, stack):.0f}. Kırmızı = jam (all-in).")
        else:
            table = build_mtt_rfi(pos, stack)
            if stack >= 150:
                mode_note = (f"{stack}bb DEEP — suited connector/ace implied odds "
                             f"ile genişler. RFI açış range'i.")
            elif stack <= 40:
                mode_note = (f"{stack}bb SHALLOW — 3-bet-or-fold artar, suited gapper "
                             f"kısılır. Daha linear/high-card ağırlıklı.")
            else:
                mode_note = (f"{stack}bb — ante-aware açış range'i (cash 100bb'ye yakın).")
        self.ex_grid.set_range(table)
        # range %
        total = 0; played = 0.0
        for hk, a in table.items():
            c = 6 if len(hk) == 2 else (4 if hk.endswith("s") else 12)
            played += c * (a.get("raise", 0) + a.get("call", 0)) / 100
        # total combos always 1326
        pct = played / 1326 * 100
        self.ex_stats_lbl.setText(f"Range: {pct:.1f}%  ·  {pos} {stack}bb")
        self.ex_note.setText(mode_note)

    # ── DRILL LOGIC ───────────────────────────────────────────────────
    def _new_pf_spot(self, start_timer: bool = True) -> None:
        pos = random.choice(POSITIONS)
        stack = random.choice(PF_STACKS)
        hand = random.choice(self._all_hands())
        table = build_mtt_push_fold(pos, stack)
        action = table.get(hand, {"raise": 0, "call": 0, "fold": 100})
        self._spot = {"pos": pos, "stack": stack, "hand": hand, "action": action}
        self._answered = False

        # Spotu GERÇEK poker masasına çiz (hero koltukta + kartları + pot)
        from app.ui.components.card_view import hand_key_to_cards
        from app.ui.components.spot_table import render_spot_on_table
        c1, c2 = hand_key_to_cards(hand)
        render_spot_on_table(self.pf_table, {
            "hero_cards": f"{c1} {c2}", "board": "", "position": pos,
            "table": "6-max", "stack_bb": stack, "street": "preflop",
            "pot_bb": 1.5, "action_history": "",
        })
        self.pf_situation.setText(
            f"♟ Turnuva · {stack}bb efektif stack, {pos} pozisyonundasın. "
            f"Herkes sana fold etti — jam mı, fold mu? "
            f"(ante'li Nash push/fold)")
        self.btn_fold.setEnabled(True)
        self.btn_jam.setEnabled(True)
        self.btn_fold.setStyleSheet(self._action_style(COLOR_FOLD))
        self.btn_jam.setStyleSheet(self._action_style(COLOR_JAM))
        self.pf_fb.setText("")
        self.pf_next.hide()

    @staticmethod
    def _all_hands() -> list:
        ranks = "AKQJT98765432"
        out = []
        for i, hi in enumerate(ranks):
            for j, lo in enumerate(ranks):
                if i == j: out.append(hi + lo)
                elif i < j: out.append(hi + lo + "s")
                else: out.append(lo + hi + "o")
        return out

    def _pf_answer(self, user: str) -> None:
        if self._answered or not self._spot:
            return
        self._answered = True
        sp = self._spot
        a = sp["action"]
        jam_freq = a.get("raise", 0)
        correct = "raise" if jam_freq >= 50 else "fold"
        ok = (user == correct) or (20 <= jam_freq <= 80)  # mixed → either ok
        self.stats.record(sp["stack"], ok)

        for b, key in [(self.btn_fold, "fold"), (self.btn_jam, "raise")]:
            b.setEnabled(False)
            if key == correct:
                b.setStyleSheet(self._action_style(COLOR_GOOD))
            elif key == user and not ok:
                b.setStyleSheet(self._action_style(COLOR_BAD))

        head = (f"<span style='color:{COLOR_GOOD};font-size:18px;'>✓ DOĞRU</span>"
                if ok else
                f"<span style='color:{COLOR_BAD};font-size:18px;'>✗ YANLIŞ</span>")
        jam_note = (f"Nash jam frekansı: <b>%{jam_freq}</b>  "
                    f"({sp['pos']} {sp['stack']}bb {sp['hand']})")
        if 20 <= jam_freq <= 80:
            jam_note += "  — mixed spot, ikisi de OK"
        elif correct == "raise":
            jam_note += "  — bu el jam range'inde"
        else:
            jam_note += "  — bu el fold (jam range dışı)"
        self.pf_fb.setText(f"{head}<br><br>{jam_note}")
        self.pf_next.show()
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        self.st_acc.setText(f"{self.stats.acc:.0f}%")
        self.st_acc.setStyleSheet(
            f"color:{COLOR_GOOD if self.stats.acc>=75 else COLOR_AMBER if self.stats.acc>=50 else COLOR_BAD};"
            f"font-size:40px;font-weight:900;font-family:monospace;")
        self.st_sub.setText(f"{self.stats.correct}/{self.stats.total} doğru")
        self.st_streak.setText(f"🔥 Streak: {self.stats.streak}  (best {self.stats.best})")
        lines = ["Stack bazında:"]
        for stk in PF_STACKS:
            t, c = self.stats.by_stack.get(stk, (0, 0))
            if t > 0:
                pct = c / t * 100
                col = COLOR_GOOD if pct >= 80 else COLOR_AMBER if pct >= 60 else COLOR_BAD
                lines.append(f"<span style='color:{COLOR_MUTED};'>{stk:>2}bb</span> "
                             f"<span style='color:{col};'>{c}/{t} ({pct:.0f}%)</span>")
        self.st_bystack.setText("<br>".join(lines) if len(lines) > 1
                                else "Stack bazında:\nHenüz veri yok.")

    # ── HELPERS ───────────────────────────────────────────────────────
    def _lbl(self, t: str) -> QLabel:
        l = QLabel(t)
        l.setStyleSheet(f"color:{COLOR_MUTED};font-size:11px;font-weight:600;"
                       f"text-transform:uppercase;letter-spacing:1px;")
        return l

    def _action_style(self, color: str) -> str:
        return (f"QPushButton{{background:{color};color:white;border:none;"
                f"border-radius:8px;font-size:15px;font-weight:800;letter-spacing:1px;padding:10px;}}"
                f"QPushButton:disabled{{background:{COLOR_LINE};color:{COLOR_MUTED};}}")
