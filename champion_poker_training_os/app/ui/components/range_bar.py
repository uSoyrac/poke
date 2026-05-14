"""Range Bar — APT-style leak indicator with green target range + red out-of-range bubble.

Visualises whether the user's stat (VPIP, PFR, 3-bet %, etc.) sits inside the
recommended range. The bar is red when the value is out of range, green when in.
A bubble (callout) shows the actual value at the position along the bar.

Example:

    bar = RangeBar(value=48, low=19, high=33, max_val=100)
    # → Red bar, bubble shows "48%" pushed right of the green zone

    bar = RangeBar(value=23, low=19, high=33, max_val=100)
    # → Green bar, bubble centred inside the recommended range
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


# Palette tuned to APT's reference (light pink / mint green pills)
_C_RED_BG    = "#F6C5C5"   # out-of-range body
_C_RED_LINE  = "#D67878"
_C_GRN_BG    = "#C6E9C8"   # in-range body
_C_GRN_LINE  = "#5DB36F"
_C_NEUTRAL   = "#1F2937"   # no-data fill
_C_BUBBLE_BG = "#FFFFFF"
_C_BUBBLE_BR = "#374151"
_C_TEXT      = "#0F1419"
_C_MUTED     = "#6B7280"


class RangeBar(QWidget):
    """Painted bar with target range zone + value bubble."""

    def __init__(
        self,
        value:   Optional[float],
        low:     float,
        high:    Optional[float] = None,
        max_val: float = 100.0,
        unit:    str   = "%",
        label_below: str = "",
        no_data:  bool = False,
    ):
        super().__init__()
        self.value   = value
        self.low     = float(low)
        self.high    = float(high) if high is not None else None
        self.max_val = float(max_val)
        self.unit    = unit
        self.label_below = label_below
        self.no_data = no_data or value is None
        self.setMinimumHeight(56)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _in_range(self) -> bool:
        if self.no_data or self.value is None:
            return False
        if self.high is None:
            return self.value >= self.low
        return self.low <= self.value <= self.high

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        bar_h = 22
        bar_y = (h - bar_h) // 2 - 6
        pad   = 14

        in_range = self._in_range()
        if self.no_data:
            body = QColor(_C_NEUTRAL)
            line = QColor("#374151")
        elif in_range:
            body = QColor(_C_GRN_BG)
            line = QColor(_C_GRN_LINE)
        else:
            body = QColor(_C_RED_BG)
            line = QColor(_C_RED_LINE)

        # Pill body — full width of the bar with rounded caps
        bar_rect = QRectF(pad, bar_y, w - 2 * pad, bar_h)
        p.setBrush(body)
        p.setPen(QPen(line, 1))
        p.drawRoundedRect(bar_rect, bar_h / 2, bar_h / 2)

        # Recommended-range zone — outlined arrows + ticks at low/high inside the bar
        def x_for(v: float) -> float:
            v = max(0.0, min(self.max_val, v))
            return pad + (w - 2 * pad) * (v / self.max_val)

        if not self.no_data:
            x_lo = x_for(self.low)
            x_hi = x_for(self.high) if self.high is not None else (w - pad)
            # Vertical tick marks at low and high
            p.setPen(QPen(QColor("#374151"), 1.5))
            p.drawLine(int(x_lo), bar_y, int(x_lo), bar_y + bar_h)
            if self.high is not None:
                p.drawLine(int(x_hi), bar_y, int(x_hi), bar_y + bar_h)

        # Bubble (callout) — placed at value position with text inside
        if not self.no_data and self.value is not None:
            bx = x_for(self.value)
            bubble_w = 60
            bubble_h = 24
            bub_x = bx - bubble_w / 2
            bub_y = bar_y - 1
            # Clamp to widget bounds
            bub_x = max(2, min(w - bubble_w - 2, bub_x))
            p.setBrush(QColor(_C_BUBBLE_BG))
            p.setPen(QPen(QColor(_C_BUBBLE_BR), 1))
            p.drawRoundedRect(QRectF(bub_x, bub_y, bubble_w, bubble_h), bubble_h / 2, bubble_h / 2)
            p.setPen(QPen(QColor(_C_TEXT)))
            font = QFont(); font.setPointSize(10); font.setBold(True)
            p.setFont(font)
            text = f"{self.value:g}{self.unit}" if self.unit != "%" else f"{self.value:g} %"
            p.drawText(QRectF(bub_x, bub_y, bubble_w, bubble_h), Qt.AlignCenter, text)
        else:
            # "No Data" bubble on the far left
            bubble_w = 80
            bubble_h = 24
            p.setBrush(QColor(_C_BUBBLE_BG))
            p.setPen(QPen(QColor(_C_BUBBLE_BR), 1))
            p.drawRoundedRect(QRectF(pad - 2, bar_y - 1, bubble_w, bubble_h), bubble_h / 2, bubble_h / 2)
            p.setPen(QPen(QColor(_C_MUTED)))
            font = QFont(); font.setPointSize(9); font.setItalic(True)
            p.setFont(font)
            p.drawText(QRectF(pad - 2, bar_y - 1, bubble_w, bubble_h), Qt.AlignCenter, "No Data")

        # Below-bar label: "X% ← Recommended Range → Y%" (uses widget's unit)
        if not self.label_below:
            unit_suffix = f" {self.unit}" if self.unit else ""
            if self.high is not None:
                self.label_below = (
                    f"{self.low:g}{unit_suffix}  ←  Recommended Range  →  "
                    f"{self.high:g}{unit_suffix}"
                )
            else:
                self.label_below = f"{self.low:g}{unit_suffix}  ←  Recommended Range  →"

        below_y = bar_y + bar_h + 4
        p.setPen(QPen(QColor("#9CA3AF")))
        font = QFont(); font.setPointSize(10)
        p.setFont(font)
        p.drawText(QRectF(0, below_y, w, 18), Qt.AlignCenter, self.label_below)

        p.end()
