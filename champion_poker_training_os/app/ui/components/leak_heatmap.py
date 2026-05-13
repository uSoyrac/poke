"""LeakHeatmap — 8-position × 5-pot-type accuracy grid.

Visual map of where the user is losing EV. Each cell is one
(position, pot_type) combination. Colour intensity = severity:
  bright green = high accuracy (≥85%)
  green       = good           (70-85%)
  amber       = needs work     (50-70%)
  red         = leak detected  (<50%)

Click a cell to emit `cell_clicked(position, pot_type)` — caller can route
the user into a focused drill pack.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


# Order matters — top-down on the heatmap (early position → blind position)
POSITIONS = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
POT_TYPES = ["SRP", "3BP", "4BP", "Limped", "Squeeze"]


@dataclass
class LeakCell:
    sample:    int   = 0
    correct:   int   = 0
    ev_loss:   float = 0.0

    @property
    def accuracy(self) -> float:
        return (self.correct / self.sample) if self.sample else 0.0

    @property
    def severity(self) -> str:
        """red | amber | green | bright_green | unknown"""
        if self.sample == 0:    return "unknown"
        a = self.accuracy
        if a >= 0.85:           return "bright_green"
        if a >= 0.70:           return "green"
        if a >= 0.50:           return "amber"
        return "red"


SEVERITY_COLOURS = {
    "bright_green": (QColor("#10B981"), "#FFFFFF"),
    "green":        (QColor("#0E7C61"), "#E5E7EB"),
    "amber":        (QColor("#B45309"), "#FEF3C7"),
    "red":          (QColor("#991B1B"), "#FECACA"),
    "unknown":      (QColor("#1F2937"), "#6B7280"),
}


class LeakHeatmap(QWidget):
    """Click-to-drill leak grid: 8 positions × 5 pot types."""

    cell_clicked = Signal(str, str)  # emits (position, pot_type)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells: dict[tuple[str, str], LeakCell] = {}
        self._hover: Optional[tuple[str, str]] = None
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(420, 380)
        self.setMouseTracking(True)

    # ── public API ─────────────────────────────────────────────────────
    def set_data(self, cells: dict[tuple[str, str], LeakCell]) -> None:
        self._cells = dict(cells)
        self.update()

    def set_data_from_leaks(self, leaks: list[dict]) -> None:
        """Accepts the output of LeakDetectionAgent.run().data['leaks']."""
        self._cells = {}
        for leak in leaks or []:
            pos = leak.get("position", "")
            pot = leak.get("pot_type", "")
            if pos not in POSITIONS or pot not in POT_TYPES:
                continue
            sample  = int(leak.get("sample", 0))
            ev_loss = float(leak.get("total_ev_loss", 0.0))
            # Estimate correct count from EV loss density
            avg     = float(leak.get("avg_ev_loss", 0.0))
            wrongs  = max(0, int(round(min(sample, ev_loss / max(avg, 0.1)))))
            correct = max(0, sample - wrongs)
            self._cells[(pos, pot)] = LeakCell(sample=sample, correct=correct, ev_loss=ev_loss)
        self.update()

    def clear(self) -> None:
        self._cells.clear()
        self.update()

    def cell_at(self, x: float, y: float) -> Optional[tuple[str, str]]:
        """Hit-test: return (position, pot_type) for the pixel coordinate."""
        ox, oy, cw, ch, lw = self._geometry()
        col = int((x - ox - lw) / cw)
        row = int((y - oy) / ch)
        if 0 <= row < len(POSITIONS) and 0 <= col < len(POT_TYPES):
            return (POSITIONS[row], POT_TYPES[col])
        return None

    # ── interaction ────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:
        hit = self.cell_at(event.position().x(), event.position().y())
        if hit != self._hover:
            self._hover = hit
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton:
            return
        hit = self.cell_at(event.position().x(), event.position().y())
        if hit:
            self.cell_clicked.emit(*hit)

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    # ── geometry & paint ──────────────────────────────────────────────
    def _geometry(self) -> tuple[float, float, float, float, float]:
        """Returns (origin_x, origin_y, cell_w, cell_h, label_w)."""
        label_w = 70  # left column for position labels
        top_h   = 28  # top row for pot-type headers
        avail_w = max(0, self.width() - label_w - 16)
        avail_h = max(0, self.height() - top_h - 16)
        cw = avail_w / len(POT_TYPES)
        ch = avail_h / len(POSITIONS)
        return 8, top_h + 8, cw, ch, label_w

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        ox, oy, cw, ch, lw = self._geometry()

        # Header row — pot types
        header_font = QFont(); header_font.setBold(True); header_font.setPointSize(11)
        painter.setFont(header_font)
        painter.setPen(QPen(QColor("#9CA3AF")))
        for ci, pot in enumerate(POT_TYPES):
            x = ox + lw + ci * cw
            painter.drawText(int(x), 0, int(cw), int(oy - 2), Qt.AlignCenter, pot)

        # Body
        body_font = QFont(); body_font.setBold(True); body_font.setPointSize(10)
        for ri, pos in enumerate(POSITIONS):
            y = oy + ri * ch
            # Position label
            painter.setFont(header_font)
            painter.setPen(QPen(QColor("#E5E7EB")))
            painter.drawText(int(ox), int(y), int(lw), int(ch), Qt.AlignVCenter | Qt.AlignRight, pos + "  ")
            # Cells
            for ci, pot in enumerate(POT_TYPES):
                x = ox + lw + ci * cw
                cell = self._cells.get((pos, pot))
                sev = cell.severity if cell else "unknown"
                bg, fg = SEVERITY_COLOURS[sev]
                # Hover highlight: tint border cyan
                is_hover = self._hover == (pos, pot)
                painter.fillRect(int(x + 1), int(y + 1), int(cw - 2), int(ch - 2), bg)
                painter.setPen(QPen(QColor("#22D3EE") if is_hover else QColor("#0B0F14"), 2 if is_hover else 1))
                painter.drawRect(int(x + 1), int(y + 1), int(cw - 2), int(ch - 2))
                # Content
                painter.setFont(body_font)
                painter.setPen(QPen(QColor(fg)))
                if cell and cell.sample > 0:
                    lines = [f"{cell.accuracy*100:.0f}%", f"-{cell.ev_loss:.1f}bb",
                             f"n={cell.sample}"]
                else:
                    lines = ["—"]
                line_h = (ch - 8) / max(1, len(lines))
                for li, line in enumerate(lines):
                    painter.drawText(
                        int(x), int(y + 4 + li * line_h),
                        int(cw), int(line_h),
                        Qt.AlignCenter, line,
                    )
        painter.end()
