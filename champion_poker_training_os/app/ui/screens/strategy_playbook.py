"""Strateji Planı (Playbook) — gerçek hayatta uygulanabilir uzun-vade
cash game + MTT yol haritası.

Bu ekran bir "antrenör"den çok bir SAHA REHBERİDİR: masaya oturduğunda
kafanda olması gereken karar çerçeveleri. İçerik, modern solver-çağı pro
konsensüsüne (Upswing / GTOWizard / RIO mantığı) dayanır ama EZBER değil
ANLAYIŞ verir — her ilke "neden" ile gelir, böylece gerçek elde karar
verirken uygulayabilirsin.

İki mod: CASH GAME (6-max derin stack) ve MTT (turnuva, ICM duyarlı).
Her bölüm bir kart; kartlar ilgili trainer'a "Pratik yap" ile bağlanır.
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from app.core.app_state import AppState
# Playbook İÇERİĞİ tek doğru kaynaktan gelir (app.poker.playbook) — AI Koç da
# aynı veriyi kullanır, böylece ekran ile koç birebir tutarlıdır.
from app.poker.playbook import CASH_PLAYBOOK, MTT_PLAYBOOK

# ── Tema renkleri (diğer ekranlarla tutarlı) ─────────────────────────
_ACCENT = "#5ad17a"   # yeşil — ana vurgu
_INFO   = "#5ad1ce"   # cyan
_WARN   = "#d6c668"   # amber — dikkat
_DANGER = "#e87474"   # kırmızı — tuzak
_MUTED  = "#898d80"


# ── Kart bileşeni ────────────────────────────────────────────────────
def _section_card(section: dict, on_link) -> QFrame:
    card = QFrame()
    card.setObjectName("GTOCard")
    accent = section["accent"]
    card.setStyleSheet(
        f"QFrame#GTOCard {{ background:#131613; border:1px solid #33382c; "
        f"border-left:3px solid {accent}; border-radius:6px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)

    title = QLabel(section["title"])
    title.setStyleSheet(
        f"color:{accent}; font-size:15px; font-weight:700;")
    title.setWordWrap(True)
    lay.addWidget(title)

    frame_lbl = QLabel(section["frame"])
    frame_lbl.setObjectName("Muted")
    frame_lbl.setWordWrap(True)
    frame_lbl.setStyleSheet("font-style:italic; color:#b9bcae; font-size:12px;")
    lay.addWidget(frame_lbl)

    for rule, why in section["rules"]:
        item = QVBoxLayout()
        item.setSpacing(2)
        r = QLabel(f"▸ {rule}")
        r.setWordWrap(True)
        r.setStyleSheet("color:#f4f5ee; font-size:13px; font-weight:600;")
        item.addWidget(r)
        w = QLabel(f"    └ Neden: {why}")
        w.setWordWrap(True)
        w.setStyleSheet("color:#898d80; font-size:12px;")
        item.addWidget(w)
        lay.addLayout(item)

    link = section.get("link")
    if link:
        label, target = link
        btn = QPushButton(f"⟶  Pratik: {label}")
        btn.setObjectName("NavButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{accent}; "
            f"border:1px solid {accent}; border-radius:4px; padding:6px 10px; "
            f"font-size:12px; text-align:left; }} "
            f"QPushButton:hover {{ background:{accent}; color:#0d0f0c; }}")
        btn.clicked.connect(lambda _=False, t=target: on_link(t))
        lay.addWidget(btn)

    return card


class StrategyPlaybookScreen(QWidget):
    """Gerçek-hayat uzun-vade cash + MTT strateji rehberi."""

    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._mode = "cash"

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self._layout = QVBoxLayout(body)
        self._layout.setContentsMargins(28, 24, 28, 28)
        self._layout.setSpacing(16)

        # Başlık
        title = QLabel("Strateji Planı — Saha Rehberi")
        title.setObjectName("Title")
        title.setStyleSheet("font-size:22px; font-weight:800; color:#f4f5ee;")
        self._layout.addWidget(title)

        sub = QLabel(
            "Gerçek hayatta masaya oturduğunda kafanda olması gereken uzun-vade "
            "karar çerçeveleri. Ezber değil ANLAYIŞ: her ilke 'neden'iyle gelir. "
            "GTO temelin — para disiplin + sömürüden gelir."
        )
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        self._layout.addWidget(sub)

        # Mod seçici
        toggle = QHBoxLayout()
        toggle.setSpacing(8)
        self._cash_btn = QPushButton("♠  CASH GAME")
        self._mtt_btn = QPushButton("♣  MTT (Turnuva)")
        for b in (self._cash_btn, self._mtt_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
        self._cash_btn.clicked.connect(lambda: self._set_mode("cash"))
        self._mtt_btn.clicked.connect(lambda: self._set_mode("mtt"))
        toggle.addWidget(self._cash_btn)
        toggle.addWidget(self._mtt_btn)
        toggle.addStretch(1)
        self._layout.addLayout(toggle)

        # İçerik kabı
        self._content = QVBoxLayout()
        self._content.setSpacing(14)
        self._layout.addLayout(self._content)
        self._layout.addStretch(1)

        self._set_mode("cash")

    # ── mod ──
    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._cash_btn.setChecked(mode == "cash")
        self._mtt_btn.setChecked(mode == "mtt")
        active = "#5ad17a"
        for b, on in ((self._cash_btn, mode == "cash"),
                      (self._mtt_btn, mode == "mtt")):
            if on:
                b.setStyleSheet(
                    f"QPushButton {{ background:{active}; color:#0d0f0c; "
                    f"border:none; border-radius:5px; padding:9px 18px; "
                    f"font-size:13px; font-weight:700; }}")
            else:
                b.setStyleSheet(
                    "QPushButton { background:#131613; color:#898d80; "
                    "border:1px solid #33382c; border-radius:5px; "
                    "padding:9px 18px; font-size:13px; }")
        self._render()

    def _render(self) -> None:
        while self._content.count():
            it = self._content.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        sections = CASH_PLAYBOOK if self._mode == "cash" else MTT_PLAYBOOK
        for sec in sections:
            self._content.addWidget(_section_card(sec, self._goto))

    def _goto(self, target: str) -> None:
        self.navigate_requested.emit(target)
