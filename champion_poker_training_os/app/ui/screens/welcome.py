"""Welcome / Home screen — crystal-clear "Start Here" layout.

Three giant workflow buttons dominate the top half so the user immediately
knows what to click. Stat cards + quick-links fill the bottom half.
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
_MUTED  = "#6B7280"
_CYAN   = "#22D3EE"
_GREEN  = "#10B981"
_AMBER  = "#F59E0B"
_RED    = "#EF4444"


def _btn(label: str, color: str) -> QPushButton:
    b = QPushButton(label)
    b.setMinimumHeight(56)
    b.setStyleSheet(
        f"QPushButton{{background:{color};color:#000;border:none;"
        "border-radius:10px;font-size:15px;font-weight:800;padding:0 24px;}}"
        f"QPushButton:hover{{opacity:0.88;background:{color}CC;}}"
    )
    return b


class _BigCard(QFrame):
    """Giant start-here card — icon + title + one-liner + CTA button."""
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, subtitle: str,
                 cta: str, target: str, accent: str, primary: bool = False):
        super().__init__()
        self._target = target
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        border = accent if primary else _BORDER
        self.setStyleSheet(
            f"QFrame{{background:{_PANEL};border:2px solid {border};"
            "border-radius:16px;}"
            f"QFrame:hover{{border-color:{accent};}}"
        )
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 26, 28, 24)
        v.setSpacing(0)

        il = QLabel(icon)
        il.setStyleSheet("font-size:48px;")
        v.addWidget(il)
        v.addSpacing(12)

        tl = QLabel(title)
        tl.setStyleSheet(f"color:{_TEXT};font-size:22px;font-weight:800;")
        v.addWidget(tl)
        v.addSpacing(6)

        sl = QLabel(subtitle)
        sl.setStyleSheet(f"color:{_MUTED};font-size:13px;")
        sl.setWordWrap(True)
        v.addWidget(sl)
        v.addStretch(1)

        btn = _btn(cta, accent)
        btn.setMinimumHeight(52)
        btn.clicked.connect(lambda: self.clicked.emit(self._target))
        v.addWidget(btn)


class _StatCard(QFrame):
    def __init__(self, label: str, value: str, accent: str = _CYAN):
        super().__init__()
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QFrame{{background:{_CARD};border:1px solid {_BORDER};"
            "border-radius:10px;}"
        )
        h = QVBoxLayout(self)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(2)
        vl = QLabel(value)
        vl.setStyleSheet(f"color:{accent};font-size:24px;font-weight:800;")
        ll = QLabel(label)
        ll.setStyleSheet(f"color:{_MUTED};font-size:11px;font-weight:600;")
        h.addWidget(vl)
        h.addWidget(ll)


class _QuickLink(QPushButton):
    def __init__(self, icon: str, label: str, target: str):
        super().__init__(f"{icon}  {label}")
        self._target = target
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet(
            f"QPushButton{{background:{_CARD};color:{_TEXT};"
            f"border:1px solid {_BORDER};border-radius:8px;"
            "font-size:12px;font-weight:600;padding:0 12px;text-align:left;}}"
            f"QPushButton:hover{{border-color:{_CYAN};color:{_CYAN};}}"
        )


class WelcomeScreen(QWidget):
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setStyleSheet(f"background:{_BG};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        content = QWidget()
        content.setStyleSheet(f"background:{_BG};")
        root = QVBoxLayout(content)
        root.setContentsMargins(32, 28, 32, 32)
        root.setSpacing(24)

        # ── Header ───────────────────────────────────────────────────────
        hl = QHBoxLayout()
        title = QLabel("♠  Champion Poker Training OS")
        title.setStyleSheet(f"color:{_TEXT};font-size:28px;font-weight:800;")
        sub = QLabel("GTO-tabanlı offline poker antrenmanı")
        sub.setStyleSheet(f"color:{_MUTED};font-size:14px;")
        hl.addWidget(title)
        hl.addStretch(1)
        hl.addWidget(sub, 0, Qt.AlignVCenter)
        root.addLayout(hl)

        # ── "NEREDEN BAŞLAYACAĞIM" label ─────────────────────────────────
        start_lbl = QLabel("NEREDEN BAŞLAYACAĞIM?")
        start_lbl.setStyleSheet(
            f"color:{_CYAN};font-size:11px;font-weight:700;letter-spacing:2px;"
        )
        root.addWidget(start_lbl)

        # ── 3 giant start-here cards ─────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        learn = _BigCard(
            "📐", "GTO Trainer",
            "Range matrisi + spot kütüphanesi. Preflop stratejini öğren, "
            "pozisyon × pot tipi için her elleri gör.",
            "→  GTO TRAINER'A GİT", "GTO Trainer (Range View)",
            _CYAN, primary=True,
        )
        learn.clicked.connect(self.navigate_requested)
        cards_row.addWidget(learn)

        practice = _BigCard(
            "🎯", "Spot Antrenman",
            "325 hazır spot. Bir el gör, karar ver — fold / call / raise / jam. "
            "GTO frekansı anında gösterilir.",
            "→  SPOT'LARA GİT", "Spot Practice Trainer",
            _GREEN,
        )
        practice.clicked.connect(self.navigate_requested)
        cards_row.addWidget(practice)

        play = _BigCard(
            "🃏", "Masa Oyna",
            "Bot masasında gerçek eller oyna. "
            "Dealer dönüşü, blindler, side-pot ve sonuç — tam oyun.",
            "→  MASAYA OTU", "Play Session",
            _AMBER,
        )
        play.clicked.connect(self.navigate_requested)
        cards_row.addWidget(play)

        root.addLayout(cards_row)

        # ── Stat bar ─────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        drills_val = str(state.completed_drills) if state.completed_drills else "0"
        acc_val = f"{state.accuracy:.0f}%" if state.accuracy else "—"
        ev_val = f"{state.ev_loss_total:.1f}bb" if state.ev_loss_total else "0.0bb"
        for label, val, acc in [
            ("Tamamlanan Drill", drills_val, _CYAN),
            ("Doğruluk", acc_val, _GREEN),
            ("EV Kaybı (toplam)", ev_val, _RED),
            ("Katalog", "325 spot", _AMBER),
        ]:
            stats_row.addWidget(_StatCard(label, val, acc))
        root.addLayout(stats_row)

        # ── Quick-links grid ─────────────────────────────────────────────
        ql_lbl = QLabel("HIZLI BAĞLANTILAR")
        ql_lbl.setStyleSheet(
            f"color:{_MUTED};font-size:10px;font-weight:700;letter-spacing:1.5px;"
        )
        root.addWidget(ql_lbl)

        grid = QGridLayout()
        grid.setSpacing(8)
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
        outer.addWidget(scroll)
