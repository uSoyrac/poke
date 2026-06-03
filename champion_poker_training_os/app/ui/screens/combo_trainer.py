"""Combo Counting Trainer — river bluff-catch drill (gerçek masa hissi).

Random river spot dağıtılır (hero eli + 5-kart board + villain'ın polarize
bahis range'i). Sen kafadan value:bluff combo'yu sayıp CALL/FOLD dersin
(zaman kısıtı YOK). Sonra combinatorics motoru kesin cevabı + blocker'ı +
öğretici notu verir → combo sayımını gerçek masadaki gibi çalışırsın.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.poker.combo_drill import generate_spot, grade
from app.poker.combinatorics import coach_combo_line
from app.ui.components.poker_table import LivePokerTable
from app.ui.components.spot_table import render_spot_on_table

_ACCENT = "#5ad17a"
_INFO = "#5ad1ce"
_WARN = "#d6c668"
_DANGER = "#e87474"
_MUTED = "#898d80"
_CARD = "#131613"
_LINE = "#23271f"
_INK = "#f4f5ee"


class ComboTrainerScreen(QWidget):
    """River bluff-catch combo-sayım antrenörü."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state=None):
        super().__init__()
        self.state = state
        self._spot = None
        self._answered = False
        self._n = 0
        self._correct = 0
        self._streak = 0

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        L = QVBoxLayout(body)
        L.setContentsMargins(24, 20, 24, 24)
        L.setSpacing(14)

        title = QLabel("🎴 Combo Counting Trainer — River Bluff-Catch")
        title.setStyleSheet(f"font-size:21px; font-weight:800; color:{_INK};")
        L.addWidget(title)
        sub = QLabel(
            "Elit koç refleksi: TEK EL DEĞİL, COMBO SAY. Villain bahsine karşı "
            "range'indeki value vs bluff combo'yu kafadan tahmin et, pot odds'la "
            "kıyasla, CALL/FOLD ver. Sonra kesin combo + blocker analizini gör.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        L.addWidget(sub)

        # Masa + yan panel
        row = QHBoxLayout()
        row.setSpacing(14)
        self.table_view = LivePokerTable()
        self.table_view.setMinimumHeight(420)
        row.addWidget(self.table_view, 3)

        side = QVBoxLayout()
        side.setSpacing(10)
        self._situation = QLabel("—")
        self._situation.setWordWrap(True)
        self._situation.setStyleSheet(
            f"background:{_CARD}; border:1px solid {_LINE}; border-radius:8px; "
            f"padding:12px; color:{_INK}; font-size:13px;")
        side.addWidget(self._situation)

        self._stats = QLabel("Bu seans: 0/0  ·  streak 0")
        self._stats.setStyleSheet(f"color:{_MUTED}; font-size:12px; font-weight:700;")
        side.addWidget(self._stats)
        side.addStretch(1)
        rw = QWidget()
        rw.setLayout(side)
        rw.setFixedWidth(320)
        row.addWidget(rw)
        L.addLayout(row)

        # Aksiyon butonları
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self._call_btn = QPushButton("CALL")
        self._fold_btn = QPushButton("FOLD")
        self._call_btn.clicked.connect(lambda: self._answer("CALL"))
        self._fold_btn.clicked.connect(lambda: self._answer("FOLD"))
        for b, col in ((self._call_btn, _ACCENT), (self._fold_btn, _DANGER)):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(46)
            b.setStyleSheet(
                f"QPushButton {{ background:{col}; color:#0d0f0c; border:none; "
                f"border-radius:8px; font-size:16px; font-weight:800; "
                f"letter-spacing:1.5px; }} QPushButton:disabled {{ "
                f"background:{_LINE}; color:{_MUTED}; }}")
        self._next_btn = QPushButton("Sonraki El  ▸")
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setMinimumHeight(46)
        self._next_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{_INFO}; "
            f"border:1px solid {_INFO}; border-radius:8px; font-size:14px; "
            f"font-weight:700; padding:0 20px; }}")
        self._next_btn.clicked.connect(self._new_spot)
        btns.addWidget(self._call_btn, 1)
        btns.addWidget(self._fold_btn, 1)
        btns.addWidget(self._next_btn, 1)
        L.addLayout(btns)

        # Reveal / analiz
        self._reveal = QLabel("")
        self._reveal.setWordWrap(True)
        self._reveal.setTextFormat(Qt.RichText)
        self._reveal.setStyleSheet(
            f"background:{_CARD}; border:1px solid {_LINE}; border-radius:8px; "
            f"padding:14px; font-family:'JetBrains Mono',monospace; font-size:12px; "
            f"color:{_INK};")
        self._reveal.setVisible(False)
        L.addWidget(self._reveal)
        L.addStretch(1)

        self._new_spot()

    # ── akış ──
    def _new_spot(self) -> None:
        self._spot = generate_spot(rng=random)
        self._answered = False
        self._reveal.setVisible(False)
        self._call_btn.setEnabled(True)
        self._fold_btn.setEnabled(True)
        s = self._spot
        render_spot_on_table(self.table_view, s)
        bet = s["to_call_bb"]; pot = s["pot_bb"]
        odds = 100.0 * bet / (pot + bet)
        self._situation.setText(
            f"<b>RIVER</b> — Villain {bet:.0f}bb bahis attı (pot {pot:.0f}bb).<br><br>"
            f"{s['villain_desc']}<br><br>"
            f"Gereken equity (pot odds): <b>%{odds:.0f}</b><br>"
            f"Sence value &gt; bluff mi? Elin neyi blokluyor? <b>CALL mı FOLD mu?</b>")

    def _answer(self, action: str) -> None:
        if self._answered or not self._spot:
            return
        self._answered = True
        self._call_btn.setEnabled(False)
        self._fold_btn.setEnabled(False)
        g = grade(self._spot, action)
        self._n += 1
        if g["correct"]:
            self._correct += 1
            self._streak += 1
        else:
            self._streak = 0
        self._stats.setText(
            f"Bu seans: {self._correct}/{self._n} "
            f"(%{100*self._correct/max(self._n,1):.0f})  ·  streak {self._streak}")

        a = g["analysis"]
        head_col = _ACCENT if g["correct"] else _DANGER
        head = ("✓ DOĞRU" if g["correct"]
                else f"✗ YANLIŞ — doğrusu {g['correct_action']}")
        self._reveal.setText(
            f"<span style='color:{head_col}; font-weight:800; font-size:14px'>{head}"
            f"</span>  (senin: {g['your_action']})<br><br>"
            f"<span style='color:{_INFO}'>{coach_combo_line(a)}</span><br><br>"
            f"<span style='color:{_MUTED}'>Ders: villain'ın {a['value_combos']} value "
            f"vs {a['bluff_combos']} bluff combo'su var → hero ~%{a['win_pct']:.0f} "
            f"kazanır, pot odds %{a['needed_equity']:.0f} gerektiriyor. "
            f"Blocker: {a['blocker_verdict']}.</span>")
        self._reveal.setVisible(True)
        # Koça da bildir (sağ panelde görünsün)
        try:
            self.coach_message.emit(
                f"Combo drill: {head}. {coach_combo_line(a)}")
        except Exception:
            pass
