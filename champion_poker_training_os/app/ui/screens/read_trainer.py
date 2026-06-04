"""Opponent Read Trainer ekranı (geliştirme #2).

Villain'in DAVRANIŞINDAN (tell'ler) tipini oku; tahminden SONRA gerçek stat +
exploit açılır. 'Doğru oyun rakibe + okumaya göre değişir' becerisini drill'ler.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.poker.read_trainer import generate_read_drill, score_read


class ReadTrainerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self._rng = random.Random()
        self._drill = None
        self._answered = False
        self._correct = 0
        self._total = 0

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

        title = QLabel("Opponent Read Trainer — Rakibi Oku")
        title.setObjectName("Title")
        L.addWidget(title)
        sub = QLabel("Villain'in DAVRANIŞINDAN tipini oku — 'doğru oyun rakibe "
                     "ve okumana göre değişir'. Tahminden sonra gerçek stat açılır.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        L.addWidget(sub)

        self.acc_lbl = QLabel("Okuma doğruluğu: — (0/0)")
        self.acc_lbl.setObjectName("Cyan")
        L.addWidget(self.acc_lbl)

        # Villain davranış kartı
        card = QFrame()
        card.setObjectName("ReadCard")
        card.setStyleSheet("QFrame#ReadCard{background:#131613;border:1px solid "
                           "#23271f;border-radius:10px;}")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(18, 16, 18, 16)
        self.villain_lbl = QLabel()
        self.villain_lbl.setObjectName("SectionTitle")
        cv.addWidget(self.villain_lbl)
        self.tells_lbl = QLabel()
        self.tells_lbl.setWordWrap(True)
        self.tells_lbl.setStyleSheet("color:#d7dcc8; font-size:13px; line-height:1.7;")
        cv.addWidget(self.tells_lbl)
        L.addWidget(card)

        # Tip seçim butonları
        q = QLabel("Bu villain hangi tip? (davranışa göre seç)")
        q.setObjectName("Muted")
        L.addWidget(q)
        self.choice_row = QHBoxLayout()
        self.choice_row.setSpacing(8)
        L.addLayout(self.choice_row)
        self._choice_btns = []

        # Sonuç / reveal
        self.result_lbl = QLabel()
        self.result_lbl.setWordWrap(True)
        self.result_lbl.setStyleSheet("font-size:13px; padding:6px 0;")
        L.addWidget(self.result_lbl)

        self.next_btn = QPushButton("Sonraki rakip →")
        self.next_btn.clicked.connect(self._new_drill)
        self.next_btn.setVisible(False)
        L.addWidget(self.next_btn)
        L.addStretch(1)

        self._new_drill()

    def _new_drill(self):
        self._drill = generate_read_drill(self._rng)
        self._answered = False
        d = self._drill
        self.villain_lbl.setText(f"🎭 {d.villain_name}  ·  {d.stats['hands']} el gözlem")
        self.tells_lbl.setText("Gözlemlerin:\n" +
                               "\n".join(f"  • {t}" for t in d.action_log))
        self.result_lbl.setText("")
        self.next_btn.setVisible(False)
        # Seçim butonlarını yenile
        for b in self._choice_btns:
            b.setParent(None)
            b.deleteLater()
        self._choice_btns = []
        for choice in d.choices:
            b = QPushButton(choice)
            b.setStyleSheet("QPushButton{background:#1a1e16;color:#e8ecd8;border:"
                            "1px solid #2a3322;border-radius:6px;padding:8px 14px;}"
                            "QPushButton:hover{border-color:#5ad17a;}")
            b.clicked.connect(lambda _=False, c=choice: self._guess(c))
            self.choice_row.addWidget(b)
            self._choice_btns.append(b)

    def _guess(self, choice: str):
        if self._answered or not self._drill:
            return
        self._answered = True
        self._total += 1
        r = score_read(choice, self._drill)
        if r["correct"]:
            self._correct += 1
        color = "#5ad17a" if r["correct"] else "#e87474"
        self.result_lbl.setStyleSheet(f"font-size:13px;padding:6px 0;color:{color};")
        self.result_lbl.setText(f"{r['explanation']}\n\n🎯 Exploit: {r['exploit']}")
        acc = 100 * self._correct / max(self._total, 1)
        self.acc_lbl.setText(
            f"Okuma doğruluğu: %{acc:.0f} ({self._correct}/{self._total})")
        for b in self._choice_btns:
            b.setEnabled(False)
        self.next_btn.setVisible(True)
        self.coach_message.emit(
            f"Rakip okuma: {self._drill.correct_type}. {self._drill.correct_exploit}")
