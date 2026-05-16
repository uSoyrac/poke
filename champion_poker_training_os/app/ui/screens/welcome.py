"""Welcome / Home screen — büyük 'Start Here' kartlarıyla net giriş ekranı.

Tüm stil objectName ile scope'lanır ki child widget'lara cascade etmesin.
Kartlara explicit min-yükseklik verilir ki scroll'da ezilmesin.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState

_BG     = "#0A0E14"
_CARD   = "#0F141C"
_PANEL  = "#131A24"
_BORDER = "#1E2733"
_TEXT   = "#E5E7EB"
_MUTED  = "#9CA3AF"
_CYAN   = "#22D3EE"
_GREEN  = "#10B981"
_AMBER  = "#F59E0B"
_RED    = "#EF4444"


class _BigCard(QFrame):
    """Büyük 'tıkla-başla' kartı — ikon + başlık + alt yazı + buton."""
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, subtitle: str,
                 cta: str, target: str, accent: str):
        super().__init__()
        self._target = target
        self.setObjectName("BigCard")
        self.setFrameShape(QFrame.NoFrame)
        # Kartların boyutu sabit minimum'a sahip olmalı ki scroll'da ezilmesin
        self.setMinimumSize(280, 320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame#BigCard {{"
            f"  background: {_PANEL};"
            f"  border: 2px solid {accent};"
            f"  border-radius: 16px;"
            f"}}"
            f"QFrame#BigCard:hover {{"
            f"  background: #1A2333;"
            f"}}"
        )

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 22)
        v.setSpacing(0)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size: 44px; background: transparent; color: {_TEXT};")
        v.addWidget(icon_lbl)
        v.addSpacing(14)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 22px; font-weight: 800; background: transparent;"
        )
        v.addWidget(title_lbl)
        v.addSpacing(8)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet(
            f"color: {_MUTED}; font-size: 13px; background: transparent; line-height: 1.5;"
        )
        sub_lbl.setWordWrap(True)
        sub_lbl.setMinimumHeight(64)
        v.addWidget(sub_lbl)
        v.addStretch(1)

        btn = QPushButton(cta)
        btn.setObjectName("BigCardCTA")
        btn.setMinimumHeight(52)
        btn.setCursor(Qt.PointingHandCursor)
        # Açık metin / koyu arkaplan ile yüksek kontrast
        btn.setStyleSheet(
            f"QPushButton#BigCardCTA {{"
            f"  background: {accent};"
            f"  color: #061018;"
            f"  border: none;"
            f"  border-radius: 10px;"
            f"  font-size: 14px;"
            f"  font-weight: 800;"
            f"  padding: 0 18px;"
            f"  letter-spacing: 0.5px;"
            f"}}"
            f"QPushButton#BigCardCTA:hover {{"
            f"  background: {accent};"
            f"}}"
        )
        btn.clicked.connect(lambda: self.clicked.emit(self._target))
        v.addWidget(btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._target)
        super().mousePressEvent(event)


class _StatCard(QFrame):
    def __init__(self, label: str, value: str, accent: str = _CYAN):
        super().__init__()
        self.setObjectName("StatCard")
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(88)
        self.setMinimumWidth(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame#StatCard {{"
            f"  background: {_CARD};"
            f"  border: 1px solid {_BORDER};"
            f"  border-radius: 10px;"
            f"}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(4)
        val = QLabel(value)
        val.setStyleSheet(
            f"color: {accent}; font-size: 24px; font-weight: 800; background: transparent;"
        )
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {_MUTED}; font-size: 11px; font-weight: 600; background: transparent;"
        )
        v.addWidget(val)
        v.addWidget(lbl)


class _QuickLink(QPushButton):
    def __init__(self, icon: str, label: str, target: str):
        super().__init__(f"  {icon}   {label}")
        self.setObjectName("QuickLink")
        self._target = target
        self.setMinimumHeight(46)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QPushButton#QuickLink {{"
            f"  background: {_CARD};"
            f"  color: {_TEXT};"
            f"  border: 1px solid {_BORDER};"
            f"  border-radius: 8px;"
            f"  font-size: 13px;"
            f"  font-weight: 600;"
            f"  padding: 0 14px;"
            f"  text-align: left;"
            f"}}"
            f"QPushButton#QuickLink:hover {{"
            f"  border: 1px solid {_CYAN};"
            f"  color: {_CYAN};"
            f"  background: #0D1620;"
            f"}}"
        )


class WelcomeScreen(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setObjectName("WelcomeRoot")
        self.setStyleSheet(f"QWidget#WelcomeRoot {{ background: {_BG}; }}")

        # Scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 8px; background: transparent; }"
            "QScrollBar::handle:vertical { background: #2A3A50; border-radius: 4px; min-height: 24px; }"
        )

        content = QWidget()
        content.setObjectName("WelcomeContent")
        content.setStyleSheet(f"QWidget#WelcomeContent {{ background: {_BG}; }}")
        content.setMinimumHeight(820)  # Scroll içinde ezilmesin

        root = QVBoxLayout(content)
        root.setContentsMargins(36, 28, 36, 32)
        root.setSpacing(22)

        # ── Üst başlık ───────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("♠  Champion Poker Training OS")
        title.setStyleSheet(
            f"color: {_TEXT}; font-size: 26px; font-weight: 800; background: transparent;"
        )
        tag = QLabel("GTO tabanlı offline poker antrenmanı")
        tag.setStyleSheet(
            f"color: {_MUTED}; font-size: 13px; background: transparent;"
        )
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(tag, 0, Qt.AlignVCenter)
        root.addLayout(header)

        # ── "NEREDEN BAŞLA" etiketi ──────────────────────────────────
        kicker = QLabel("▸  NEREDEN BAŞLAYACAĞIM?")
        kicker.setStyleSheet(
            f"color: {_CYAN}; font-size: 11px; font-weight: 800;"
            f" letter-spacing: 2px; background: transparent; padding-top: 8px;"
        )
        root.addWidget(kicker)

        # ── 3 büyük kart ─────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(18)

        learn = _BigCard(
            "📐", "GTO Trainer",
            "13×13 range matrisi ve 325 hazır spot kütüphanesi. "
            "Pozisyon × pot tipi için her elin GTO frekansını gör.",
            "GTO TRAINER'A GİT  →", "Range Studio", _CYAN,
        )
        learn.clicked.connect(self.navigate_requested)
        cards_row.addWidget(learn)

        practice = _BigCard(
            "🎯", "Spot Antrenman",
            "Bir el gör, karar ver: FOLD / CALL / RAISE / JAM. "
            "Anlık geri bildirim ve GTO doğruluk bar'ı.",
            "SPOT'LARA GİT  →", "Spot Practice Trainer", _GREEN,
        )
        practice.clicked.connect(self.navigate_requested)
        cards_row.addWidget(practice)

        play = _BigCard(
            "🃏", "Masa Oyna",
            "Bot masasında gerçek eller oyna. Dealer dönüşü, blindler, "
            "side-pot, showdown — tam poker deneyimi.",
            "MASAYA OTUR  →", "Play Session", _AMBER,
        )
        play.clicked.connect(self.navigate_requested)
        cards_row.addWidget(play)

        root.addLayout(cards_row)

        # ── İstatistik bar ───────────────────────────────────────────
        stats_kicker = QLabel("İLERLEMEN")
        stats_kicker.setStyleSheet(
            f"color: {_MUTED}; font-size: 10px; font-weight: 800;"
            f" letter-spacing: 1.5px; background: transparent; padding-top: 6px;"
        )
        root.addWidget(stats_kicker)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        drills = str(state.completed_drills) if state.completed_drills else "0"
        acc = f"{state.accuracy:.0f}%" if state.accuracy else "—"
        # Pull live data from My Mistakes + Tournament Archive
        try:
            from app.db.mistakes_queue import load_mistakes
            mistakes = load_mistakes()
            open_leaks = sum(1 for m in mistakes if not m.drilled)
            leaks_val = str(open_leaks) if open_leaks else "0"
        except Exception:
            leaks_val = "—"
        try:
            from app.db.tournament_archive import load_archive
            archive = load_archive()
            tours_val = str(len(archive)) if archive else "0"
        except Exception:
            tours_val = "—"
        for label, val, accent in [
            ("Tamamlanan Drill", drills,    _CYAN),
            ("Doğruluk",         acc,       _GREEN),
            ("Açık Leak",        leaks_val, _RED),
            ("Turnuva",          tours_val, _AMBER),
        ]:
            stats.addWidget(_StatCard(label, val, accent))
        root.addLayout(stats)

        # ── Hızlı bağlantılar ────────────────────────────────────────
        ql_kicker = QLabel("HIZLI BAĞLANTILAR")
        ql_kicker.setStyleSheet(
            f"color: {_MUTED}; font-size: 10px; font-weight: 800;"
            f" letter-spacing: 1.5px; background: transparent; padding-top: 6px;"
        )
        root.addWidget(ql_kicker)

        grid = QGridLayout()
        grid.setSpacing(10)
        links = [
            ("🏆", "Turnuva Oyna",     "Tournament Play Mode"),
            ("⚔️",  "Heads-Up Trainer", "Heads-Up Trainer"),
            ("⚡", "Hızlı Oyun",       "Fast Play Simulator"),
            ("📚", "Çalışma Kitaplığı","GTO Study Library"),
            ("💪", "Drills",           "Drills"),
            ("🔬", "El Analiz",        "Hand History Analyzer"),
            ("🩺", "Leak Finder",      "Leak Finder"),
            ("💰", "ICM / PKO",        "ICM / PKO Trainer"),
            ("🌊", "Postflop",         "Postflop Trainer"),
            ("🏁", "River Trainer",    "River Decision Trainer"),
            ("🤖", "AI Coach",         "AI Poker Coach"),
            ("📈", "Raporlar",         "Reports"),
        ]
        cols = 4
        for idx, (icon, label, target) in enumerate(links):
            btn = _QuickLink(icon, label, target)
            btn.clicked.connect(lambda _=False, t=target: self.navigate_requested.emit(t))
            grid.addWidget(btn, idx // cols, idx % cols)
        root.addLayout(grid)

        root.addStretch(1)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)
