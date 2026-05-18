"""PokePageHeader — page title with eyebrow number + italic accent.

Layout (theme.css `.page__hd`):

    01 / SECTION
    Plug your leaks.                                    [actions]
    Drill solver-verified spots, get coached…
    ─────────────────────────────────────────────────────────
"""
from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout,
                                QWidget)

from app.ui.theme import poke_tokens as t


# Match an <em>...</em> block — we'll style it Instrument Serif italic.
_EM_RE = re.compile(r"<em>(.+?)</em>", re.IGNORECASE | re.DOTALL)


def _styled_title_html(title: str) -> str:
    """Wrap any <em>…</em> spans with Instrument Serif italic styling."""
    def repl(m):
        return (f"<span style=\"font-family:'Instrument Serif'; "
                f"font-style:italic; font-weight:400; "
                f"\">{m.group(1)}</span>")
    return _EM_RE.sub(repl, title)


class PokePageHeader(QFrame):
    """Page title block. `title` may contain `<em>italic</em>` spans."""

    def __init__(self,
                 num: str,
                 title: str,
                 *,
                 sub: Optional[str] = None,
                 actions: Optional[QWidget] = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("PokePageHeader")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#PokePageHeader {{ background: transparent; "
            f"border-bottom: 1px solid {t.LINE}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 22)
        outer.setSpacing(8)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(20)

        # ── Left column: num / title / sub ───────────────────────────
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)

        if num:
            num_lbl = QLabel(num.upper())
            num_lbl.setStyleSheet(
                f"color: {t.MUTED}; background: transparent; "
                f"font-family: 'JetBrains Mono'; font-size: 11px; "
                f"font-weight: 500;"
            )
            left.addWidget(num_lbl)

        title_lbl = QLabel(_styled_title_html(title))
        title_lbl.setTextFormat(Qt.RichText)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; "
            f"font-size: 44px;"
        )
        left.addWidget(title_lbl)

        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setWordWrap(True)
            sub_lbl.setMaximumWidth(720)  # ~60ch
            sub_lbl.setStyleSheet(
                f"color: {t.MUTED}; background: transparent; "
                f"font-family: 'Space Grotesk'; font-size: 14px; "
                f"margin-top: 8px;"
            )
            left.addWidget(sub_lbl)

        row.addLayout(left, 1)

        # ── Right column: actions ────────────────────────────────────
        if actions:
            act_wrap = QVBoxLayout()
            act_wrap.setAlignment(Qt.AlignBottom | Qt.AlignRight)
            act_wrap.addWidget(actions)
            row.addLayout(act_wrap)

        outer.addLayout(row)
