"""Skills Report — APT-style skill audit using RangeBar widgets.

Each section asks one diagnostic question and shows the user's value vs the
recommended range, broken down by tournament stage (Early / Middle / Bubble / ITM).

Powered by aggregated stats from `get_session_history()` / `get_imported_hands()`
when available; falls back to demo values so the screen is always populated.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.ui.components.range_bar import RangeBar


# Poke-aligned constants (legacy _C_* names preserved for diff sanity)
from app.ui.theme import poke_tokens as _t
_C_BG     = _t.BG
_C_CARD   = _t.SURFACE
_C_PANEL  = _t.SURFACE
_C_BORDER = _t.LINE
_C_MUTED  = _t.MUTED
_C_TEXT   = _t.INK
_C_CYAN   = _t.ACCENT
_C_GREEN  = _t.ACCENT
_C_RED    = _t.DANGER
_C_BLUE   = _t.INFO
_C_AMBER  = _t.WARN
_C_PURPLE = _t.INFO
# Soft-amber header pill (was lost in the Poke sweep — restore as WARN)
_C_HEADER = _t.WARN


# (question, description, list of (stage_label, value, low, high))
# value=None → "No Data"
SKILL_QUESTIONS: list[dict] = [
    {
        "q": "How often did you see the flop?",
        "desc": ("In poker, discretion is the better part of valor. Paying to go to the flop "
                 "too often may indicate you are playing inferior hands. This value measures "
                 "how often you went to the flop, not counting times from the big blind "
                 "without committing additional chips."),
        "stages": [
            ("Early Stage",    48, 19, 33),
            ("Middle Stage",   None, 17, 31),
            ("Bubble Stage",   None, 0.2, 0.3),
            ("In-The-Money",   None, 0.2, 0.3),
        ],
    },
    {
        "q": "When you went to the flop, how often did you raise pre-flop?",
        "desc": ("When you have a strong hand, you should avoid letting players with inferior "
                 "hands see the flop cheaply. This value shows how often you were the pre-flop "
                 "raiser (out of all the times you saw the flop)."),
        "stages": [
            ("Early Stage",    70, 55, None),
            ("Middle Stage",   None, 56, None),
        ],
    },
    {
        "q": "Were you aggressive enough against a pre-flop raise?",
        "desc": ("This measures how often you 3-bet, out of all the times you defended against "
                 "a pre-flop raise (by either calling or 3-betting). The recommendation here is "
                 "the bare minimum; more aggressive 3-betting is preferable."),
        "stages": [
            ("Overall",        50, 35, None),
        ],
    },
    {
        "q": "When you were the pre-flop raiser, did you defend OFTEN enough against a 3-bet?",
        "desc": ("You raise pre-flop and get 3-bet. Do you defend often enough against this "
                 "attack? If not, savvy players will 3-bet you widely and steal a lot of pots "
                 "from you."),
        "stages": [
            ("Overall",        100, 42, 70),
        ],
    },
    {
        "q": "When you were the pre-flop raiser, did you defend AGGRESSIVELY enough against a 3-bet?",
        "desc": ("Once again, you raise pre-flop and get 3-bet. But here we are looking at "
                 "whether you defended aggressively enough by 4-betting. Calling too many "
                 "3-bets, especially out of position, can be costly."),
        "stages": [
            ("Overall",        0, 26, None),
        ],
    },
    {
        "q": "How aggressive are you on the flop and beyond?",
        "desc": ("By being aggressive (betting and raising), you have 2 ways to win the pot. "
                 "Your opponent may fold, or you may show down the best hand. When calling, "
                 "you only have one way to win. This measurement shows how often you were "
                 "aggressive vs how often you called."),
        "stages": [
            ("Aggression factor", 1, 2.3, 4.3),
        ],
        "unit": "",   # numeric not percent
        "max":  6.0,
    },
    {
        "q": "How often did you fold to a continuation bet?",
        "desc": ("If you fold to too many c-bets, observant opponents will exploit you. "
                 "If you fold to too few, you'll call down with hopeless holdings."),
        "stages": [
            ("Overall",        72, 45, 60),
        ],
    },
    {
        "q": "How big do you typically open-raise pre-flop?",
        "desc": ("Open-raise sizing affects how often you steal blinds vs how much you "
                 "lose when called. 2.0-2.5x is standard in MTTs; bigger opens leak chips."),
        "stages": [
            ("Overall (x BB)", 3.1, 2.0, 2.6),
        ],
        "unit": "x",
        "max":  5.0,
    },
]


def _question_block(q: dict) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:0;}}"
    )
    v = QVBoxLayout(f)
    v.setContentsMargins(20, 16, 20, 16)
    v.setSpacing(6)

    title = QLabel(q["q"])
    title.setStyleSheet(f"color:{_C_TEXT};font-size:16px;font-weight:700;background:transparent;")
    title.setWordWrap(True)
    v.addWidget(title)

    desc = QLabel(q["desc"])
    desc.setStyleSheet(f"color:{_C_MUTED};font-size:12px;background:transparent;")
    desc.setWordWrap(True)
    v.addWidget(desc)
    v.addSpacing(8)

    max_val = q.get("max", 100.0)
    unit    = q.get("unit", "%")

    for stage in q["stages"]:
        label, val, low, high = stage
        # Stage label
        st_lbl = QLabel(label)
        st_lbl.setAlignment(Qt.AlignCenter)
        st_lbl.setStyleSheet(f"color:{_C_TEXT};font-size:13px;font-weight:600;background:transparent;padding-top:6px;")
        v.addWidget(st_lbl)
        # Range bar
        bar = RangeBar(value=val, low=low, high=high, max_val=max_val, unit=unit)
        v.addWidget(bar)
    return f


class SkillsReportScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setStyleSheet(f"background:{_C_BG};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:0;min-height:24px;}"
        )

        content = QWidget()
        content.setStyleSheet(f"background:{_C_BG};")
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)

        # Header
        title = QLabel("📊  Skills Report")
        title.setStyleSheet(f"color:{_C_TEXT};font-size:24px;font-weight:800;background:transparent;")
        root.addWidget(title)

        sub = QLabel(
            "Her bir leak için kişisel değerin önerilen aralıkla karşılaştırılır. "
            "Yeşil = aralık içinde, kırmızı = dışında. 'No Data' = bu kategori için "
            "henüz yeterli el oynamadın."
        )
        sub.setStyleSheet(f"color:{_C_MUTED};font-size:13px;background:transparent;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        warning = QLabel(
            "⚠  Warning! Bu raporun anlamlı olması için 100+ el oyna. "
            "Şu an demo değerler gösteriliyor."
        )
        warning.setStyleSheet(
            f"background:{_C_HEADER};color:#92400E;font-size:12px;"
            f"padding:8px 12px;border-radius:0;font-weight:600;"
        )
        warning.setWordWrap(True)
        root.addWidget(warning)

        # Question blocks
        for q in SKILL_QUESTIONS:
            root.addWidget(_question_block(q))

        root.addStretch(1)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
