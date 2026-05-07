from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.poker.ranges import demo_frequency, range_matrix


COLOR_RAISE = QColor("#10B981")
COLOR_CALL = QColor("#22D3EE")
COLOR_MIX = QColor("#8B5CF6")
COLOR_FOLD = QColor("#1F2937")
COLOR_BORDER = QColor("#2D3748")
COLOR_SELECT = QColor("#F59E0B")
COLOR_TEXT = QColor("#E5E7EB")
COLOR_TEXT_DIM = QColor("#9CA3AF")


def freq_color(freq: int) -> QColor:
    if freq >= 80:
        return COLOR_RAISE
    if freq >= 50:
        return COLOR_CALL
    if freq >= 25:
        return COLOR_MIX
    return COLOR_FOLD


class RangeCell(QWidget):
    """One hand combo cell. Renders frequency bar + label, optionally selectable."""

    clicked = Signal(str)

    def __init__(self, hand: str, freq: int, selectable: bool = False):
        super().__init__()
        self.hand = hand
        self.freq = freq
        self.selectable = selectable
        self.selected = False
        self.show_freq = True
        self.setFixedSize(QSize(46, 36))
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor if selectable else Qt.ArrowCursor)
        self.setToolTip(f"{hand}: {freq}% solver frequency")

    def set_freq(self, freq: int) -> None:
        self.freq = freq
        self.update()

    def set_selected(self, value: bool) -> None:
        if self.selected == value:
            return
        self.selected = value
        self.update()

    def set_show_freq(self, value: bool) -> None:
        self.show_freq = value
        self.update()

    def mousePressEvent(self, event) -> None:
        if self.selectable and event.button() == Qt.LeftButton:
            self.selected = not self.selected
            self.update()
            self.clicked.emit(self.hand)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)

        # Base background — fold colour with subtle tint
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#161B22"))
        painter.drawRoundedRect(rect, 4, 4)

        if self.show_freq and self.freq > 0:
            color = freq_color(self.freq)
            inner = rect.adjusted(2, 2, -2, -2)
            fill_h = int(inner.height() * (self.freq / 100.0))
            fill_rect = QRect(inner.x(), inner.bottom() - fill_h, inner.width(), fill_h)
            tinted = QColor(color)
            tinted.setAlpha(220 if self.freq >= 60 else 170)
            painter.setBrush(tinted)
            painter.drawRoundedRect(fill_rect, 3, 3)

        # Border
        border_color = COLOR_SELECT if self.selected else COLOR_BORDER
        pen = QPen(border_color, 2 if self.selected else 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)

        # Hand label
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(COLOR_TEXT))
        painter.drawText(rect, Qt.AlignCenter, self.hand)
        painter.end()


class RangeGrid(QWidget):
    """13×13 range grid. Read-only by default, set selectable=True for quiz mode."""

    selection_changed = Signal(set)
    cell_clicked = Signal(str)

    def __init__(self, mode: str = "BTN RFI", selectable: bool = False, show_title: bool = True):
        super().__init__()
        self.mode = mode
        self.selectable = selectable
        self.cells: dict[str, RangeCell] = {}
        self._selected: set[str] = set()
        self._frequencies: dict[str, int] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        if show_title:
            header = QHBoxLayout()
            self.title_label = QLabel(f"Range Grid — {mode}")
            self.title_label.setObjectName("SectionTitle")
            header.addWidget(self.title_label)
            header.addStretch(1)
            self.legend = QLabel("● Pure raise  ● Mixed call  ● Bluff/mix  ● Fold")
            self.legend.setObjectName("Muted")
            header.addWidget(self.legend)
            layout.addLayout(header)
        else:
            self.title_label = None

        grid = QGridLayout()
        grid.setSpacing(2)
        for row, hands in enumerate(range_matrix()):
            for col, hand in enumerate(hands):
                freq = demo_frequency(hand, mode)
                self._frequencies[hand] = freq
                cell = RangeCell(hand, freq, selectable=selectable)
                cell.clicked.connect(self._on_cell_clicked)
                grid.addWidget(cell, row, col)
                self.cells[hand] = cell
        layout.addLayout(grid)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if self.title_label is not None:
            self.title_label.setText(f"Range Grid — {mode}")
        for hand, cell in self.cells.items():
            freq = demo_frequency(hand, mode)
            self._frequencies[hand] = freq
            cell.set_freq(freq)

    def set_frequencies(self, freq_map: dict[str, int]) -> None:
        for hand, freq in freq_map.items():
            self._frequencies[hand] = freq
            cell = self.cells.get(hand)
            if cell:
                cell.set_freq(freq)

    def set_show_frequencies(self, value: bool) -> None:
        for cell in self.cells.values():
            cell.set_show_freq(value)

    def clear_selection(self) -> None:
        for cell in self.cells.values():
            cell.set_selected(False)
        self._selected.clear()
        self.selection_changed.emit(set(self._selected))

    def selection(self) -> set[str]:
        return set(self._selected)

    def solver_range(self, threshold: int = 50) -> set[str]:
        return {h for h, f in self._frequencies.items() if f >= threshold}

    def frequency_of(self, hand: str) -> int:
        return self._frequencies.get(hand, 0)

    def _on_cell_clicked(self, hand: str) -> None:
        cell = self.cells.get(hand)
        if not cell:
            return
        if cell.selected:
            self._selected.add(hand)
        else:
            self._selected.discard(hand)
        self.cell_clicked.emit(hand)
        self.selection_changed.emit(set(self._selected))
