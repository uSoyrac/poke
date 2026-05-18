"""PokeTag — small uppercase pill.

Pattern: 10px JetBrains Mono uppercase, 3×7 padding, 1px line_2 border.
Tones: g (accent) · r (danger) · y (warn) · b (info) · neutral.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.ui.theme import poke_tokens as t


def _tone_colors(tone: str) -> tuple[str, str, str]:
    """Return (fg, border, bg) for a tone."""
    if tone == "g":
        return t.ACCENT,   "#5db75b4D", "#5db75b14"
    if tone == "r":
        return t.DANGER_2, "#cc3a2b4D", "#cc3a2b14"
    if tone == "y":
        return t.WARN,     "#d6a23b4D", "#d6a23b14"
    if tone == "b":
        return t.INFO,     "#5288d64D", "#5288d614"
    return t.INK_2, t.LINE_2, t.SURFACE_2


class PokeTag(QLabel):
    """A small uppercase tag/pill — optionally prefixed with a dot."""

    def __init__(self,
                 text: str,
                 *,
                 tone: str = "neutral",
                 dot: bool = False,
                 parent=None):
        display = (f"●  {text.upper()}" if dot else text.upper())
        super().__init__(display, parent)
        fg, border, bg = _tone_colors(tone)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QLabel {{"
            f"  color: {fg}; background: {bg};"
            f"  border: 1px solid {border};"
            f"  font-family: 'JetBrains Mono'; font-weight: 500;"
            f"  font-size: 10px;"
            f"  padding: 3px 7px;"
            f"}}"
        )
        # Don't stretch — tags should hug content.
        self.setSizePolicy(self.sizePolicy().horizontalPolicy().Maximum,
                           self.sizePolicy().verticalPolicy().Maximum)
