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

from typing import Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)


class _Tab(QFrame):
    """Single tab pill — title + float button + close button."""

    activated = Signal(object)   # self
    closed    = Signal(object)   # self
    floated   = Signal(object)   # self  ← new: pop this tab out to a floating window

    def __init__(self, title: str, can_close: bool = True):
        super().__init__()
        self.setObjectName("MultiSessionTab")
        self.setCursor(Qt.PointingHandCursor)
        self._active    = False
        self._can_close = can_close
        self._floating  = False

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 4, 6)
        h.setSpacing(6)

        self.label = QLabel(title)
        self.label.setObjectName("MultiSessionTabLabel")
        h.addWidget(self.label)

        # ⧉ Float — pops the tab into a standalone resizable window
        self.float_btn = QPushButton("⧉")
        self.float_btn.setObjectName("MultiSessionTabFloat")
        self.float_btn.setFixedSize(22, 22)
        self.float_btn.setCursor(Qt.PointingHandCursor)
        self.float_btn.setToolTip("Pop out to floating window")
        self.float_btn.clicked.connect(lambda: self.floated.emit(self))
        h.addWidget(self.float_btn)

        # X close button
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
        self.close_btn.setVisible(can and not self._floating)

    def set_floating(self, floating: bool) -> None:
        """Mark this tab as representing a floating window (dims the close X)."""
        self._floating = floating
        self.float_btn.setToolTip(
            "Bring floating window to front" if floating else "Pop out to floating window"
        )
        self.float_btn.setText("◫" if floating else "⧉")
        self.close_btn.setVisible(self._can_close and not floating)
        self._apply_style()

    def _apply_style(self) -> None:
        base_label = (
            "font-family:'JetBrains Mono',monospace; font-size:11px; "
            "font-weight:{weight}; letter-spacing:1.4px;"
        )
        btn_base = (
            "background:transparent; border:none; "
            "font-family:'JetBrains Mono','Menlo',monospace; "
            "font-size:12px; font-weight:800; padding:0;"
        )
        if self._floating:
            # Greyed-out — the game is in its own window
            self.setStyleSheet(
                "QFrame#MultiSessionTab { background:#0d1a14; "
                "border:1px solid #2a4a30; border-bottom:1px solid #5ad17a; }"
                f"QLabel#MultiSessionTabLabel {{ color:#3a6a48; background:transparent; "
                f"{base_label.format(weight=600)} }}"
                f"QPushButton#MultiSessionTabFloat {{ {btn_base} color:#3a6a48; }}"
                f"QPushButton#MultiSessionTabFloat:hover {{ color:#5ad17a; }}"
                f"QPushButton#MultiSessionTabClose {{ {btn_base} color:#2a3a28; }}"
            )
        elif self._active:
            self.setStyleSheet(
                "QFrame#MultiSessionTab { background:#11241a; "
                "border:1px solid #5ad17a; border-bottom:none; }"
                f"QLabel#MultiSessionTabLabel {{ color:#5ad17a; background:transparent; "
                f"{base_label.format(weight=700)} }}"
                f"QPushButton#MultiSessionTabFloat {{ {btn_base} color:#5ad17a; }}"
                f"QPushButton#MultiSessionTabFloat:hover {{ color:#5ad1ce; }}"
                f"QPushButton#MultiSessionTabClose {{ {btn_base} color:#5ad17a; }}"
                "QPushButton#MultiSessionTabClose:hover { color:#e87474; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#MultiSessionTab { background:#0f1210; "
                "border:1px solid #23271f; border-bottom:1px solid #5ad17a; }"
                f"QLabel#MultiSessionTabLabel {{ color:#898d80; background:transparent; "
                f"{base_label.format(weight=600)} }}"
                "QFrame#MultiSessionTab:hover QLabel#MultiSessionTabLabel { color:#d6d8cf; }"
                f"QPushButton#MultiSessionTabFloat {{ {btn_base} color:#5a5e54; }}"
                f"QPushButton#MultiSessionTabFloat:hover {{ color:#5ad1ce; }}"
                f"QPushButton#MultiSessionTabClose {{ {btn_base} color:#5a5e54; }}"
                "QPushButton#MultiSessionTabClose:hover { color:#e87474; }"
            )


# ── Floating table window ─────────────────────────────────────────────────

