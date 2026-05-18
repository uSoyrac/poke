"""PokeSeg — segmented control (radio group as a bar of pills)."""
from __future__ import annotations

from typing import Callable, Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton

from app.ui.theme import poke_tokens as t


class PokeSeg(QFrame):
    """Segmented control. `options` is a list of strings OR (value, label)
    tuples. Emits `changed(value)` when the user clicks a segment."""
    changed = Signal(str)

    def __init__(self,
                 options: Iterable,
                 *,
                 value: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("PokeSeg")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#PokeSeg {{ background: transparent; "
            f"border: 1px solid {t.LINE_2}; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        opts = list(options)
        normalised: list[tuple[str, str]] = []
        for o in opts:
            if isinstance(o, str):
                normalised.append((o, o))
            else:
                normalised.append((o[0], o[1] if len(o) > 1 else o[0]))

        self._value = value if value is not None else (normalised[0][0] if normalised else "")
        self._buttons: dict[str, QPushButton] = {}

        for i, (val, lbl) in enumerate(normalised):
            b = QPushButton(lbl.upper())
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.setMinimumHeight(28)
            b.clicked.connect(lambda _checked=False, v=val: self._on_click(v))
            # Right border between segments (except last)
            right_border = ("border-right: 1px solid " + t.LINE_2 + ";"
                            if i < len(normalised) - 1 else "")
            b.setStyleSheet(
                f"QPushButton {{"
                f"  background: transparent; color: {t.MUTED};"
                f"  font-family: 'JetBrains Mono'; font-weight: 500;"
                f"  font-size: 11px;"
                f"  padding: 6px 14px; border: 0; {right_border}"
                f"}}"
                f"QPushButton:hover {{ background: {t.SURFACE}; color: {t.INK}; }}"
            )
            self._buttons[val] = b
            row.addWidget(b)
        self._refresh()

    def _on_click(self, v: str) -> None:
        if v == self._value:
            return
        self._value = v
        self._refresh()
        self.changed.emit(v)

    def _refresh(self) -> None:
        for val, btn in self._buttons.items():
            active = (val == self._value)
            base = btn.styleSheet().split("QPushButton:hover")[0]
            # Re-build with/without the active rule
            on_rule = (f"QPushButton {{ background: {t.ACCENT}; color: {t.ACCENT_INK}; "
                       f"font-family: 'JetBrains Mono'; font-weight: 500; "
                       f"font-size: 11px; "
                       f"padding: 6px 14px; border: 0; "
                       + ("border-right: 1px solid " + t.ACCENT + ";"
                          if list(self._buttons.values()).index(btn) <
                          len(self._buttons) - 1 else "")
                       + "}")
            if active:
                btn.setStyleSheet(on_rule)
            else:
                # Restore the default rules
                idx = list(self._buttons.values()).index(btn)
                right_border = ("border-right: 1px solid " + t.LINE_2 + ";"
                                if idx < len(self._buttons) - 1 else "")
                btn.setStyleSheet(
                    f"QPushButton {{"
                    f"  background: transparent; color: {t.MUTED};"
                    f"  font-family: 'JetBrains Mono'; font-weight: 500;"
                    f"  font-size: 11px;"
                    f"  padding: 6px 14px; border: 0; {right_border}"
                    f"}}"
                    f"QPushButton:hover {{ background: {t.SURFACE}; color: {t.INK}; }}"
                )

    def value(self) -> str:
        return self._value

    def set_value(self, v: str) -> None:
        if v in self._buttons:
            self._value = v
            self._refresh()
