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


class SidebarNav(QFrame):
    """Scrollable sidebar navigation.

    Wraps all nav buttons inside a QScrollArea so that, no matter how many
    items there are or how short the window is, every item stays reachable.
    """
    navigation_requested = Signal(str)

    def __init__(self, items: list[str]):
        super().__init__()
        self.setObjectName("Sidebar")
        self.buttons: dict[str, QPushButton] = {}

        # Outer layout — brand header pinned on top, scrollable nav fills rest
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Brand header (fixed, doesn't scroll)
        header = QFrame()
        header.setObjectName("SidebarHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 16, 14, 12)
        header_layout.setSpacing(2)
        brand = QLabel("Champion\nPoker Training OS")
        brand.setObjectName("SectionTitle")
        brand.setWordWrap(True)
        subtitle = QLabel("Offline solver lab")
        subtitle.setObjectName("Cyan")
        header_layout.addWidget(brand)
        header_layout.addWidget(subtitle)
        outer.addWidget(header)

        # Scrollable nav buttons region — every item reachable even on small windows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:6px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:3px;min-height:24px;}"
            "QScrollBar::handle:vertical:hover{background:#3A4A60;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none;}"
        )

        inner = QWidget()
        inner.setObjectName("SidebarScrollInner")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(10, 4, 10, 14)
        inner_layout.setSpacing(4)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for item in items:
            button = QPushButton(item)
            button.setCheckable(True)
            button.setObjectName("NavButton")
            button.setMinimumHeight(34)
            button.setToolTip(item)  # full label on hover even if truncated
            button.clicked.connect(lambda checked=False, name=item: self.navigation_requested.emit(name))
            group.addButton(button)
            self.buttons[item] = button
            inner_layout.addWidget(button)
        inner_layout.addStretch(1)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        self.set_active(items[0])

    def set_active(self, item: str) -> None:
        if item in self.buttons:
            self.buttons[item].setChecked(True)
            # Scroll the active item into view so it's never hidden
            try:
                btn = self.buttons[item]
                area = self.findChild(QScrollArea)
                if area is not None:
                    area.ensureWidgetVisible(btn, 0, 40)
            except Exception:
                pass
