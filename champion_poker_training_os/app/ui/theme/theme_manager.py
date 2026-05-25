from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.core.config import THEME_PATH

# Cached raw QSS (loaded once)
_BASE_QSS: str | None = None


def _base_qss() -> str:
    global _BASE_QSS
    if _BASE_QSS is None:
        _BASE_QSS = THEME_PATH.read_text(encoding="utf-8")
    return _BASE_QSS


def generate_scaled_theme(scale: float) -> str:
    """Return the full app stylesheet with all font-size and padding px values
    multiplied by *scale*.  Clamped to [0.50, 2.40] so nothing becomes
    unreadably tiny or absurdly large.
    """
    scale = max(0.50, min(2.40, scale))
    if abs(scale - 1.0) < 0.015:
        return _base_qss()

    css = _base_qss()

    # ── font-size: Npx ──────────────────────────────────────────────────────
    def _font(m: re.Match) -> str:
        px = max(7, round(int(m.group(1)) * scale))
        return f"font-size: {px}px"

    css = re.sub(r"font-size:\s*(\d+)px", _font, css)

    # ── padding: [N1px N2px N3px N4px] (1–4 values) ─────────────────────────
    # Only the numeric values before "px" inside a padding: … ; block.
    def _pad(m: re.Match) -> str:
        # m.group(0) = whole "padding: X1px X2px …" fragment (up to semicolon)
        # Replace each number-before-px inside it
        def _px(n: re.Match) -> str:
            return str(max(1, round(int(n.group(1)) * scale)))
        return re.sub(r"\b(\d+)(?=px)", _px, m.group(0))

    css = re.sub(r"padding:[^;]+;", _pad, css)

    # ── letter-spacing: Npx ─────────────────────────────────────────────────
    def _ls(m: re.Match) -> str:
        val = round(float(m.group(1)) * scale, 2)
        return f"letter-spacing: {val}px"

    css = re.sub(r"letter-spacing:\s*([\d.]+)px", _ls, css)

    return css


def apply_dark_theme(app: QApplication, path: Path = THEME_PATH) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(_base_qss())
