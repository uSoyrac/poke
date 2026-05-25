from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


# Logical grouping for the brutalist sidebar
NAV_GROUPS = [
    ("MAIN", [
        "Dashboard",
        "Play Session",
        "Tournament Simulator",
        "My Profile",
    ]),
    ("TRAINING", [
        "GTO Study Library",
        "Spot Practice Trainer",
        "Preflop Range Trainer",
        "Postflop Trainer",
        "River Decision Trainer",
        "Combat Trainer",
        "Math Lab",
    ]),
    ("ANALYSIS", [
        "Hand History Analyzer",
        "Fast Play Simulator",
        "ICM / PKO Trainer",
        "Leak Finder",
        "AI Poker Coach",
        "Reports",
    ]),
    ("LIBRARY", [
        "Opponent Profiles",
        "Knowledge Base",
        "Study Planner",
        "Settings / Compliance Guard",
    ]),
]


class SidebarNav(QFrame):
    navigation_requested = Signal(str)

    EXPANDED_WIDTH = 232
    COLLAPSED_WIDTH = 52

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.EXPANDED_WIDTH)
        self.buttons: dict[str, QPushButton] = {}
        self._collapsed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Brand block + collapse toggle
        brand_box = QFrame()
        brand_box.setStyleSheet("border-bottom: 1px solid #23271f;")
        brand_l = QHBoxLayout(brand_box)
        brand_l.setContentsMargins(20, 16, 12, 16)
        brand_l.setSpacing(8)

        brand_text_col = QVBoxLayout()
        brand_text_col.setContentsMargins(0, 0, 0, 0)
        brand_text_col.setSpacing(2)
        # Style Guide § nav__brand-mark — "POKE" + lime "." dot
        self.brand_label = QLabel("POKE<span style='color:#5ad17a;'>.</span>")
        self.brand_label.setTextFormat(Qt.RichText)
        self.brand_label.setObjectName("BrandMark")
        self.brand_tag = QLabel("CHAMPION OS / v2.0")
        self.brand_tag.setObjectName("BrandTag")
        brand_text_col.addWidget(self.brand_label)
        brand_text_col.addWidget(self.brand_tag)
        brand_l.addLayout(brand_text_col, 1)

        self.toggle_btn = QPushButton("◀")
        self.toggle_btn.setObjectName("PaneToggle")  # styled per design (accent on hover)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedSize(28, 28)
        self.toggle_btn.setToolTip("Collapse sidebar (⌘B)")
        self.toggle_btn.clicked.connect(self.toggle_collapsed)
        brand_l.addWidget(self.toggle_btn, 0, Qt.AlignTop)

        root.addWidget(brand_box)

        # Scrollable nav body
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(0, 10, 0, 14)
        body_l.setSpacing(0)
        self._body = body
        self._group_labels: list[QLabel] = []

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        items_set = set(items)
        used = set()
        for group_name, group_items in NAV_GROUPS:
            valid = [i for i in group_items if i in items_set]
            if not valid:
                continue
            label = QLabel(group_name)
            label.setObjectName("NavGroupLabel")
            self._group_labels.append(label)
            body_l.addSpacing(8)
            body_l.addWidget(label)
            for item in valid:
                used.add(item)
                btn = self._make_button(item)
                body_l.addWidget(btn)

        # Anything not categorized
        leftover = [i for i in items if i not in used]
        if leftover:
            label = QLabel("OTHER")
            label.setObjectName("NavGroupLabel")
            self._group_labels.append(label)
            body_l.addSpacing(8)
            body_l.addWidget(label)
            for item in leftover:
                btn = self._make_button(item)
                body_l.addWidget(btn)

        body_l.addStretch(1)
        self.scroll.setWidget(body)
        root.addWidget(self.scroll, 1)

        # Footer / user + mini profil
        self._footer = QFrame()
        self._footer.setStyleSheet("border-top: 1px solid #23271f;")
        f_l = QVBoxLayout(self._footer)
        f_l.setContentsMargins(16, 10, 16, 10)
        f_l.setSpacing(4)

        user_row = QHBoxLayout()
        user = QLabel("UYGAR")
        user.setObjectName("SectionTitle")
        meta = QLabel("GTO MODE")
        meta.setObjectName("BrandTag")
        meta.setStyleSheet("color: #5ad17a; font-size:10px;")
        user_row.addWidget(user)
        user_row.addStretch(1)
        user_row.addWidget(meta)
        f_l.addLayout(user_row)

        # Mini profil stats (DB'den — gizlenmiş bileşen, update_profile() ile güncellenir)
        self._profile_strip = QLabel("—")
        self._profile_strip.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:9px; "
            "color:#5a5e54; letter-spacing:0.5px; background:transparent;"
        )
        self._profile_strip.setWordWrap(True)
        f_l.addWidget(self._profile_strip)
        self.refresh_profile()

        # "Shortcuts ?" link — clicking opens the cheat-sheet dialog. The
        # actual ? keystroke also opens it (wired in MainWindow), this
        # button is the discoverable entry-point for mouse-driven users.
        self.shortcuts_btn = QPushButton("Shortcuts  ?")
        self.shortcuts_btn.setObjectName("NavButton")
        self.shortcuts_btn.setCursor(Qt.PointingHandCursor)
        self.shortcuts_btn.setStyleSheet(
            "QPushButton#NavButton { padding-top: 8px; padding-bottom: 8px; "
            "color: #898d80; font-size: 12px; }"
            "QPushButton#NavButton:hover { color: #5ad17a; background: #131613; }"
        )
        f_l.addWidget(self.shortcuts_btn)
        root.addWidget(self._footer)

        if items:
            self.set_active(items[0])

    def _make_button(self, item: str) -> QPushButton:
        btn = QPushButton(item)
        btn.setCheckable(True)
        btn.setObjectName("NavButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, name=item: self.navigation_requested.emit(name))
        self.group.addButton(btn)
        self.buttons[item] = btn
        return btn

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)

    def refresh_profile(self) -> None:
        """DB'den kişisel profil istatistiklerini çek ve footer'ı güncelle."""
        try:
            from app.db.repository import get_player_stats, get_leak_analysis
            stats = get_player_stats()
            leaks = get_leak_analysis()
            total = stats.get("total_hands", 0)
            if total < 3:
                self._profile_strip.setText("Henüz veri yok")
                return
            vpip   = stats.get("vpip", 0)
            pfr    = stats.get("pfr", 0)
            bb100  = stats.get("bb_per_100", 0)
            top_leak = leaks[0]["name"] if leaks else "—"
            self._profile_strip.setText(
                f"VPIP {vpip:.0f}% · PFR {pfr:.0f}% · {bb100:+.1f}BB/100\n"
                f"Leak: {top_leak[:22]}"
            )
        except Exception:
            self._profile_strip.setText("Profil yükleniyor...")

    def toggle_collapsed(self) -> None:
        """Toggle between full sidebar and a narrow rail with just the toggle.

        When collapsed: shows only the toggle button so the play area gets
        the screen back. Click the ▶ chevron (or press ⌘B) to expand again.
        """
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.setFixedWidth(self.COLLAPSED_WIDTH)
            self.brand_label.hide()
            self.brand_tag.hide()
            self.scroll.hide()
            self._footer.hide()
            self.toggle_btn.setText("▶")
            self.toggle_btn.setToolTip("Expand sidebar (⌘B)")
        else:
            self.setFixedWidth(self.EXPANDED_WIDTH)
            self.brand_label.show()
            self.brand_tag.show()
            self.scroll.show()
            self._footer.show()
            self.toggle_btn.setText("◀")
            self.toggle_btn.setToolTip("Collapse sidebar (⌘B)")
            self.refresh_profile()  # sidebar açılınca profili tazele
