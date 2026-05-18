"""PokeStat — primary KPI cell.

Pattern from `.stat` in theme.css (HANDOFF.md §2.3):

    WINRATE                              ▲
    7.2 bb/100
    +1.4 vs last 7d
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.ui.theme import poke_tokens as t


class PokeStat(QFrame):
    """A single KPI cell — label + big value + delta/sub."""

    def __init__(self,
                 label: str,
                 value: str,
                 *,
                 unit: Optional[str] = None,
                 delta: Optional[str] = None,
                 delta_sign: str = "+",
                 sub: Optional[str] = None,
                 mono: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("PokeStat")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#PokeStat {{ background: {t.SURFACE}; "
            f"border: 1px solid {t.LINE}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(10)

        # ── Label row ────────────────────────────────────────────────
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 10px; "
            f"font-weight: 500;"
        )
        outer.addWidget(lbl)

        # ── Value row (big number) ───────────────────────────────────
        val_row = QHBoxLayout()
        val_row.setSpacing(4)
        val_row.setAlignment(Qt.AlignLeft | Qt.AlignBottom)

        val_lbl = QLabel(value)
        if mono:
            val_lbl.setStyleSheet(
                f"color: {t.INK}; background: transparent; "
                f"font-family: 'JetBrains Mono'; font-weight: 500; "
                f"font-size: 40px;"
            )
        else:
            val_lbl.setStyleSheet(
                f"color: {t.INK}; background: transparent; "
                f"font-family: 'Space Grotesk'; font-weight: 700; "
                f"font-size: 40px;"
            )
        val_row.addWidget(val_lbl)

        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet(
                f"color: {t.MUTED}; background: transparent; "
                f"font-family: 'Space Grotesk'; font-size: 16px; "
                f"font-weight: 500; margin-bottom: 4px;"
            )
            val_row.addWidget(unit_lbl)

        val_row.addStretch(1)
        outer.addLayout(val_row)

        # ── Sub row (delta + caption) ────────────────────────────────
        if delta or sub:
            sub_row = QHBoxLayout()
            sub_row.setSpacing(6)
            sub_row.setAlignment(Qt.AlignLeft)

            if delta:
                arrow = "▲" if delta_sign in ("+", "▲") else "▼"
                color = t.ACCENT if delta_sign in ("+", "▲") else t.DANGER_2
                d_lbl = QLabel(f"{arrow} {delta_sign}{delta}")
                d_lbl.setStyleSheet(
                    f"color: {color}; background: transparent; "
                    f"font-family: 'JetBrains Mono'; font-size: 10px; "
                    f"font-weight: 600;"
                )
                sub_row.addWidget(d_lbl)

            if sub:
                s_lbl = QLabel(sub)
                s_lbl.setStyleSheet(
                    f"color: {t.MUTED}; background: transparent; "
                    f"font-family: 'JetBrains Mono'; font-size: 10px; "
                    f""
                )
                sub_row.addWidget(s_lbl)

            sub_row.addStretch(1)
            outer.addLayout(sub_row)
