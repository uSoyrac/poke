"""POKE Style Guide screen — live in-app reference of every primitive.

Mirrors `poke/project/Style Guide.html` in PySide6. Lives at its own
sidebar slot so designers + devs can scroll the system end-to-end.

Sections:
  01  Color
  02  Type · 3 families
  03  Spacing & Borders
  04  Buttons
  05  Tags
  06  Stats / KPI
  07  Controls
  08  Cards
  09  Layout & Keyboard hints
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                                QLineEdit, QScrollArea, QSlider, QVBoxLayout,
                                QWidget)

from app.ui.components.poke import (PokeBtn, PokeCard, PokePageHeader,
                                     PokeSeg, PokeStat, PokeTag)
from app.ui.theme import poke_tokens as t


# ─── helpers ─────────────────────────────────────────────────────────


def _label(text: str, *, kind: str = "label") -> QLabel:
    """Build a styled label. kind ∈ {label, body, mono, muted}."""
    lbl = QLabel(text)
    if kind == "label":
        lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 10px; "
            f"font-weight: 500;"
        )
        lbl.setText(text.upper())
    elif kind == "mono":
        lbl.setStyleSheet(
            f"color: {t.INK_2}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px;"
        )
    elif kind == "muted":
        lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
    else:
        lbl.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
    return lbl


def _section_header(num: str, title: str, sub: str) -> QFrame:
    """Section header — number · title · subline.

    Mirrors `.sec__hd` from the Style Guide HTML.
    """
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background: transparent; "
        f"border-bottom: 1px solid {t.LINE}; }}"
    )
    grid = QGridLayout(f)
    grid.setContentsMargins(0, 0, 0, 18)
    grid.setHorizontalSpacing(20)

    num_lbl = QLabel(num.upper())
    num_lbl.setStyleSheet(
        f"color: {t.ACCENT}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 12px; "
        f"font-weight: 600;"
    )
    num_lbl.setFixedWidth(70)
    grid.addWidget(num_lbl, 0, 0, Qt.AlignBaseline)

    title_lbl = QLabel(title)
    title_lbl.setTextFormat(Qt.RichText)
    title_lbl.setStyleSheet(
        f"color: {t.INK}; background: transparent; "
        f"font-family: 'Space Grotesk'; font-weight: 700; "
        f"font-size: 28px;"
    )
    grid.addWidget(title_lbl, 0, 1, Qt.AlignBaseline)

    sub_lbl = QLabel(("— " + sub).upper())
    sub_lbl.setStyleSheet(
        f"color: {t.MUTED}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 11px; "
        f""
    )
    grid.addWidget(sub_lbl, 0, 2, Qt.AlignBaseline | Qt.AlignRight)

    grid.setColumnStretch(1, 1)
    return f


# ─── color swatch row ────────────────────────────────────────────────


def _swatch_row(token: str, hexv: str, name: str, use: str) -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"QFrame {{ background: transparent; "
        f"border-bottom: 1px solid {t.LINE}; }}"
    )
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)

    chip = QFrame()
    chip.setFixedSize(80, 56)
    chip.setStyleSheet(
        f"QFrame {{ background: {hexv}; "
        f"border-right: 1px solid {t.LINE}; }}"
    )
    h.addWidget(chip)

    name_w = QFrame()
    name_w.setStyleSheet(f"QFrame {{ background: transparent; border-right: 1px solid {t.LINE}; }}")
    nv = QVBoxLayout(name_w)
    nv.setContentsMargins(18, 14, 18, 14)
    nv.setSpacing(2)
    n_lbl = QLabel(name)
    n_lbl.setStyleSheet(
        f"color: {t.INK}; background: transparent; "
        f"font-family: 'Space Grotesk'; font-size: 14px; font-weight: 600;"
    )
    u_lbl = QLabel(use)
    u_lbl.setStyleSheet(
        f"color: {t.MUTED}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 10px;"
    )
    nv.addWidget(n_lbl)
    nv.addWidget(u_lbl)
    h.addWidget(name_w, 1)

    tok_lbl = QLabel(token)
    tok_lbl.setFixedWidth(150)
    tok_lbl.setStyleSheet(
        f"color: {t.INK_2}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 11px; "
        f"padding: 14px 16px; border-right: 1px solid {t.LINE};"
    )
    h.addWidget(tok_lbl)

    hex_lbl = QLabel(hexv)
    hex_lbl.setFixedWidth(100)
    hex_lbl.setStyleSheet(
        f"color: {t.MUTED}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 11px; padding: 14px 16px;"
    )
    h.addWidget(hex_lbl)
    return row


_COLORS = [
    ("--bg",         t.BG,        "Background",     "App background"),
    ("--bg-2",       t.BG_2,      "Background alt", "Sidebar, raised"),
    ("--surface",    t.SURFACE,   "Surface",        "Cards, modals"),
    ("--surface-2",  t.SURFACE_2, "Surface alt",    "Hover, headers"),
    ("--line",       t.LINE,      "Line",           "1px hairlines"),
    ("--line-2",     t.LINE_2,    "Line strong",    "Strong borders"),
    ("--ink",        t.INK,       "Ink",            "Primary text"),
    ("--ink-2",      t.INK_2,     "Ink secondary",  "Secondary text"),
    ("--muted",      t.MUTED,     "Muted",          "Labels, tertiary"),
    ("--dim",        t.DIM,       "Dim",            "Off-state"),
    ("--accent",     t.ACCENT,    "Accent",         "Brand · CTA"),
    ("--danger",     t.DANGER,    "Danger",         "Raise · error"),
    ("--warn",       t.WARN,      "Warn",           "Caution"),
    ("--info",       t.INFO,      "Info",           "Fold · neutral"),
]


def _type_row(name: str, sample: str, family: str, size: int,
              spec: str, italic: bool = False) -> QFrame:
    row = QFrame()
    row.setStyleSheet(
        f"QFrame {{ background: transparent; "
        f"border-bottom: 1px solid {t.LINE}; }}"
    )
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 16, 0, 16)
    h.setSpacing(24)

    meta = QLabel(name.upper())
    meta.setFixedWidth(140)
    meta.setStyleSheet(
        f"color: {t.MUTED}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 10px;"
    )
    h.addWidget(meta, 0, Qt.AlignVCenter)

    sample_lbl = QLabel(sample)
    # Family arrives as e.g. "Space Grotesk 700" — split off the weight.
    parts = family.rsplit(" ", 1)
    fam = parts[0]
    weight = parts[1] if len(parts) > 1 and parts[1].isdigit() else "500"
    italic_css = "italic" if italic else "normal"
    sample_lbl.setStyleSheet(
        f"color: {t.INK}; background: transparent; "
        f"font-family: '{fam}'; font-weight: {weight}; "
        f"font-style: {italic_css}; font-size: {size}px;"
    )
    h.addWidget(sample_lbl, 1)

    spec_lbl = QLabel(f"{family} · {size}px\n{spec}")
    spec_lbl.setFixedWidth(220)
    spec_lbl.setStyleSheet(
        f"color: {t.INK_2}; background: transparent; "
        f"font-family: 'JetBrains Mono'; font-size: 11px;"
    )
    spec_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    h.addWidget(spec_lbl, 0, Qt.AlignVCenter)

    return row


_TYPE_SCALE = [
    ("H1 / Page title", "Plug your leaks.",          "Space Grotesk 700",  52,  "-0.045em · 0.96 LH", False),
    ("H2 / Modal title","Trainer Scenario",          "Space Grotesk 700",  22,  "-0.03em",            False),
    ("H3 / Section",    "Today's training block",    "Space Grotesk 600",  14,  "-0.01em",            False),
    ("Body",            "Drill solver-verified spots, get coached.",
                                                     "Space Grotesk 500",  14,  "1.4 LH",             False),
    ("Caption",         "EV-loss trending down (-0.05 bb/hand).",
                                                     "Space Grotesk 500",  12,  "muted",              False),
    ("Label",           "WINRATE · BB/100",          "JetBrains Mono 500", 10,  "0.12em · uppercase", False),
    ("KPI Value",       "7.2",                       "Space Grotesk 700",  40,  "tabular-nums",       False),
    ("KPI Value Lg",    "2.50",                      "Space Grotesk 700",  64,  "-0.05em · tabular",  False),
    ("Editorial italic","— Sharpen your edge.",      "Instrument Serif 400",36, "-0.02em",            True),
    ("Mono / data",     "1422 · −0.84 · 38%",         "JetBrains Mono 500", 13,  "tabular-nums",       False),
]


# ─── spacing demo ────────────────────────────────────────────────────


def _spacing_section() -> QWidget:
    """A bar of vertical strips showing the spacing scale."""
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(14)

    v.addWidget(_label("SPACING SCALE · PX"))
    row_w = QWidget()
    row = QHBoxLayout(row_w)
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(14)
    row.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
    for px in (4, 6, 8, 12, 16, 20, 24, 32, 48, 64):
        col = QVBoxLayout()
        col.setAlignment(Qt.AlignBottom | Qt.AlignCenter)
        col.setSpacing(8)
        bar = QFrame()
        bar.setFixedSize(24, int(px * 1.5))
        bar.setStyleSheet(f"QFrame {{ background: {t.ACCENT}; }}")
        col.addWidget(bar, 0, Qt.AlignCenter)
        lbl = QLabel(str(px))
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 10px;"
        )
        col.addWidget(lbl)
        wrap_col = QWidget()
        wrap_col.setLayout(col)
        row.addWidget(wrap_col)
    row.addStretch(1)
    v.addWidget(row_w)

    # Border strength examples
    v.addWidget(_label("BORDERS"))
    b_row = QHBoxLayout()
    b_row.setSpacing(14)
    for caption, css, color in [
        ("1PX · LINE",   f"border: 1px solid {t.LINE};",   t.MUTED),
        ("1PX · STRONG", f"border: 1px solid {t.LINE_2};", t.MUTED),
        ("2PX · ACCENT", f"border: 2px solid {t.ACCENT};", t.ACCENT),
    ]:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: {t.SURFACE}; {css} }}"
        )
        fv = QVBoxLayout(f)
        fv.setContentsMargins(20, 18, 20, 18)
        fv.setSpacing(6)
        t1 = QLabel(caption)
        t1.setStyleSheet(
            f"color: {color}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 10px; "
            f"font-weight: 600;"
        )
        t2 = QLabel("Brutalist · sharp")
        t2.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px;"
        )
        fv.addWidget(t1)
        fv.addWidget(t2)
        b_row.addWidget(f, 1)
    v.addLayout(b_row)
    return wrap


# ─── main screen ─────────────────────────────────────────────────────


class PokeStyleGuideScreen(QWidget):
    """Scrolling style guide — live reference for every Poke primitive."""

    def __init__(self, state=None, parent=None):
        super().__init__(parent)
        self.state = state
        self.setObjectName("PokeStyleGuide")
        self.setStyleSheet(
            f"#PokeStyleGuide {{ background: {t.BG}; }}"
        )

        # Outer scroll
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {t.BG}; border: 0; }}"
            f"QScrollBar:vertical {{ width: 10px; background: transparent; }}"
            f"QScrollBar::handle:vertical {{ background: {t.LINE}; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll, 1)

        body = QWidget()
        body.setStyleSheet(f"QWidget {{ background: {t.BG}; }}")
        scroll.setWidget(body)

        v = QVBoxLayout(body)
        v.setContentsMargins(40, 48, 40, 80)
        v.setSpacing(40)

        # ── Hero ─────────────────────────────────────────────────────
        v.addWidget(self._build_hero())

        # ── 01 · Color ───────────────────────────────────────────────
        v.addWidget(_section_header("01", "Color", f"{len(_COLORS)} tokens"))
        for tok, hexv, name, use in _COLORS:
            v.addWidget(_swatch_row(tok, hexv, name, use))

        # ── 02 · Type ────────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header(
            "02", "<span>Type</span> · 3 families",
            "space grotesk · jetbrains mono · instrument serif"))
        for name, sample, family, size, spec, italic in _TYPE_SCALE:
            v.addWidget(_type_row(name, sample, family, size, spec, italic))

        # ── 03 · Spacing & Borders ───────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("03", "Spacing & Borders",
                                     "0 radius · 1px borders · 10-step scale"))
        v.addWidget(_spacing_section())

        # ── 04 · Buttons ─────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("04", "Buttons", "4 variants × 3 sizes"))
        v.addLayout(self._buttons_demo())

        # ── 05 · Tags ────────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("05", "Tags", "5 tones · with/without dot"))
        v.addLayout(self._tags_demo())

        # ── 06 · Stats ───────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("06", "Stats / KPI", "primary metric pattern"))
        v.addLayout(self._stats_demo())

        # ── 07 · Controls ────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("07", "Controls",
                                     "seg · slider · input"))
        v.addLayout(self._controls_demo())

        # ── 08 · Cards ───────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("08", "Cards", "anatomy"))
        v.addLayout(self._cards_demo())

        # ── 09 · Keyboard ────────────────────────────────────────────
        v.addSpacing(12)
        v.addWidget(_section_header("09", "Keyboard",
                                     "every action without your mouse"))
        v.addLayout(self._keyboard_demo())

        v.addStretch(1)

    # ── hero ─────────────────────────────────────────────────────────

    def _build_hero(self) -> QFrame:
        f = QFrame()
        f.setStyleSheet(
            f"QFrame {{ background: transparent; "
            f"border-bottom: 1px solid {t.LINE}; }}"
        )
        v = QVBoxLayout(f)
        v.setContentsMargins(0, 16, 0, 40)
        v.setSpacing(14)

        eyebrow = QLabel("POKE / DESIGN SYSTEM · MAY 2026 · v0.9")
        eyebrow.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f""
        )
        v.addWidget(eyebrow)

        # Title (with italic <em> styling via rich text)
        title = QLabel(
            "A "
            "<span style=\"font-family:'Instrument Serif'; font-style:italic; "
            "font-weight:400;\">brutalist editorial</span><br/>"
            "poker training OS."
        )
        title.setTextFormat(Qt.RichText)
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; "
            f"font-size: 64px;"
        )
        v.addWidget(title)

        lede = QLabel(
            "One language for every screen. Sharp corners, heavy display type, "
            "tabular monospace numbers. Built for low cognitive load — every "
            "screen has one primary action, every spot has a number, every leak "
            "has a verdict."
        )
        lede.setWordWrap(True)
        lede.setMaximumWidth(720)
        lede.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 17px;"
        )
        v.addWidget(lede)

        # Meta cells
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        meta_row.setContentsMargins(0, 12, 0, 0)
        for k, val in [
            ("TYPE",   "Space Grotesk · JetBrains Mono · Instrument Serif"),
            ("ACCENT", "OKLCH(72% 0.18 145) · LIME"),
            ("RADIUS", "0px (sharp corners)"),
            ("STACK",  "PySide6 · Qt 6"),
            ("TARGET", "Desktop · 1280×800 minimum"),
        ]:
            cell = QFrame()
            cell.setStyleSheet(
                f"QFrame {{ background: {t.BG_2}; "
                f"border: 1px solid {t.LINE_2}; }}"
            )
            ch = QHBoxLayout(cell)
            ch.setContentsMargins(14, 10, 14, 10)
            ch.setSpacing(8)
            k_lbl = QLabel(k)
            k_lbl.setStyleSheet(
                f"color: {t.MUTED}; background: transparent; "
                f"font-family: 'JetBrains Mono'; font-size: 11px;"
            )
            v_lbl = QLabel(val)
            v_lbl.setStyleSheet(
                f"color: {t.INK_2}; background: transparent; "
                f"font-family: 'JetBrains Mono'; font-size: 11px;"
            )
            ch.addWidget(k_lbl)
            ch.addWidget(v_lbl)
            meta_row.addWidget(cell)
        meta_row.addStretch(1)
        v.addLayout(meta_row)
        return f

    # ── demos ────────────────────────────────────────────────────────

    def _buttons_demo(self):
        v = QVBoxLayout()
        v.setSpacing(16)

        v.addWidget(_label("VARIANTS"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(PokeBtn("Start training", variant="primary", kbd="↵"))
        row.addWidget(PokeBtn("Import HH"))
        row.addWidget(PokeBtn("Filter", variant="ghost"))
        row.addWidget(PokeBtn("Reset",  variant="danger"))
        row.addStretch(1)
        wrap = QWidget(); wrap.setLayout(row); v.addWidget(wrap)

        v.addWidget(_label("SIZES"))
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row2.addWidget(PokeBtn("Small", size="sm"))
        row2.addWidget(PokeBtn("Default"))
        row2.addWidget(PokeBtn("Large", size="lg", variant="primary"))
        row2.addStretch(1)
        wrap2 = QWidget(); wrap2.setLayout(row2); v.addWidget(wrap2)

        v.addWidget(_label("DISABLED"))
        b = PokeBtn("Disabled")
        b.setEnabled(False)
        v.addWidget(b, 0, Qt.AlignLeft)
        return v

    def _tags_demo(self):
        v = QVBoxLayout()
        v.setSpacing(14)
        v.addWidget(_label("TONES · WITH DOT"))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setAlignment(Qt.AlignLeft)
        for tone, txt in [("neutral","NEUTRAL"), ("g","ACTIVE"),
                          ("r","CRITICAL"), ("y","MEDIUM"), ("b","FOLD")]:
            row.addWidget(PokeTag(txt, tone=tone, dot=True))
        row.addStretch(1)
        w = QWidget(); w.setLayout(row); v.addWidget(w)

        v.addWidget(_label("TONES · WITHOUT DOT"))
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.setAlignment(Qt.AlignLeft)
        for tone, txt in [("neutral","3B"), ("g","CLEAN"),
                          ("r","LEARN"), ("y","PRO"), ("b","PREFLOP")]:
            row2.addWidget(PokeTag(txt, tone=tone))
        row2.addStretch(1)
        w2 = QWidget(); w2.setLayout(row2); v.addWidget(w2)
        return v

    def _stats_demo(self):
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        stats = [
            PokeStat("Winrate", "7.2",  unit="bb/100", delta="1.4", delta_sign="+", sub="vs last 7d"),
            PokeStat("EV-loss", "0.17", unit="bb/h",   delta="0.05", delta_sign="−", sub="trending down"),
            PokeStat("Streak",  "14",   unit="d",      delta="1",    delta_sign="+", sub="best yet"),
            PokeStat("Verdict", "JAM",  mono=True,                    sub="solver agrees"),
        ]
        for i, s in enumerate(stats):
            grid.addWidget(s, 0, i)
        return grid

    def _controls_demo(self):
        v = QVBoxLayout()
        v.setSpacing(16)

        v.addWidget(_label("SEG · SEGMENTED CONTROL"))
        seg_row = QHBoxLayout()
        seg_row.setSpacing(14)
        seg_row.setAlignment(Qt.AlignLeft)
        seg_row.addWidget(PokeSeg(["7d", "30d", "All"], value="30d"))
        seg_row.addWidget(PokeSeg(
            [("r","RAISE"), ("c","CALL"), ("f","FOLD")], value="r"))
        seg_row.addStretch(1)
        w1 = QWidget(); w1.setLayout(seg_row); v.addWidget(w1)

        v.addWidget(_label("SLIDER / RANGE"))
        sr = QHBoxLayout()
        sr.setSpacing(14)
        sr.setAlignment(Qt.AlignLeft)
        sr.addWidget(QLabel("SIZE"))
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 100); s.setValue(65)
        s.setFixedWidth(320)
        s.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: {t.LINE_2}; height: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {t.ACCENT}; }}"
            f"QSlider::handle:horizontal {{ background: {t.ACCENT}; "
            f"width: 12px; margin: -7px 0; border: 0; }}"
        )
        sr.addWidget(s)
        readout = QLabel("15.0 bb")
        readout.setStyleSheet(
            f"color: {t.INK}; background: {t.BG}; "
            f"border: 1px solid {t.LINE_2}; padding: 6px 12px; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; min-width: 80px;"
        )
        sr.addWidget(readout)
        sr.addStretch(1)
        w2 = QWidget(); w2.setLayout(sr); v.addWidget(w2)

        v.addWidget(_label("INPUT"))
        inp = QLineEdit()
        inp.setPlaceholderText("Search hands, ranges, concepts…")
        inp.setFixedWidth(420)
        inp.setStyleSheet(
            f"QLineEdit {{ background: {t.BG}; color: {t.INK}; "
            f"border: 1px solid {t.LINE_2}; padding: 9px 12px; "
            f"font-family: 'JetBrains Mono'; font-size: 13px; }}"
            f"QLineEdit:focus {{ border-color: {t.ACCENT}; }}"
        )
        v.addWidget(inp, 0, Qt.AlignLeft)
        return v

    def _cards_demo(self):
        h = QHBoxLayout()
        h.setSpacing(14)
        c1 = PokeCard("Today's training block",
                       num="A1",
                       sub="4 SPOTS · ~25 MIN",
                       action=PokeBtn("Re-roll", variant="ghost", size="sm"))
        b = _label("WITH HEADER · NUMBERED")
        c1.add_to_body(b)
        body_lbl = QLabel(
            "Card header pattern: num · title · sub · action.\n"
            "Header has 14×18 padding and a hairline bottom border. "
            "Body has 18px padding by default."
        )
        body_lbl.setWordWrap(True)
        body_lbl.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
        c1.add_to_body(body_lbl)
        h.addWidget(c1, 1)

        c2 = PokeCard("No number")
        c2.add_to_body(_label("SIMPLE"))
        body_lbl2 = QLabel(
            "Cards without a number prefix are also valid — typical for less "
            "structured screens like Coach or Welcome."
        )
        body_lbl2.setWordWrap(True)
        body_lbl2.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 13px;"
        )
        c2.add_to_body(body_lbl2)
        h.addWidget(c2, 1)
        return h

    def _keyboard_demo(self):
        groups = [
            ("NAV", [("Dashboard","1"),("Live Table","2"),("Trainer","3"),
                     ("Tournament","4"),("Studio","5"),("Leaks","6")]),
            ("LIVE TABLE", [("Fold","F"),("Call","C"),("Raise","R"),
                            ("All-in","A"),("Next hand","SPACE")]),
            ("GLOBAL", [("Coach","?"),("Settings",","),("Welcome","W"),
                        ("Close modal","ESC")]),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        for col, (title, items) in enumerate(groups):
            wrap = QVBoxLayout()
            wrap.setSpacing(6)
            wrap.addWidget(_label(title))
            for lbl, k in items:
                row = QFrame()
                row.setStyleSheet(
                    f"QFrame {{ background: {t.BG_2}; "
                    f"border: 1px solid {t.LINE}; }}"
                )
                rh = QHBoxLayout(row)
                rh.setContentsMargins(12, 8, 12, 8)
                ll = QLabel(lbl)
                ll.setStyleSheet(
                    f"color: {t.INK_2}; background: transparent; "
                    f"font-family: 'Space Grotesk'; font-size: 13px;"
                )
                rh.addWidget(ll)
                rh.addStretch(1)
                kk = QLabel(k)
                kk.setStyleSheet(
                    f"color: {t.ACCENT}; background: {t.BG}; "
                    f"border: 1px solid {t.LINE_2}; "
                    f"padding: 2px 7px; "
                    f"font-family: 'JetBrains Mono'; font-size: 11px;"
                )
                rh.addWidget(kk)
                wrap.addWidget(row)
            wrap.addStretch(1)
            w = QWidget(); w.setLayout(wrap)
            grid.addWidget(w, 0, col)
        return grid
