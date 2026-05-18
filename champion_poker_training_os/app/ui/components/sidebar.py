"""SidebarNav — Poke brutalist editorial sidebar.

Anatomy (mirrors theme.css `.nav` rules in the design handoff):

    ┌──────────────────────────────────┐
    │ poke.            CHAMPION OS · v1│  ← brand block
    ├──────────────────────────────────┤
    │ OYNA                       4     │  ← section label + count
    │ │ ♔  Masa Oyna              1    │
    │ │ ♚  Turnuva                2    │
    │   ...                            │
    └──────────────────────────────────┘

  • 232 px wide (Poke standard)
  • Active row: 2-px accent left-rule, surface background, accent ink
  • Hover row: surface background, ink secondary
  • Items grouped under uppercase mono section labels
"""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import poke_tokens as t


# Map nav item name → short label shown in sidebar.
# Icons removed — Poke is text-first / brutalist. Glyphs only when they earn
# their weight (status indicators, not decoration).
_NAV_META: dict[str, str] = {
    "Welcome":                      "Home",
    "Dashboard":                    "Dashboard",
    "Play Session":                 "Live Table",
    "Tournament Play Mode":         "Tournament",
    "Heads-Up Trainer":             "Heads-Up",
    "Fast Play Simulator":          "Fast Play",
    "Range Studio":                 "Range Studio",
    "GTO Study Library":            "Study Library",
    "Spot Practice Trainer":        "Spot Trainer",
    "Drills":                       "Drills",
    "Postflop Trainer":             "Postflop",
    "River Decision Trainer":       "River",
    "ICM / PKO Trainer":            "ICM / PKO",
    "Math Lab":                     "Math Lab",
    "Hands":                        "Hands",
    "Hand History Analyzer":        "Analyzer",
    "Leak Finder":                  "Leak Finder",
    "Skills Report":                "Skills Report",
    "My Mistakes":                  "My Mistakes",
    "Tournament Simulator":         "Tour. Sim",
    "Combat Trainer":               "Combat",
    "AI Poker Coach":               "AI Coach",
    "Reports":                      "Reports",
    "Aggregated Reports":           "Agg. Reports",
    "Knowledge Base":               "Knowledge",
    "Study Planner":                "Study Plan",
    "Table Settings":               "Table Setup",
    "Settings / Compliance Guard":  "Settings",
    "Style Guide":                  "Style Guide",
}

# Section headers with the nav items they contain (ordered).
_SECTIONS: list[tuple[str, list[str]]] = [
    ("", [
        "Welcome",
        "Dashboard",
    ]),
    ("PLAY", [
        "Play Session",
        "Tournament Play Mode",
        "Heads-Up Trainer",
        "Fast Play Simulator",
    ]),
    ("LEARN", [
        "Range Studio",
        "GTO Study Library",
        "Spot Practice Trainer",
        "Drills",
        "Postflop Trainer",
        "River Decision Trainer",
        "ICM / PKO Trainer",
        "Math Lab",
    ]),
    ("ANALYZE", [
        "Hands",
        "Hand History Analyzer",
        "Leak Finder",
        "Skills Report",
        "My Mistakes",
        "Tournament Simulator",
        "Combat Trainer",
        "AI Poker Coach",
        "Reports",
        "Aggregated Reports",
    ]),
    ("SETTINGS", [
        "Knowledge Base",
        "Study Planner",
        "Table Settings",
        "Settings / Compliance Guard",
        "Style Guide",
    ]),
]


# ─── styles ──────────────────────────────────────────────────────────


_BRAND_QSS = f"""
#SidebarBrand {{
  background: {t.BG_2};
  border-bottom: 1px solid {t.LINE};
}}
"""

_SCROLL_QSS = f"""
QScrollArea {{ background: transparent; border: 0; }}
QScrollBar:vertical {{ width: 5px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {t.LINE_2}; }}
QScrollBar::handle:vertical:hover {{ background: {t.MUTED}; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; background: none; }}
"""

_NAVBTN_QSS = f"""
QPushButton#NavButton {{
  text-align: left;
  padding: 6px 18px 6px 18px;
  border: 0;
  border-left: 2px solid transparent;
  color: {t.INK_2};
  background: transparent;
  font-family: 'Space Grotesk';
  font-weight: 500;
  font-size: 13px;
}}
QPushButton#NavButton:hover {{
  color: {t.INK};
  background: {t.SURFACE};
}}
QPushButton#NavButton:checked {{
  color: {t.INK};
  background: {t.SURFACE};
  border-left: 2px solid {t.ACCENT};
  font-weight: 600;
}}
"""


