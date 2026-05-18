"""Bundled Poke font loader.

Loads Space Grotesk, JetBrains Mono and Instrument Serif TTFs from
`app/ui/theme/fonts/` into QFontDatabase at app startup so the Poke
design system works even on machines that don't have these fonts
installed system-wide.

Also exposes helpers to construct QFont objects with the correct
weight + letter-spacing for the Poke type scale.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from app.ui.theme import poke_tokens as t

_FONT_DIR = Path(__file__).parent / "fonts"
_FONT_FILES = [
    "SpaceGrotesk-500.ttf",
    "SpaceGrotesk-700.ttf",
    "JetBrainsMono-500.ttf",
    "JetBrainsMono-700.ttf",
    "InstrumentSerif-400.ttf",
    "InstrumentSerif-400-Italic.ttf",
]

_loaded = False


def load_poke_fonts() -> list[str]:
    """Register all bundled Poke fonts. Idempotent — safe to call
    multiple times.

    Returns the list of family names actually registered (empty if the
    fonts were already loaded or files were missing).
    """
    global _loaded
    if _loaded:
        return []
    families: list[str] = []
    for fname in _FONT_FILES:
        path = _FONT_DIR / fname
        if not path.exists():
            continue
        fid = QFontDatabase.addApplicationFont(str(path))
        if fid >= 0:
            for fam in QFontDatabase.applicationFontFamilies(fid):
                if fam not in families:
                    families.append(fam)
    _loaded = True
    return families


# ─── QFont factories ─────────────────────────────────────────────────


def _qfont(family: str, weight: int, size_px: int,
           italic: bool = False, tracking_em: float = 0.0,
           tabular: bool = False) -> QFont:
    f = QFont(family)
    f.setWeight(QFont.Weight(weight))
    f.setPixelSize(size_px)
    f.setItalic(italic)
    if tracking_em:
        # Qt's setLetterSpacing in PercentageSpacing mode: 100 = normal,
        # 110 = +10%. Convert em-based design value:  em ≈ font size.
        # Use AbsoluteSpacing in px to match CSS letter-spacing closely.
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                           tracking_em * size_px)
    if tabular:
        f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return f


def display(size: int = t.SIZE["h1"], track: float = t.TRACK["tight"]) -> QFont:
    """Space Grotesk 700 — page titles, KPI values, button labels."""
    return _qfont("Space Grotesk", 700, size, tracking_em=track,
                  tabular=True)


def body(size: int = t.SIZE["md"]) -> QFont:
    """Space Grotesk 500 — default body text."""
    return _qfont("Space Grotesk", 500, size,
                  tracking_em=t.TRACK["default"])


def mono(size: int = t.SIZE["sm"], track: float = 0.0,
         tabular: bool = True) -> QFont:
    """JetBrains Mono 500 — data, numbers, code."""
    return _qfont("JetBrains Mono", 500, size,
                  tracking_em=track, tabular=tabular)


def label(size: int = t.SIZE["xs"]) -> QFont:
    """JetBrains Mono 500 uppercase — section labels.

    Caller should still uppercase the text via .upper(). We don't force
    `text-transform` because Qt has no equivalent property.
    """
    return _qfont("JetBrains Mono", 500, size,
                  tracking_em=t.TRACK["label"])


def serif_italic(size: int = t.SIZE["h2"]) -> QFont:
    """Instrument Serif italic — editorial accents inside headlines."""
    return _qfont("Instrument Serif", 400, size, italic=True,
                  tracking_em=-0.02)


def kbd(size: int = 10) -> QFont:
    """JetBrains Mono with kbd tracking — for keyboard hint chips."""
    return _qfont("JetBrains Mono", 500, size, tracking_em=t.TRACK["kbd"])
