"""PokeBtn — brutalist editorial button.

Variants: default · primary · danger · ghost
Sizes:    sm · md (default) · lg · block

Matches the `.btn` rules in poke/project/theme.css and section 2.1 of
HANDOFF.md. Sharp corners (0 radius), 1-px line_2 border, Space Grotesk
600 13px label, optional keyboard-hint chip after the label.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton

from app.ui.theme import poke_tokens as t


_VARIANT_QSS = {
    "default": f"""
        QPushButton {{
            background: {t.SURFACE}; color: {t.INK};
            border: 1px solid {t.LINE_2};
        }}
        QPushButton:hover  {{ background: {t.SURFACE_2}; border-color: {t.MUTED}; }}
        QPushButton:pressed{{ background: {t.BG_2}; }}
        QPushButton:disabled {{ color: {t.DIM}; border-color: {t.LINE}; }}
    """,
    "primary": f"""
        QPushButton {{
            background: {t.ACCENT}; color: {t.ACCENT_INK};
            border: 1px solid {t.ACCENT};
        }}
        QPushButton:hover  {{ background: {t.ACCENT_2}; border-color: {t.ACCENT_2}; }}
        QPushButton:pressed{{ background: {t.ACCENT}; }}
        QPushButton:disabled {{ background: {t.SURFACE}; color: {t.DIM}; border-color: {t.LINE_2}; }}
    """,
    "danger": f"""
        QPushButton {{
            background: {t.DANGER}; color: #ffffff;
            border: 1px solid {t.DANGER};
        }}
        QPushButton:hover {{ background: {t.DANGER_2}; border-color: {t.DANGER_2}; }}
    """,
    "ghost": f"""
        QPushButton {{
            background: transparent; color: {t.INK_2};
            border: 1px solid {t.LINE};
        }}
        QPushButton:hover {{ background: {t.SURFACE}; color: {t.INK}; border-color: {t.LINE_2}; }}
    """,
}

_SIZE_QSS = {
    "sm": "padding: 6px 10px; font-size: 12px;",
    "md": "padding: 9px 14px; font-size: 13px;",
    "lg": "padding: 14px 22px; font-size: 14px;",
}


class PokeBtn(QPushButton):
    """Editorial brutalist button.

    Example:
        btn = PokeBtn("Start training", variant="primary", kbd="↵")
        btn.clicked.connect(handler)
    """

    def __init__(self,
                 label: str = "",
                 *,
                 variant: str = "default",
                 size: str = "md",
                 kbd: Optional[str] = None,
                 block: bool = False,
                 parent=None,
                 on_click: Optional[Callable] = None):
        # Append the kbd chip — rendered inside the same button label so
        # the chip stays aligned with the text. ▸ Space Grotesk for the
        # word, ▸ JetBrains Mono for the chip — but QPushButton has one
        # font; we accept that compromise and use mono only via padding.
        display_text = label
        if kbd:
            display_text = f"{label}   {kbd}"
        super().__init__(display_text, parent)
        self._variant = variant
        self._size = size
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFlat(False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._apply_qss()
        # Block buttons expand horizontally.
        if block:
            self.setMinimumWidth(180)
            from PySide6.QtWidgets import QSizePolicy
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Minimum heights per size — keeps clickability on touch screens.
        self.setMinimumHeight({"sm": 28, "md": 34, "lg": 46}.get(size, 34))
        if on_click:
            self.clicked.connect(on_click)

    # ── style helpers ────────────────────────────────────────────────

    def _apply_qss(self) -> None:
        variant_qss = _VARIANT_QSS.get(self._variant, _VARIANT_QSS["default"])
        size_qss = _SIZE_QSS.get(self._size, _SIZE_QSS["md"])
        self.setStyleSheet(
            f"QPushButton {{"
            f"  font-family: 'Space Grotesk'; font-weight: 600;"
            f"  {size_qss}"
            f"}}"
            + variant_qss
        )

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._apply_qss()