class SidebarNav(QFrame):
    """Scrollable Poke sidebar — section headers, active accent left-rule."""
    navigation_requested = Signal(str)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#Sidebar {{ background: {t.BG_2}; "
            f"border-right: 1px solid {t.LINE}; }}"
        )
        self.buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Brand block (pinned) ─────────────────────────────────────
        brand = QFrame()
        brand.setObjectName("SidebarBrand")
        brand.setAttribute(Qt.WA_StyledBackground, True)
        brand.setStyleSheet(_BRAND_QSS)
        bv = QVBoxLayout(brand)
        bv.setContentsMargins(20, 16, 20, 14)
        bv.setSpacing(4)

        # Wordmark with accent dot — mirrors theme.css `.nav__brand-mark::after`
        mark = QLabel(
            f"<span style=\"font-family:'Space Grotesk'; font-weight:700; "
            f"font-size:22px; color:{t.INK};\">poke</span>"
            f"<span style=\"color:{t.ACCENT}; font-weight:700; "
            f"font-size:22px;\">.</span>"
        )
        mark.setTextFormat(Qt.RichText)
        mark.setStyleSheet("background: transparent;")
        bv.addWidget(mark)

        tag = QLabel("CHAMPION POKER OS · v1")
        tag.setStyleSheet(
            f"color: {t.DIM}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 9px; "
            f"font-weight: 500;"
        )
        bv.addWidget(tag)
        outer.addWidget(brand)

        # ── Scrollable nav body ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(_SCROLL_QSS)

        inner = QWidget()
        inner.setStyleSheet(f"QWidget {{ background: {t.BG_2}; }}")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 8, 0, 16)
        inner_layout.setSpacing(0)

        group = QButtonGroup(self)
        group.setExclusive(True)

        items_set = set(items)
        for section_title, section_items in _SECTIONS:
            # Group label row (with count) — only if section has a title
            if section_title:
                present = [i for i in section_items if i in items_set]
                if not present:
                    continue
                inner_layout.addWidget(self._section_label(section_title, len(present)))

            for item in section_items:
                if item not in items_set:
                    continue
                btn = self._nav_button(item)
                btn.clicked.connect(
                    lambda _=False, n=item: self.navigation_requested.emit(n))
                group.addButton(btn)
                self.buttons[item] = btn
                inner_layout.addWidget(btn)

            # Tight gap between sections
            if section_title:
                spacer = QWidget()
                spacer.setFixedHeight(10)
                inner_layout.addWidget(spacer)

        # Fallback: any items not in _SECTIONS mapping (defensive)
        for item in items:
            if item not in self.buttons:
                btn = self._nav_button(item)
                btn.clicked.connect(
                    lambda _=False, n=item: self.navigation_requested.emit(n))
                group.addButton(btn)
                self.buttons[item] = btn
                inner_layout.addWidget(btn)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        if items:
            self.set_active(items[0])

    # ── helpers ──────────────────────────────────────────────────────

    def _section_label(self, text: str, count: int) -> QWidget:
        """Group header — uppercase JetBrains Mono with item count on the right."""
        row = QFrame()
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setStyleSheet("QFrame { background: transparent; }")
        h = QHBoxLayout(row)
        h.setContentsMargins(20, 12, 20, 6)
        h.setSpacing(8)

        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {t.DIM}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 9px; "
            f"font-weight: 500;"
        )
        h.addWidget(lbl)
        h.addStretch(1)
        cnt = QLabel(str(count))
        cnt.setStyleSheet(
            f"color: {t.MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 9px;"
        )
        h.addWidget(cnt)
        return row

    def _nav_button(self, item: str) -> QPushButton:
        short = _NAV_META.get(item, item)
        btn = QPushButton(short)
        btn.setCheckable(True)
        btn.setObjectName("NavButton")
        btn.setAttribute(Qt.WA_StyledBackground, True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(30)
        btn.setToolTip(item)
        btn.setStyleSheet(_NAVBTN_QSS)
        return btn

    # ── public API (unchanged) ───────────────────────────────────────

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)
            try:
                area = self.findChild(QScrollArea)
                if area is not None:
                    area.ensureWidgetVisible(self.buttons[item], 0, 40)
            except Exception:
                pass
