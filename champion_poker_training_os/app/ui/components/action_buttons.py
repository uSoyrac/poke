"""Unified action button row — same look & feel across the whole app.

Used by Spot Trainer, GTO Trainer, Tournament Play/Simulator, ICM, etc.
so every "fold / call / raise / jam" decision UI matches.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton, QSizePolicy


# Colour palette (matches Spot Trainer's existing scheme)
def action_palette(action: str) -> tuple[str, str, str]:
    """Return (background, border, foreground) for an action."""
    a = action.lower()
    if "fold" in a:
        return ("#1B2D4A", "#3B82F6", "#93C5FD")
    if a in ("check", "call") or "check" in a or "call" in a:
        return ("#0E2A1E", "#10B981", "#6EE7B7")
    if "jam" in a or "all" in a:
        return ("#1A0E0E", "#7F1D1D", "#FCA5A5")
    if "raise" in a or "3bet" in a or "4bet" in a or a == "bet" or "bet " in a:
        return ("#2A1B1B", "#E11D48", "#FCA5A5")
    return ("#131A24", "#1E2733", "#E5E7EB")


def action_display(action: str, pot_bb: float = 10.0, stack_bb: float = 100.0) -> str:
    """Human-readable label: FOLD / CALL / RAISE 2.3bb etc."""
    a = action.lower()
    if a == "fold":   return "FOLD"
    if a == "check":  return "CHECK"
    if a == "call":   return "CALL"
    if "small" in a:  return f"BET {pot_bb * 0.33:.1f}bb"
    if "medium" in a: return f"BET {pot_bb * 0.66:.1f}bb"
    if "large" in a:  return f"BET {pot_bb * 1.10:.1f}bb"
    if "jam" in a or "all" in a: return f"ALL-IN {stack_bb:.0f}bb"
    if "raise" in a:  return f"RAISE {pot_bb * 2.4:.1f}bb"
    if "3bet" in a:   return f"3-BET {pot_bb * 3.0:.1f}bb"
    if "4bet" in a:   return f"4-BET {pot_bb * 4.0:.1f}bb"
    if a == "bet":    return "BET"
    return action.upper()


class GtoActionButton(QPushButton):
    """Big, colour-coded action button. Optionally shows a GTO % bar after answer."""

    def __init__(self, label: str, action: str, parent=None):
        super().__init__(label, parent)
        self._action = action
        self._freq: Optional[float] = None
        bg, border, fg = action_palette(action)
        self._bg, self._border, self._fg = bg, border, fg
        self.setMinimumHeight(64)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._apply_style(False)

    @property
    def action_id(self) -> str:
        return self._action

    def set_frequency(self, freq: float) -> None:
        """Display GTO % under the action name."""
        self._freq = freq
        self._apply_style(True)
        pct = f"{freq * 100:.1f}%"
        first_line = self.text().split("\n")[0]
        self.setText(f"{first_line}\n{pct}")
        self.update()

    def reset_frequency(self) -> None:
        self._freq = None
        first_line = self.text().split("\n")[0]
        self.setText(first_line)
        self._apply_style(False)
        self.update()

    # ── styling ──────────────────────────────────────────────────────
    def _apply_style(self, answered: bool) -> None:
        focus_border = "#22D3EE" if answered else self._border
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._bg};
                border: 2px solid {self._border};
                border-radius: 10px;
                color: {self._fg};
                font-size: 15px;
                font-weight: 800;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                border-color: {focus_border};
                background: {self._bg}dd;
            }}
            QPushButton:disabled {{
                color: #555;
                border-color: #2A3441;
                background: #0F141C;
            }}
        """)

    # ── paint freq bar ───────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._freq is not None and self._freq > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            r = self.rect()
            bar_w = max(4, int((r.width() - 16) * self._freq))
            bar_h = 4
            bar_y = r.height() - 8
            painter.setPen(Qt.NoPen)
            col = QColor(self._border)
            col.setAlphaF(0.85)
            painter.setBrush(col)
            painter.drawRoundedRect(8, bar_y, bar_w, bar_h, 2, 2)
            painter.end()


def build_action_row(
    actions: list[str],
    on_click: Callable[[str], None],
    pot_bb: float = 10.0,
    stack_bb: float = 100.0,
) -> list[GtoActionButton]:
    """Convenience: build a list of GtoActionButtons wired to on_click.

    Returns the button list — caller adds them to whatever QLayout they have.
    """
    buttons: list[GtoActionButton] = []
    for action in actions:
        label = action_display(action, pot_bb, stack_bb)
        btn = GtoActionButton(label, action)
        btn.clicked.connect(lambda _, a=action: on_click(a))
        buttons.append(btn)
    return buttons
