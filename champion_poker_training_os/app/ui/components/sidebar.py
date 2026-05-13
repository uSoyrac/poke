from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# Map nav item name → (icon, short label shown in sidebar)
_NAV_META: dict[str, tuple[str, str]] = {
    "Welcome":                      ("🏠", "Ana Sayfa"),
    "Dashboard":                    ("📊", "Dashboard"),
    "Play Session":                 ("🃏", "Masa Oyna"),
    "Tournament Play Mode":         ("🏆", "Turnuva Oyna"),
    "Heads-Up Trainer":             ("⚔️",  "Heads-Up"),
    "Fast Play Simulator":          ("⚡", "Hızlı Oyun"),
    "GTO Trainer (Range View)":     ("🎯", "GTO Trainer"),
    "GTO Study Library":            ("📚", "Çalışma Kitaplığı"),
    "Spot Practice Trainer":        ("🔎", "Spot Antrenman"),
    "Drills":                       ("💪", "Drills"),
    "Preflop Range Trainer":        ("📐", "Preflop Range"),
    "Range Viewer":                 ("👁️",  "Range Viewer"),
    "Postflop Trainer":             ("🌊", "Postflop"),
    "River Decision Trainer":       ("🏁", "River Trainer"),
    "ICM / PKO Trainer":            ("💰", "ICM / PKO"),
    "Math Lab":                     ("🧮", "Math Lab"),
    "Hands":                        ("🗂️",  "El Geçmişi"),
    "Hand History Analyzer":        ("🔬", "El Analiz"),
    "Leak Finder":                  ("🩺", "Leak Finder"),
    "Tournament Simulator":         ("🎲", "Turnuva Sim"),
    "Combat Trainer":               ("🥊", "Combat"),
    "AI Poker Coach":               ("🤖", "AI Coach"),
    "Reports":                      ("📈", "Raporlar"),
    "Aggregated Reports":           ("📋", "Toplu Rapor"),
    "Knowledge Base":               ("🧠", "Bilgi Bankası"),
    "Study Planner":                ("📅", "Çalışma Planı"),
    "Table Settings":               ("🎰", "Masa Ayarları"),
    "Settings / Compliance Guard":  ("⚙️",  "Ayarlar"),
}

# Section headers with the nav items they contain (ordered)
_SECTIONS: list[tuple[str, list[str]]] = [
    ("", [
        "Welcome",
        "Dashboard",
    ]),
    ("OYNA", [
        "Play Session",
        "Tournament Play Mode",
        "Heads-Up Trainer",
        "Fast Play Simulator",
    ]),
    ("GTO ÖĞREN", [
        "GTO Trainer (Range View)",
        "GTO Study Library",
        "Spot Practice Trainer",
        "Drills",
        "Preflop Range Trainer",
        "Range Viewer",
        "Postflop Trainer",
        "River Decision Trainer",
        "ICM / PKO Trainer",
        "Math Lab",
    ]),
    ("ANALİZ", [
        "Hands",
        "Hand History Analyzer",
        "Leak Finder",
        "Tournament Simulator",
        "Combat Trainer",
        "AI Poker Coach",
        "Reports",
        "Aggregated Reports",
    ]),
    ("AYARLAR", [
        "Knowledge Base",
        "Study Planner",
        "Table Settings",
        "Settings / Compliance Guard",
    ]),
]


class SidebarNav(QFrame):
    """Scrollable sidebar navigation with section headers and icons."""
    navigation_requested = Signal(str)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Brand header — pinned, doesn't scroll
        header = QFrame()
        header.setObjectName("SidebarHeader")
        header.setStyleSheet(
            "QFrame#SidebarHeader{"
            "background:#0A0E14;"
            "border-bottom:1px solid #1E2733;"
            "}"
        )
        hl = QVBoxLayout(header)
        hl.setContentsMargins(14, 14, 14, 12)
        hl.setSpacing(2)
        brand = QLabel("♠ Champion\nPoker OS")
        brand.setStyleSheet("color:#E5E7EB;font-size:15px;font-weight:800;line-height:1.4;")
        sub = QLabel("Offline GTO Lab")
        sub.setStyleSheet("color:#22D3EE;font-size:11px;font-weight:600;")
        hl.addWidget(brand)
        hl.addWidget(sub)
        outer.addWidget(header)

        # Scrollable nav
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:5px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:3px;min-height:20px;}"
            "QScrollBar::handle:vertical:hover{background:#3A5070;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none;}"
        )

        inner = QWidget()
        inner.setObjectName("SidebarScrollInner")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 6, 8, 16)
        inner_layout.setSpacing(1)

        group = QButtonGroup(self)
        group.setExclusive(True)

        # Build section-aware nav
        items_set = set(items)
        for section_title, section_items in _SECTIONS:
            if section_title:
                lbl = QLabel(section_title)
                lbl.setStyleSheet(
                    "color:#4B5563;"
                    "font-size:10px;"
                    "font-weight:700;"
                    "letter-spacing:1.5px;"
                    "padding:10px 6px 4px 6px;"
                )
                inner_layout.addWidget(lbl)

            for item in section_items:
                if item not in items_set:
                    continue
                icon, short = _NAV_META.get(item, ("•", item))
                label = f"  {icon}  {short}"
                button = QPushButton(label)
                button.setCheckable(True)
                button.setObjectName("NavButton")
                button.setMinimumHeight(36)
                button.setToolTip(item)
                button.setStyleSheet(
                    "QPushButton#NavButton{"
                    "text-align:left;"
                    "padding:0 10px;"
                    "border-radius:8px;"
                    "font-size:13px;"
                    "font-weight:500;"
                    "color:#9CA3AF;"
                    "background:transparent;"
                    "border:none;"
                    "}"
                    "QPushButton#NavButton:hover{"
                    "color:#E5E7EB;"
                    "background:#131A24;"
                    "}"
                    "QPushButton#NavButton:checked{"
                    "color:#22D3EE;"
                    "background:#0D2030;"
                    "font-weight:700;"
                    "border-left:3px solid #22D3EE;"
                    "padding-left:7px;"
                    "}"
                )
                button.clicked.connect(lambda _=False, n=item: self.navigation_requested.emit(n))
                group.addButton(button)
                self.buttons[item] = button
                inner_layout.addWidget(button)

        # Fallback: any items not in _SECTIONS mapping
        for item in items:
            if item not in self.buttons:
                icon, short = _NAV_META.get(item, ("•", item))
                button = QPushButton(f"  {icon}  {short}")
                button.setCheckable(True)
                button.setObjectName("NavButton")
                button.setMinimumHeight(36)
                button.setToolTip(item)
                button.clicked.connect(lambda _=False, n=item: self.navigation_requested.emit(n))
                group.addButton(button)
                self.buttons[item] = button
                inner_layout.addWidget(button)

        inner_layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        if items:
            self.set_active(items[0])

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)
            try:
                area = self.findChild(QScrollArea)
                if area is not None:
                    area.ensureWidgetVisible(self.buttons[item], 0, 40)
            except Exception:
                pass
