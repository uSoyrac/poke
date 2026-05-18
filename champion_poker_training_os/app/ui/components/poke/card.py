"""PokeCard — bordered surface with optional numbered header.

Anatomy (HANDOFF.md §2.2):

    ┌──────────────────────────────────────────────────┐
    │ A1 · Today's training block       4 SPOTS · 25M │  ← header (14×18)
    ├──────────────────────────────────────────────────┤
    │ body (18px padding)                              │
    │                                                  │
    └──────────────────────────────────────────────────┘

Sharp corners (0 radius), 1-px hairline border, monospace eyebrow number.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout,
                                QWidget)

from app.ui.theme import poke_tokens as t


class PokeCard(QFrame):
    """A bordered card. Use `add_to_body(widget)` to fill the body."""

    def __init__(self,
                 title: Optional[str] = None,
                 *,
                 num: Optional[str] = None,
                 sub: Optional[str] = None,
                 action: Optional[QWidget] = None,
                 tight: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("PokeCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#PokeCard {{ background: {t.SURFACE}; "
            f"border: 1px solid {t.LINE}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────
        if title or num or sub or action:
            hd = QFrame()
            hd.setObjectName("PokeCardHd")
            hd.setStyleSheet(
                f"#PokeCardHd {{ background: transparent; "
                f"border-bottom: 1px solid {t.LINE}; }}"
            )
            row = QHBoxLayout(hd)
            row.setContentsMargins(18, 14, 18, 14)
            row.setSpacing(12)

            if num:
                num_lbl = QLabel(num.upper())
                num_lbl.setStyleSheet(
                    f"color: {t.DIM}; font-family: 'JetBrains Mono'; "
                    f"font-size: 10px; font-weight: 500; "
                    f" background: transparent;"
                )
                row.addWidget(num_lbl)

            if title:
                title_lbl = QLabel(title)
                title_lbl.setStyleSheet(
                    f"color: {t.INK}; font-family: 'Space Grotesk'; "
                    f"font-size: 14px; font-weight: 600; "
                    f"background: transparent;"
                )
                row.addWidget(title_lbl)

            row.addStretch(1)

            if sub:
                sub_lbl = QLabel(sub.upper())
                sub_lbl.setStyleSheet(
                    f"color: {t.MUTED}; font-family: 'JetBrains Mono'; "
                    f"font-size: 10px; font-weight: 500; "
                    f" background: transparent;"
                )
                row.addWidget(sub_lbl)

            if action:
                row.addWidget(action)

            outer.addWidget(hd)

        # ── Body ────────────────────────────────────────────────────
        self._body = QWidget()
        self._body.setObjectName("PokeCardBody")
        self._body.setStyleSheet("#PokeCardBody { background: transparent; }")
        body_pad = 12 if tight else 18
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(body_pad, body_pad, body_pad, body_pad)
        self._body_layout.setSpacing(12)
        outer.addWidget(self._body, 1)

    # ── public API ───────────────────────────────────────────────────

    def add_to_body(self, widget: QWidget) -> None:
        self._body_layout.addWidget(widget)

    def add_layout_to_body(self, layout) -> None:
        self._body_layout.addLayout(layout)

    def body_layout(self):
        return self._body_layout