class _TableWindow(QMainWindow):
    """Standalone resizable window hosting a popped-out session/tournament screen.

    The screen is adopted as the window's central widget. All signals from the
    screen continue to flow to the `MultiSessionTabs` host because they were
    wired up in ``add_tab()``. Closing this window re-docks the screen back
    into the tab strip.
    """

    closed = Signal()   # emitted before Qt destroys the window

    def __init__(self, title: str, screen: QWidget):
        super().__init__()
        self.setWindowTitle(title)
        self.setMinimumSize(760, 580)
        self.resize(1024, 720)
        # Dark titlebar background to match app theme on platforms that support it
        self.setStyleSheet("QMainWindow { background:#0a0c0a; }")
        self.setCentralWidget(screen)
        # QStackedWidget.removeWidget() hides the widget — must re-show it
        screen.show()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.closed.emit()
        super().closeEvent(event)


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
        # {tab_idx: (_TableWindow, original_screen)}
        self._float_windows: Dict[int, Tuple[_TableWindow, QWidget]] = {}

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
        tab.floated.connect(self._on_tab_floated)
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
        # If this tab is floating, close the window first
        if idx in self._float_windows:
            win, orig_screen = self._float_windows.pop(idx)
            win.closed.disconnect()
            win.close()
            orig_screen.setParent(None)
            orig_screen.deleteLater()
        screen = self._screens.pop(idx)
        self._tabs.pop(idx)
        self.stack.removeWidget(screen)
        screen.setParent(None)
        screen.deleteLater()
        tab.setParent(None)
        tab.deleteLater()
        # Shift float_windows keys above idx
        updated: Dict[int, Tuple[_TableWindow, QWidget]] = {}
        for k, v in self._float_windows.items():
            updated[k - 1 if k > idx else k] = v
        self._float_windows = updated
        # Pick a sensible new active index
        new_idx = min(idx, len(self._tabs) - 1)
        self._set_active(new_idx)
        self._refresh_strip()

    # ── Float / undock ───────────────────────────────────────────────────

    def _on_tab_floated(self, tab: _Tab) -> None:
        if tab not in self._tabs:
            return
        idx = self._tabs.index(tab)

        # If already floating, bring the window to front
        if idx in self._float_windows:
            win, _ = self._float_windows[idx]
            win.raise_()
            win.activateWindow()
            return

        screen = self._screens[idx]
        title = f"{self._tab_title(idx)}  —  Champion OS"

        # Build a placeholder to fill the stack slot while the window is open
        ph = QFrame()
        ph.setStyleSheet("background:#0a0c0a;")
        ph_lbl = QLabel(
            f"⧉  {self._tab_title(idx)}  is in a floating window\n\n"
            "Click the ◫ tab button to bring it back.",
            ph,
        )
        ph_lbl.setAlignment(Qt.AlignCenter)
        ph_lbl.setStyleSheet(
            "color:#3a6a48; font-family:'JetBrains Mono',monospace; "
            "font-size:12px; letter-spacing:1px;"
        )
        ph_lbl.setGeometry(0, 0, 600, 80)
        ph.setMinimumHeight(200)

        # Swap screen → placeholder in the stack
        self.stack.removeWidget(screen)
        self.stack.insertWidget(idx, ph)
        self._screens[idx] = ph

        # Create and show the floating window
        win = _TableWindow(title, screen)
        win.closed.connect(lambda: self._return_from_float(idx))
        win.show()
        win.raise_()

        self._float_windows[idx] = (win, screen)
        tab.set_floating(True)
        self._set_active(idx)

    def _return_from_float(self, idx: int) -> None:
        """Re-dock a floating screen back into the stack at its original slot."""
        if idx not in self._float_windows:
            return
        win, screen = self._float_windows.pop(idx)

        # Sanity: ensure our placeholder is still in the stack at this slot
        if idx >= len(self._screens):
            screen.setParent(None)
            screen.deleteLater()
            return

        ph = self._screens[idx]

        # Reparent screen back into our widget hierarchy
        self.stack.removeWidget(ph)
        ph.setParent(None)
        ph.deleteLater()

        self.stack.insertWidget(idx, screen)
        self._screens[idx] = screen

        # Restore tab appearance
        if idx < len(self._tabs):
            self._tabs[idx].set_floating(False)

        self._set_active(idx)

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
