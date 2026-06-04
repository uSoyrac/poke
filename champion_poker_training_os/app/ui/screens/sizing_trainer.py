"""Bet-Sizing Trainer ekranı (geliştirme #4).

Spot + 'kaç bb basarsın?' → seçimi GTO-önerilene göre quality%/EV-loss ile puanla.
Sizing = GTO'nun aksiyon kadar önemli yarısı; bu beceriyi izole drill'ler.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.poker.sizing_trainer import generate_sizing_drill, score_sizing


class SizingTrainerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self._rng = random.Random()
        self._drill = None
        self._answered = False
        self._total = 0
        self._qsum = 0.0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        L = QVBoxLayout(body)
        L.setContentsMargins(22, 22, 22, 22)
        L.setSpacing(14)

        title = QLabel("Bet-Sizing Trainer — Kaç Basmalı?")
        title.setObjectName("Title")
        L.addWidget(title)
        sub = QLabel("GTO sadece aksiyon değil SIZING'dir. Spotu oku → doğru boyutu "
                     "seç → quality% + EV kaybı geri bildirimi al.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        L.addWidget(sub)

        self.acc_lbl = QLabel("Ortalama sizing kalitesi: — (0 drill)")
        self.acc_lbl.setObjectName("Cyan")
        L.addWidget(self.acc_lbl)

        card = QFrame()
        card.setObjectName("SizeCard")
        card.setStyleSheet("QFrame#SizeCard{background:#131613;border:1px solid "
                           "#23271f;border-radius:10px;}")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(18, 16, 18, 16)
        self.spot_lbl = QLabel()
        self.spot_lbl.setObjectName("SectionTitle")
        self.spot_lbl.setWordWrap(True)
        cv.addWidget(self.spot_lbl)
        self.detail_lbl = QLabel()
        self.detail_lbl.setStyleSheet("color:#d7dcc8; font-size:13px;")
        self.detail_lbl.setWordWrap(True)
        cv.addWidget(self.detail_lbl)
        L.addWidget(card)

        q = QLabel("Kaç basarsın?")
        q.setObjectName("Muted")
        L.addWidget(q)
        self.choice_row = QHBoxLayout()
        self.choice_row.setSpacing(8)
        L.addLayout(self.choice_row)
        self._choice_btns = []

        self.result_lbl = QLabel()
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setStyleSheet("font-size:13px; padding:6px 0;")
        L.addWidget(self.result_lbl)

        self.next_btn = QPushButton("Sonraki spot →")
        self.next_btn.clicked.connect(self._new_drill)
        self.next_btn.setVisible(False)
        L.addWidget(self.next_btn)
        L.addStretch(1)

        self._new_drill()

    def _new_drill(self):
        self._drill = generate_sizing_drill(self._rng)
        self._answered = False
        d = self._drill
        board = f"  ·  Board: {d.board}" if d.board else ""
        self.spot_lbl.setText(f"🎯 {d.scenario}")
        self.detail_lbl.setText(
            f"El: {d.hero_cards}{board}  ·  Pot: {d.pot_bb:.1f}bb")
        self.result_lbl.setText("")
        self.next_btn.setVisible(False)
        for b in self._choice_btns:
            b.setParent(None)
            b.deleteLater()
        self._choice_btns = []
        for size in d.choices_bb:
            pct = 100.0 * size / d.pot_bb if d.pot_bb else 0
            lbl = (f"{size:.1f}bb" if d.scenario_key in ("preflop_open", "threebet")
                   else f"{size:.1f}bb (%{pct:.0f})")
            b = QPushButton(lbl)
            b.setStyleSheet("QPushButton{background:#1a1e16;color:#e8ecd8;border:"
                            "1px solid #2a3322;border-radius:6px;padding:8px 12px;}"
                            "QPushButton:hover{border-color:#5ad17a;}")
            b.clicked.connect(lambda _=False, s=size: self._guess(s))
            self.choice_row.addWidget(b)
            self._choice_btns.append(b)

    def _guess(self, size: float):
        if self._answered or not self._drill:
            return
        self._answered = True
        r = score_sizing(size, self._drill)
        self._total += 1
        self._qsum += r["quality_pct"]
        good = r["quality_pct"] >= 80
        color = "#5ad17a" if good else "#e8c35a" if r["quality_pct"] >= 55 else "#e87474"
        self.result_lbl.setStyleSheet(f"font-size:13px;padding:6px 0;color:{color};")
        self.result_lbl.setText(
            f"Kalite %{r['quality_pct']:.0f} · EV kaybı ~{r['ev_loss_bb']:.2f}bb\n"
            f"{r['verdict']}\n✓ GTO: {self._drill.recommended_label} — {self._drill.note}")
        self.acc_lbl.setText(
            f"Ortalama sizing kalitesi: %{self._qsum / self._total:.0f} "
            f"({self._total} drill)")
        for b in self._choice_btns:
            b.setEnabled(False)
        self.next_btn.setVisible(True)
