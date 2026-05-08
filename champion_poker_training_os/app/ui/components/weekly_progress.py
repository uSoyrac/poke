"""WeeklyProgressChart — last-7-days bar chart of drills + profit + accuracy.

Pulls from played_hands and adaptive_spots via app.training.weekly_stats.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.training.weekly_stats import collect_weekly_stats


class WeeklyProgressChart(QWidget):
    """7-day bar chart: drill count (cyan) + hands (purple) + profit overlay (green/red)."""

    def __init__(self, days: list[dict] | None = None):
        super().__init__()
        self.days = days if days is not None else collect_weekly_stats()
        self.setMinimumHeight(170)
        self.setMinimumWidth(420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def refresh(self) -> None:
        self.days = collect_weekly_stats()
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        margin_x = 28
        margin_y = 26
        chart_w = w - margin_x * 2
        chart_h = h - margin_y * 2

        # Backdrop grid lines
        painter.setPen(QPen(QColor("#1E2733"), 1))
        for frac in (0.25, 0.5, 0.75):
            y = margin_y + int(chart_h * frac)
            painter.drawLine(margin_x, y, w - margin_x, y)

        if not self.days:
            return

        # Find scale: use max(drills, hands)
        max_count = max(
            max((d["drills"] for d in self.days), default=0),
            max((d["hands"] for d in self.days), default=0),
            5,  # never zero — keeps bars visible
        )

        n = len(self.days)
        col_w = chart_w / n
        gap = 6
        bar_w = (col_w - gap * 2) / 2  # two bars per day side-by-side

        for i, day in enumerate(self.days):
            cx = margin_x + col_w * i + gap
            # Drills bar (cyan)
            drills_h = int(chart_h * day["drills"] / max_count)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#22D3EE"))
            painter.drawRoundedRect(
                int(cx), margin_y + chart_h - drills_h, int(bar_w), drills_h, 2, 2,
            )
            # Hands bar (purple)
            hands_h = int(chart_h * day["hands"] / max_count)
            painter.setBrush(QColor("#8B5CF6"))
            painter.drawRoundedRect(
                int(cx + bar_w + 1), margin_y + chart_h - hands_h, int(bar_w), hands_h, 2, 2,
            )
            # Day label
            painter.setPen(QPen(QColor("#9CA3AF")))
            font = QFont(); font.setPointSize(9); font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(margin_x + col_w * i, margin_y + chart_h + 4, col_w, 16),
                Qt.AlignCenter, day["label"],
            )
            # Accuracy small text on top of the bar
            if day["drills"] > 0:
                painter.setPen(QPen(QColor("#10B981" if day["accuracy"] >= 60 else "#F59E0B")))
                font_acc = QFont(); font_acc.setPointSize(8); font_acc.setBold(True)
                painter.setFont(font_acc)
                painter.drawText(
                    QRectF(margin_x + col_w * i, margin_y - 6, col_w, 16),
                    Qt.AlignCenter, f"{day['accuracy']:.0f}%",
                )

        # Legend
        font = QFont(); font.setPointSize(9); font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#22D3EE")))
        painter.drawText(margin_x, h - 4, "■ Drills")
        painter.setPen(QPen(QColor("#8B5CF6")))
        painter.drawText(margin_x + 80, h - 4, "■ Hands")
        # Empty-state overlay
        if all(d["drills"] == 0 and d["hands"] == 0 for d in self.days):
            painter.setPen(QPen(QColor("#4B5563")))
            font_empty = QFont(); font_empty.setPointSize(11)
            painter.setFont(font_empty)
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "No data yet — play hands or solve drills to fill this chart.")
        painter.end()
