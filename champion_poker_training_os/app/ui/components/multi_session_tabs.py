"""MultiSessionTabs — host multiple parallel screens (Play Session, Tournament).

Wraps a screen class so the user can keep N parallel sessions / tournaments
open at the same time. Each tab is an independent instance — its own
PokerGame, LiveHUD, setup state. Switching tabs is instant; state is
preserved because every tab keeps its own QStackedWidget child alive.

Signals (``coach_message``, ``hand_completed``, ``navigate_requested``)
are forwarded from every tab so the global Coach / sidebar / main window
keep working transparently — no callsite changes needed in main.py.

The top strip uses the brutalist dark-theme palette (#0a0c0a / #131613 /
#5ad17a) so it visually matches the rest of the app.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)


class _Tab(QFrame):
    """Single tab pill — title + close button."""

    activated = Signal(object)   # self
    closed = Signal(object)      # self

    def __init__(self, title: str, can_close: bool = True):
        super().__init__()
        self.setObjectName("MultiSessionTab")
        self.setCursor(Qt.PointingHandCursor)
        self._active = False
        self._can_close = can_close

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 6, 6)
        h.setSpacing(8)

        self.label = QLabel(title)
        self.label.setObjectName("MultiSessionTabLabel")
        h.addWidget(self.label)

        # ASCII "X" with bigger font so it actually renders in the small tab
        self.close_btn = QPushButton("X")
        self.close_btn.setObjectName("MultiSessionTabClose")
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setToolTip("Bu sekmeyi kapat")
        self.close_btn.clicked.connect(lambda: self.closed.emit(self))
        self.close_btn.setVisible(can_close)
        h.addWidget(self.close_btn)

        self._apply_style()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.activated.emit(self)
        super().mousePressEvent(ev)

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def set_title(self, title: str) -> None:
        self.label.setText(title)

    def set_can_close(self, can: bool) -> None:
        self._can_close = can
        self.close_btn.setVisible(can)

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                "QFrame#MultiSessionTab { background:#11241a; "
                "border:1px solid #5ad17a; border-bottom:none; }"
                "QLabel#MultiSessionTabLabel { color:#5ad17a; background:transparent; "
                "font-family:'JetBrains Mono',monospace; font-size:11px; "
                "font-weight:700; letter-spacing:1.4px; }"
                "QPushButton#MultiSessionTabClose { background:transparent; "
                "color:#5ad17a; border:none; font-family:'JetBrains Mono','Menlo',monospace; "
                "font-size:12px; font-weight:800; padding:0; }"
                "QPushButton#MultiSessionTabClose:hover { color:#e87474; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#MultiSessionTab { background:#0f1210; "
                "border:1px solid #23271f; border-bottom:1px solid #5ad17a; }"
                "QLabel#MultiSessionTabLabel { color:#898d80; background:transparent; "
                "font-family:'JetBrains Mono',monospace; font-size:11px; "
                "font-weight:600; letter-spacing:1.4px; }"
                "QFrame#MultiSessionTab:hover QLabel#MultiSessionTabLabel { color:#d6d8cf; }"
                "QPushButton#MultiSessionTabClose { background:transparent; "
                "color:#5a5e54; border:none; font-family:'JetBrains Mono','Menlo',monospace; "
                "font-size:12px; font-weight:800; padding:0; }"
                "QPushButton#MultiSessionTabClose:hover { color:#e87474; }"
            )


class MultiSessionTabs(QWidget):
    """Host multiple parallel screens with a tab bar on top.

    Usage:
        host = MultiSessionTabs(
            screen_factory=lambda: PlaySessionScreen(app_state),
            title_prefix="Session",
            forward_signals=["coach_message", "hand_completed", "navigate_requested"],
        )
        # Then connect host.coach_message etc. exactly like the single screen.
    """

    # Re-emitted from any active tab so existing main.py hooks keep working
    coach_message = Signal(str)
    hand_completed = Signal(dict)
    navigate_requested = Signal(str)
    tournament_advice_requested = Signal(str)

    MAX_TABS = 6

    def __init__(
        self,
        screen_factory: Callable[[], QWidget],
        title_prefix: str = "Session",
        forward_signals: Optional[List[str]] = None,
    ):
        super().__init__()
        self._factory = screen_factory
        self._title_prefix = title_prefix
        self._forward = forward_signals or [
            "coach_message", "hand_completed", "navigate_requested",
            "tournament_advice_requested",
        ]
        self._tabs: List[_Tab] = []
        self._screens: List[QWidget] = []
        self._active_idx = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── TAB STRIP ──────────────────────────────────────────────
        strip = QFrame()
        strip.setObjectName("MultiSessionStrip")
        strip.setStyleSheet(
            "QFrame#MultiSessionStrip { background:#0a0c0a; "
            "border-bottom:1px solid #23271f; }"
        )
        strip_l = QHBoxLayout(strip)
        strip_l.setContentsMargins(14, 8, 14, 0)
        strip_l.setSpacing(2)

        self._tabs_box = QHBoxLayout()
        self._tabs_box.setSpacing(2)
        strip_l.addLayout(self._tabs_box)

        self.new_btn = QPushButton("+  NEW")
        self.new_btn.setObjectName("MultiSessionNewBtn")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.setStyleSheet(
            "QPushButton#MultiSessionNewBtn { background:#0f2318; color:#5ad17a; "
            "border:1px solid #5ad17a; font-family:'JetBrains Mono',monospace; "
            "font-size:11px; font-weight:700; letter-spacing:1.4px; padding:5px 14px; "
            "margin-left:8px; }"
            "QPushButton#MultiSessionNewBtn:hover { background:#143020; }"
            "QPushButton#MultiSessionNewBtn:disabled { background:#0f1210; "
            "color:#33382c; border-color:#23271f; }"
        )
        self.new_btn.setToolTip(f"Yeni paralel {title_prefix.lower()} aç")
        self.new_btn.clicked.connect(self.add_tab)
        strip_l.addWidget(self.new_btn)
        strip_l.addStretch(1)

        # Live count + hint on right
        self.count_label = QLabel("")
        self.count_label.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:10px; "
            "letter-spacing:1.5px; color:#5a5e54; background:transparent; padding-right:4px;"
        )
        strip_l.addWidget(self.count_label)
        root.addWidget(strip)

        # ── SCREEN STACK ───────────────────────────────────────────
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # First tab on init
        self.add_tab()

    # ── public API ──────────────────────────────────────────────────

    def add_tab(self) -> None:
        if len(self._tabs) >= self.MAX_TABS:
            return
        screen = self._factory()
        # Forward declared signals
        for sig_name in self._forward:
            sig = getattr(screen, sig_name, None)
            host_sig = getattr(self, sig_name, None)
            if sig is not None and host_sig is not None:
                sig.connect(host_sig)

        idx = len(self._screens)
        self._screens.append(screen)
        self.stack.addWidget(screen)

        tab = _Tab(self._tab_title(idx))
        tab.activated.connect(self._on_tab_activated)
        tab.closed.connect(self._on_tab_closed)
        self._tabs.append(tab)
        self._tabs_box.addWidget(tab)

        self._set_active(idx)
        self._refresh_strip()

    def active_screen(self) -> Optional[QWidget]:
        if 0 <= self._active_idx < len(self._screens):
            return self._screens[self._active_idx]
        return None

    def screens(self) -> List[QWidget]:
        return list(self._screens)

    # ── internal ────────────────────────────────────────────────────

    def _tab_title(self, idx: int) -> str:
        return f"{self._title_prefix.upper()} {idx + 1}"

    def _on_tab_activated(self, tab: _Tab) -> None:
        if tab in self._tabs:
            self._set_active(self._tabs.index(tab))

    def _on_tab_closed(self, tab: _Tab) -> None:
        if len(self._tabs) <= 1:
            return  # never close the last one
        idx = self._tabs.index(tab)
        screen = self._screens.pop(idx)
        self._tabs.pop(idx)
        self.stack.removeWidget(screen)
        screen.setParent(None)
        screen.deleteLater()
        tab.setParent(None)
        tab.deleteLater()
        # Pick a sensible new active index
        new_idx = min(idx, len(self._tabs) - 1)
        self._set_active(new_idx)
        self._refresh_strip()

    def _set_active(self, idx: int) -> None:
        if not (0 <= idx < len(self._screens)):
            return
        self._active_idx = idx
        self.stack.setCurrentIndex(idx)
        for i, t in enumerate(self._tabs):
            t.set_active(i == idx)

    def _refresh_strip(self) -> None:
        # Re-title every tab (keeps numbering stable after close)
        for i, t in enumerate(self._tabs):
            t.set_title(self._tab_title(i))
            t.set_can_close(len(self._tabs) > 1)
        self.count_label.setText(
            f"{len(self._tabs)} / {self.MAX_TABS} TABS"
        )
        self.new_btn.setEnabled(len(self._tabs) < self.MAX_TABS)
