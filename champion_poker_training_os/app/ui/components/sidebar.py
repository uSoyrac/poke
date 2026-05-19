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
  padding: 0;
  border: 0;
  border-left: 2px solid transparent;
  background: transparent;
}}
QPushButton#NavButton:hover {{
  background: {t.SURFACE};
}}
QPushButton#NavButton:checked {{
  background: {t.SURFACE};
  border-left: 2px solid {t.ACCENT};
}}
QPushButton#NavButton QLabel {{ background: transparent; }}
"""

_NAVLBL_QSS = (
    f"color: {t.INK_2}; background: transparent; "
    f"font-family: 'Space Grotesk'; font-weight: 500; font-size: 13px;"
)
_NAVLBL_ACTIVE_QSS = (
    f"color: {t.INK}; background: transparent; "
    f"font-family: 'Space Grotesk'; font-weight: 600; font-size: 13px;"
)
_KBD_QSS = (
    f"color: {t.DIM}; background: {t.BG}; "
    f"border: 1px solid {t.LINE}; "
    f"padding: 1px 5px 1px 5px; "
    f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 9px;"
)
_KBD_ACTIVE_QSS = (
    f"color: {t.ACCENT}; background: {t.BG}; "
    f"border: 1px solid {t.LINE_2}; "
    f"padding: 1px 5px 1px 5px; "
    f"font-family: 'JetBrains Mono'; font-weight: 600; font-size: 9px;"
)


class SidebarNav(QFrame):
    """Scrollable Poke sidebar — section headers, active accent left-rule."""
    navigation_requested = Signal(str)

    # Emitted whenever the sidebar collapse state changes. The MainWindow
    # listens so it can persist the user preference if it wants to.
    collapse_toggled = Signal(bool)   # True = collapsed (icon-only), False = full

    EXPANDED_WIDTH = 232
    COLLAPSED_WIDTH = 56

    def __init__(self, items: list[str],
                 shortcuts: dict[str, str] | None = None,
                 *, collapsed: bool = False):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"#Sidebar {{ background: {t.BG_2}; "
            f"border-right: 1px solid {t.LINE}; }}"
        )
        self.buttons: dict[str, QPushButton] = {}
        self._labels: dict[str, QLabel] = {}
        self._kbd_chips: dict[str, QLabel] = {}
        self._section_rows: list[QWidget] = []
        self._shortcuts = shortcuts or {}
        self._collapsed = bool(collapsed)
        self.setFixedWidth(
            self.COLLAPSED_WIDTH if self._collapsed else self.EXPANDED_WIDTH
        )

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

        # Row 1: wordmark + collapse toggle button
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(8)
        # Wordmark with accent dot — mirrors theme.css `.nav__brand-mark::after`
        self._brand_full = QLabel(
            f"<span style=\"font-family:'Space Grotesk'; font-weight:700; "
            f"font-size:22px; color:{t.INK};\">poke</span>"
            f"<span style=\"color:{t.ACCENT}; font-weight:700; "
            f"font-size:22px;\">.</span>"
        )
        self._brand_full.setTextFormat(Qt.RichText)
        self._brand_full.setStyleSheet("background: transparent;")
        brand_row.addWidget(self._brand_full)
        brand_row.addStretch(1)

        # Toggle button — collapses sidebar to icons-only width
        self._collapse_btn = QPushButton("«")
        self._collapse_btn.setFixedSize(22, 22)
        self._collapse_btn.setCursor(Qt.PointingHandCursor)
        self._collapse_btn.setToolTip("Collapse sidebar (⌃B)")
        self._collapse_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: transparent; color: {t.MUTED};"
            f"  border: 1px solid {t.LINE_2};"
            f"  font-family: 'JetBrains Mono'; font-weight: 600; font-size: 12px;"
            f"  padding: 0;"
            f"}}"
            f"QPushButton:hover {{ color: {t.ACCENT}; border-color: {t.ACCENT}; }}"
        )
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        brand_row.addWidget(self._collapse_btn)
        bv.addLayout(brand_row)

        self._brand_tag = QLabel("CHAMPION POKER OS · v1")
        self._brand_tag.setStyleSheet(
            f"color: {t.DIM}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 9px; "
            f"font-weight: 500;"
        )
        bv.addWidget(self._brand_tag)
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
                sec_widget = self._section_label(section_title, len(present))
                self._section_rows.append(sec_widget)
                inner_layout.addWidget(sec_widget)

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

        # Apply initial collapse state — show the buttons/labels first so
        # they're laid out fully, then hide what should be hidden.
        if self._collapsed:
            self._apply_collapsed_state()

    # ── collapse / expand ────────────────────────────────────────────
    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == bool(collapsed):
            return
        self._collapsed = bool(collapsed)
        self._apply_collapsed_state()
        self.collapse_toggled.emit(self._collapsed)

    def _apply_collapsed_state(self) -> None:
        """Toggle width + nav-button labels + brand text for collapsed mode."""
        collapsed = self._collapsed
        self.setFixedWidth(
            self.COLLAPSED_WIDTH if collapsed else self.EXPANDED_WIDTH
        )
        # Brand: hide tag line + use short "p." mark when collapsed.
        self._brand_tag.setVisible(not collapsed)
        if collapsed:
            self._brand_full.setText(
                f"<span style=\"font-family:'Space Grotesk'; font-weight:700; "
                f"font-size:18px; color:{t.INK};\">p</span>"
                f"<span style=\"color:{t.ACCENT}; font-weight:700; "
                f"font-size:18px;\">.</span>"
            )
            self._collapse_btn.setText("»")
            self._collapse_btn.setToolTip("Expand sidebar (⌃B)")
        else:
            self._brand_full.setText(
                f"<span style=\"font-family:'Space Grotesk'; font-weight:700; "
                f"font-size:22px; color:{t.INK};\">poke</span>"
                f"<span style=\"color:{t.ACCENT}; font-weight:700; "
                f"font-size:22px;\">.</span>"
            )
            self._collapse_btn.setText("«")
            self._collapse_btn.setToolTip("Collapse sidebar (⌃B)")
        # Section headers: hide labels in collapsed mode (icons would be
        # too cramped). The nav-button labels themselves also get hidden so
        # only the active-rule + kbd chip remain visible.
        for row in self._section_rows:
            row.setVisible(not collapsed)
        for item, lbl in self._labels.items():
            # Show short form when collapsed: first letter of the short name
            if collapsed:
                short = lbl.text()
                lbl.setProperty("_full_text", short)
                # Pick the first non-space character for the icon-mark
                icon = short.strip()[:1].upper() if short.strip() else "•"
                lbl.setText(icon)
                lbl.setStyleSheet(
                    f"color: {t.INK_2}; background: transparent; "
                    f"font-family: 'JetBrains Mono'; font-weight: 600; "
                    f"font-size: 13px;"
                )
            else:
                full = lbl.property("_full_text")
                if full:
                    lbl.setText(full)
                # Reset style — _on_toggled will repaint if this row is checked
                btn = self.buttons.get(item)
                if btn and btn.isChecked():
                    self._on_toggled(item, True)
                else:
                    self._on_toggled(item, False)
        # Hide kbd chips in collapsed mode (no room)
        for chip in self._kbd_chips.values():
            chip.setVisible(not collapsed)

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
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setObjectName("NavButton")
        btn.setAttribute(Qt.WA_StyledBackground, True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(30)
        btn.setToolTip(item)
        btn.setStyleSheet(_NAVBTN_QSS)

        row = QHBoxLayout(btn)
        row.setContentsMargins(18, 6, 12, 6)
        row.setSpacing(8)

        lbl = QLabel(short)
        lbl.setStyleSheet(_NAVLBL_QSS)
        lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(lbl)
        row.addStretch(1)
        self._labels[item] = lbl

        kbd_text = self._shortcuts.get(item, "")
        if kbd_text:
            chip = QLabel(kbd_text)
            chip.setStyleSheet(_KBD_QSS)
            chip.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            row.addWidget(chip)
            self._kbd_chips[item] = chip

        btn.toggled.connect(lambda checked, it=item: self._on_toggled(it, checked))
        return btn

    def _on_toggled(self, item: str, checked: bool) -> None:
        lbl = self._labels.get(item)
        if lbl:
            lbl.setStyleSheet(_NAVLBL_ACTIVE_QSS if checked else _NAVLBL_QSS)
        chip = self._kbd_chips.get(item)
        if chip:
            chip.setStyleSheet(_KBD_ACTIVE_QSS if checked else _KBD_QSS)

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
