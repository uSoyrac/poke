"""Central shortcut registry + on-screen cheat sheet.

Single source of truth for every keybinding in the app. UI code registers
real ``QShortcut`` objects that resolve to callables; the cheat-sheet
dialog renders the same data for the user. Adding a new shortcut means
appending one row in ``SHORTCUTS`` and wiring it in the relevant screen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)


@dataclass(frozen=True)
class Shortcut:
    keys: str          # Display form, e.g. "Ctrl+B", "F", "Space"
    action: str        # Human-readable description
    context: str = ""  # Optional sub-context, e.g. "Play screen"


# Groups → list of (keys, action, optional context)
SHORTCUTS: List[tuple[str, List[Shortcut]]] = [
    ("Layout", [
        Shortcut("Ctrl+B", "Toggle sidebar"),
        Shortcut("Ctrl+J", "Toggle AI Coach panel"),
        Shortcut("?",      "Show this shortcut cheat sheet"),
        Shortcut("Esc",    "Close any open dialog"),
    ]),
    ("Navigation", [
        Shortcut("Ctrl+1", "Dashboard"),
        Shortcut("Ctrl+2", "Play Session"),
        Shortcut("Ctrl+3", "Tournament Simulator"),
        Shortcut("Ctrl+4", "GTO Study Library"),
        Shortcut("Ctrl+5", "Spot Practice Trainer"),
        Shortcut("Ctrl+6", "Hand History Analyzer"),
        Shortcut("Ctrl+7", "AI Poker Coach"),
        Shortcut("Ctrl+8", "Leak Finder"),
        Shortcut("Ctrl+9", "Reports"),
    ]),
    ("Play actions", [
        Shortcut("F",     "Fold",          "Play / Tournament"),
        Shortcut("C",     "Call (or Check if no bet)", "Play / Tournament"),
        Shortcut("R",     "Raise (or Bet)", "Play / Tournament"),
        Shortcut("A",     "All-in",        "Play / Tournament"),
        Shortcut("Space", "Deal next hand", "Play / Tournament"),
        Shortcut("Enter", "Confirm / advance", "Modals"),
    ]),
]


class ShortcutsDialog(QDialog):
    """Cheat-sheet overlay. Press ? anywhere to open, Esc to close."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setModal(True)
        self.resize(560, 580)
        self.setStyleSheet(
            "QDialog { background: #0a0c0a; border: 1px solid #33382c; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        # Header
        num = QLabel("KEYBOARD / SHORTCUTS")
        num.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; font-size: 10px; "
            "font-weight: 600; letter-spacing: 2px; color: #898d80;"
        )
        title = QLabel("Cheat sheet")
        title_font = QFont()
        title_font.setFamily("Space Grotesk")
        title_font.setPixelSize(28)
        title_font.setWeight(QFont.Bold)
        title.setFont(title_font)
        title.setStyleSheet("color: #f4f5ee; margin: 0;")
        root.addWidget(num)
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #23271f; border: none; max-height: 1px;")
        root.addWidget(sep)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(0, 0, 0, 0)
        body_l.setSpacing(20)

        for group_name, items in SHORTCUTS:
            group = QFrame()
            gl = QVBoxLayout(group)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setSpacing(6)

            hd = QLabel(group_name.upper())
            hd.setStyleSheet(
                "font-family: 'JetBrains Mono', monospace; font-size: 10px; "
                "font-weight: 500; letter-spacing: 1.8px; color: #5a5e54;"
            )
            gl.addWidget(hd)

            for sc in items:
                row = QFrame()
                row_l = QHBoxLayout(row)
                row_l.setContentsMargins(0, 4, 0, 4)
                row_l.setSpacing(14)

                kbd = QLabel(sc.keys)
                kbd.setStyleSheet(
                    "font-family: 'JetBrains Mono', monospace; font-size: 11px; "
                    "font-weight: 700; color: #f4f5ee; background: #131613; "
                    "border: 1px solid #33382c; padding: 4px 10px; min-width: 64px;"
                )
                kbd.setAlignment(Qt.AlignCenter)
                kbd.setFixedWidth(96)

                action = QLabel(sc.action)
                action.setStyleSheet(
                    "font-family: 'Space Grotesk', sans-serif; font-size: 13px; "
                    "color: #d6d8cf;"
                )

                ctx = QLabel(sc.context)
                ctx.setStyleSheet(
                    "font-family: 'JetBrains Mono', monospace; font-size: 10px; "
                    "color: #898d80; letter-spacing: 1px;"
                )

                row_l.addWidget(kbd)
                row_l.addWidget(action, 1)
                if sc.context:
                    row_l.addWidget(ctx)
                gl.addWidget(row)

            body_l.addWidget(group)

        body_l.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer
        ft = QHBoxLayout()
        hint = QLabel("Press Esc to close")
        hint.setStyleSheet(
            "font-family: 'JetBrains Mono', monospace; font-size: 10px; "
            "color: #5a5e54; letter-spacing: 1px;"
        )
        ft.addWidget(hint)
        ft.addStretch(1)
        close_btn = QPushButton("CLOSE")
        close_btn.setObjectName("GhostButton")
        close_btn.clicked.connect(self.accept)
        ft.addWidget(close_btn)
        root.addLayout(ft)

    def keyPressEvent(self, event):  # type: ignore[override]
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_Question:
            self.accept()
            return
        super().keyPressEvent(event)
