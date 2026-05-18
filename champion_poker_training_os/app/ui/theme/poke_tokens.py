"""POKE design system tokens — brutalist editorial.

Single source of truth for the new "Poke" visual language. Mirrors
`theme.css` from the design handoff (poke/project/theme.css). Use these
tokens everywhere; never hardcode hex codes in component code.

Reference: poke/project/HANDOFF.md  · poke/project/theme.css
"""
from __future__ import annotations

from dataclasses import dataclass


# ─── Color tokens (dark default) ─────────────────────────────────────
# Values copied verbatim from theme.css :root.

# Surfaces
BG          = "#0a0c0a"   # App background
BG_2        = "#0f1210"   # Sidebar, raised areas, alt rows
SURFACE     = "#131613"   # Cards, modal panels
SURFACE_2   = "#181b17"   # Hover, table headers

# Lines
LINE        = "#23271f"   # 1-px hairline borders
LINE_2      = "#33382c"   # 1-px strong / interactive borders

# Ink (text)
INK         = "#f4f5ee"   # Primary text
INK_2       = "#d6d8cf"   # Secondary text
MUTED       = "#898d80"   # Tertiary / labels
DIM         = "#5a5e54"   # Quaternary / off labels

# Accent (lime — brand)
# OKLCH(72% 0.18 145) ≈ #5db75b — fallback for Qt (no oklch support)
ACCENT      = "#5db75b"
ACCENT_2    = "#7fd97d"   # hover
ACCENT_INK  = "#0a0c0a"   # text on accent

# Semantic
DANGER      = "#cc3a2b"   # Bet/raise, errors, expensive leaks
DANGER_2    = "#e25a4d"   # Lighter danger / deltas
WARN        = "#d6a23b"   # Caution / medium leaks
INFO        = "#5288d6"   # Fold / neutral info


# ─── Typography ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class Font:
    family: str
    weight: int


F_DISPLAY = Font("Space Grotesk", 700)   # Headings, KPI values, button labels
F_BODY    = Font("Space Grotesk", 500)   # Default body
F_SERIF   = Font("Instrument Serif", 400)  # Italic editorial accents
F_MONO    = Font("JetBrains Mono", 500)  # Numbers, labels, code

SIZE = {
    "xs":  10,   # labels
    "sm":  12,   # caption
    "md":  13,   # body / button
    "lg":  14,   # H3 / section
    "xl":  16,
    "h3":  22,   # modal title
    "h2":  32,
    "h1":  52,   # page title
    "kpi":      40,
    "kpi_lg":   64,
}

# Letter-spacing values in 1000ths of em — Qt uses px in QFont, so we
# pre-compute the px equivalent at every relevant size when constructing
# fonts (see poke_fonts.py helpers).
TRACK = {
    "tight":     -0.045,  # page titles
    "h2":        -0.040,
    "h3":        -0.030,
    "default":   -0.010,
    "label":      0.120,  # uppercase mono labels
    "kbd":        0.140,
}


# ─── Spacing & radii ─────────────────────────────────────────────────

# Radii: 0 EVERYWHERE. Brutalist sharp corners.
RADIUS = 0

# Spacing scale (px) — never use values outside this scale.
SPACE = {
    "0":  4,
    "1":  6,
    "2":  8,
    "3":  12,
    "4":  16,
    "5":  20,
    "6":  24,
    "7":  32,
    "8":  48,
    "9":  64,
}


# ─── Layout primitives ───────────────────────────────────────────────

SIDEBAR_W   = 232
TOPBAR_H    = 56
STATUSBAR_H = 28
PAGE_PAD    = 28
PAGE_MAXW   = 1480


# ─── Convenience tuples ──────────────────────────────────────────────

ALL_COLORS: dict[str, str] = {
    "bg": BG, "bg_2": BG_2, "surface": SURFACE, "surface_2": SURFACE_2,
    "line": LINE, "line_2": LINE_2,
    "ink": INK, "ink_2": INK_2, "muted": MUTED, "dim": DIM,
    "accent": ACCENT, "accent_2": ACCENT_2, "accent_ink": ACCENT_INK,
    "danger": DANGER, "danger_2": DANGER_2, "warn": WARN, "info": INFO,
}
