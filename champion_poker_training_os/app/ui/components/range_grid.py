from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.poker.ranges import demo_frequency, range_matrix


class RangeGrid(QWidget):
    def __init__(self, mode: str = "BTN RFI"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(f"Range Grid - {mode}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(2)
        for row, hands in enumerate(range_matrix()):
            for col, hand in enumerate(hands):
                freq = demo_frequency(hand, mode)
                button = QPushButton(hand)
                button.setFixedSize(42, 30)
                button.setToolTip(f"{hand}: {freq}% frequency")
                button.setStyleSheet(_cell_style(freq))
                grid.addWidget(button, row, col)
        layout.addLayout(grid)


def _cell_style(freq: int) -> str:
    if freq >= 80:
        color = QColor("#10B981")
    elif freq >= 50:
        color = QColor("#22D3EE")
    elif freq >= 25:
        color = QColor("#8B5CF6")
    else:
        color = QColor("#1F2937")
    return (
        f"background: {color.name()}; border: 1px solid #2D3748; "
        "border-radius: 3px; padding: 0; font-size: 10px; color: #E5E7EB;"
    )

