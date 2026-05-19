"""Range Studio — birleşik ekran: GTO Trainer + Range Viewer + Range Trainer.

Bu 3 ekran çok benzer şeyler yapıyordu (13×13 grid, hand strategy, range visual).
Tek bir Range Studio çatısı altında 3 sekme:

  1. Trainer   — spot library + decision flow (eski GTO Trainer)
  2. Viewer    — solver chart browse (eski Range Viewer)
  3. Drill     — flash-card style range memorization (eski Range Trainer)

Sidebar'da tek '🎯 Range Studio' item'i. Eski 3 ekran wrapper'ları
backward-compat için tutuldu — onları açanlar Range Studio'ya yönlenir.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.ui.screens.gto_trainer import GTOTrainerScreen
from app.ui.screens.range_trainer import RangeTrainerScreen
from app.ui.screens.range_viewer import RangeViewerScreen


# Poke-aligned constants (legacy _C_* names preserved for diff sanity)
from app.ui.theme import poke_tokens as _t
_C_BG     = _t.BG
_C_CARD   = _t.SURFACE
_C_PANEL  = _t.SURFACE
_C_BORDER = _t.LINE
_C_MUTED  = _t.MUTED
_C_TEXT   = _t.INK
_C_CYAN   = _t.ACCENT
_C_GREEN  = _t.ACCENT
_C_RED    = _t.DANGER
_C_BLUE   = _t.INFO
_C_AMBER  = _t.WARN
_C_PURPLE = _t.INFO


def _tab_btn(label: str, active: bool) -> QPushButton:
    b = QPushButton(label)
    b.setCheckable(True)
    b.setChecked(active)
    b.setFixedHeight(36)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{_C_MUTED};"
        f"border:none;border-bottom:2px solid transparent;"
        f"padding:0 22px;font-size:13px;font-weight:700;}}"
        f"QPushButton:hover{{color:{_C_TEXT};}}"
        f"QPushButton:checked{{color:{_C_CYAN};border-bottom-color:{_C_CYAN};}}"
    )
    return b


class RangeStudioScreen(QWidget):
    """Unified Trainer / Viewer / Drill experience for ranges."""
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setStyleSheet(f"background:{_C_BG};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Tab bar ────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border-bottom:1px solid {_C_BORDER};}}"
        )
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 4, 20, 4)
        bar_layout.setSpacing(0)

        title = QLabel("🎯  Range Studio")
        title.setStyleSheet(
            f"color:{_C_TEXT};font-size:15px;font-weight:800;padding-right:30px;"
        )
        bar_layout.addWidget(title)

        self._tab_buttons: list[QPushButton] = []
        tabs = [
            ("Trainer",  "Spot kütüphanesi + karar pratiği"),
            ("Viewer",   "Solver chart inceleme"),
            ("Drill",    "Hand-by-hand range ezberleme"),
        ]
        for i, (name, _hint) in enumerate(tabs):
            btn = _tab_btn(name, i == 0)
            btn.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            self._tab_buttons.append(btn)
            bar_layout.addWidget(btn)
        bar_layout.addStretch(1)

        # Quick hint label on the right
        hint = QLabel("Trainer = pratik · Viewer = chart · Drill = ezber")
        hint.setStyleSheet(f"color:{_C_MUTED};font-size:11px;")
        bar_layout.addWidget(hint)
        root.addWidget(bar)

        # ── Stacked content ────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{_C_BG};")
        # Embed the underlying screens
        self._trainer = GTOTrainerScreen(state)
        self._viewer  = RangeViewerScreen(state)
        self._drill   = RangeTrainerScreen(state)
        self._stack.addWidget(self._trainer)
        self._stack.addWidget(self._viewer)
        self._stack.addWidget(self._drill)

        # Forward coach_message signals from the underlying screens
        for sub in (self._trainer, self._viewer, self._drill):
            if hasattr(sub, "coach_message"):
                sub.coach_message.connect(self.coach_message.emit)
            if hasattr(sub, "navigate_requested"):
                sub.navigate_requested.connect(self.navigate_requested.emit)

        root.addWidget(self._stack, 1)

    def _switch(self, idx: int) -> None:
        for i, b in enumerate(self._tab_buttons):
            b.setChecked(i == idx)
        self._stack.setCurrentIndex(idx)
