"""GTO-style range grid widget.

Her hücre 169 elden birini temsil eder. Aksiyon frekansına göre renklendirme:
  - Raise = kırmızı (#DC2626)
  - Call  = yeşil  (#10B981)
  - Fold  = mavi   (#1E40AF)
Mixed strategy → hücre dikey olarak böl, oranı yansıt (GTOWizard tarzı).

Kullanım:
    grid = RangeGrid(position="BTN", scenario="RFI", stack_depth=100, mode="cash")
    grid.refresh()
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QFont, QPen
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.poker.gto_ranges import get_action, range_matrix


# ── COLORS (GTOWizard-style palette) ─────────────────────────────────
COLOR_RAISE = QColor("#DC2626")   # kırmızı
COLOR_CALL  = QColor("#10B981")   # yeşil
COLOR_FOLD  = QColor("#2563EB")   # mavi
COLOR_BORDER = QColor("#0F1419")
COLOR_TEXT_LIGHT = QColor("#FAFAFA")
COLOR_TEXT_DARK = QColor("#0F1419")


class HandCell(QWidget):
    """Tek bir 13×13 hücre. İçinde hand label + action stripe."""

    clicked = Signal(str)   # hand_key

    def __init__(self, hand: str, action: dict, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.hand = hand
        self.action = action   # {"raise": pct, "call": pct, "fold": pct}
        self.setFixedSize(64, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self._tooltip())

    def _tooltip(self) -> str:
        parts = []
        for label, key in [("Raise", "raise"), ("Call", "call"), ("Fold", "fold")]:
            pct = self.action.get(key, 0)
            if pct > 0:
                parts.append(f"{label} {pct}%")
        return f"{self.hand} — " + ", ".join(parts) if parts else self.hand

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self.clicked.emit(self.hand)
        super().mousePressEvent(ev)

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        raise_pct = self.action.get("raise", 0)
        call_pct = self.action.get("call", 0)
        fold_pct = self.action.get("fold", 0)
        total = max(1, raise_pct + call_pct + fold_pct)

        # Hücre arka planı — yatay olarak böl: raise | call | fold
        # GTOWizard yatay layout: solda raise, ortada call, sağda fold
        x = rect.left()
        w_total = rect.width()
        for pct, color in [(raise_pct, COLOR_RAISE),
                           (call_pct, COLOR_CALL),
                           (fold_pct, COLOR_FOLD)]:
            if pct <= 0:
                continue
            seg_w = int(round(w_total * pct / total))
            if seg_w <= 0:
                continue
            seg_rect = QRect(x, rect.top(), seg_w, rect.height())
            p.fillRect(seg_rect, color)
            x += seg_w

        # Border
        p.setPen(QPen(COLOR_BORDER, 1))
        p.drawRect(rect)

        # Hand label — ortala, gölgeli yazı
        font = QFont("Inter, Helvetica, sans-serif")
        font.setPixelSize(12)
        font.setBold(True)
        p.setFont(font)
        # Beyaz yazı, hafif outline (her arka plana karşı okunabilir)
        p.setPen(QPen(COLOR_TEXT_DARK, 2))
        p.drawText(rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, self.hand)
        p.setPen(QPen(COLOR_TEXT_LIGHT, 1))
        p.drawText(rect, Qt.AlignCenter, self.hand)


class RangeGrid(QWidget):
    """13×13 range grid + legend."""

    hand_clicked = Signal(str)

    def __init__(self, position: str = "BTN", scenario: str = "RFI",
                 stack_depth: int = 100, mode: str = "cash",
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.position = position
        self.scenario = scenario
        self.stack_depth = stack_depth
        self.mode = mode
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.title = QLabel(self._title_text())
        self.title.setObjectName("SectionTitle")
        layout.addWidget(self.title)

        # Stats banner (range % gibi özet)
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #94A3B8; font-size: 11px; padding: 2px 0;"
        )
        layout.addWidget(self.stats_label)

        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setSpacing(1)
        self.grid.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.grid_widget, 1)

        # Legend (renk açıklamaları)
        legend = self._build_legend()
        layout.addWidget(legend)

        self.refresh()

    def _title_text(self) -> str:
        return (f"{self.position} — {self.scenario}  "
                f"({self.stack_depth}bb, {self.mode.upper()})")

    def _build_legend(self) -> QWidget:
        w = QWidget()
        h = QGridLayout(w)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(12)
        for i, (label, color) in enumerate([
            ("Raise", COLOR_RAISE), ("Call", COLOR_CALL), ("Fold", COLOR_FOLD)
        ]):
            swatch = QLabel("")
            swatch.setFixedSize(14, 14)
            swatch.setStyleSheet(
                f"background: {color.name()}; border: 1px solid #0F1419; "
                "border-radius: 2px;"
            )
            text = QLabel(label)
            text.setStyleSheet("color: #CBD5E1; font-size: 11px;")
            h.addWidget(swatch, 0, i * 2)
            h.addWidget(text, 0, i * 2 + 1)
        return w

    def set_config(self, position: str, scenario: str,
                   stack_depth: int, mode: str) -> None:
        self.position = position
        self.scenario = scenario
        self.stack_depth = stack_depth
        self.mode = mode
        self.title.setText(self._title_text())
        self.refresh()

    def refresh(self) -> None:
        # Eski hücreleri temizle
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Yeni hücreleri çiz + range yüzdesini hesapla
        total_combos = 0
        raise_combos = 0.0
        call_combos = 0.0
        for row, hands in enumerate(range_matrix()):
            for col, hand in enumerate(hands):
                action = get_action(self.position, hand, self.scenario,
                                    self.stack_depth, self.mode)
                cell = HandCell(hand, action)
                cell.clicked.connect(self.hand_clicked.emit)
                self.grid.addWidget(cell, row, col)
                # Combos sayısı: pair=6, suited=4, offsuit=12
                if len(hand) == 2:
                    combo_count = 6
                elif hand.endswith("s"):
                    combo_count = 4
                else:
                    combo_count = 12
                total_combos += combo_count
                raise_combos += combo_count * action.get("raise", 0) / 100
                call_combos += combo_count * action.get("call", 0) / 100

        # Range % istatistiği
        range_pct = (raise_combos + call_combos) / max(total_combos, 1) * 100
        raise_pct = raise_combos / max(total_combos, 1) * 100
        self.stats_label.setText(
            f"Range: {range_pct:.1f}%   ·   Raise: {raise_pct:.1f}%   ·   "
            f"Toplam {total_combos} kombo"
        )


# ── BACKWARDS COMPAT (eski API'yi koru) ──────────────────────────────

def _cell_style(freq: int) -> str:
    """Eski API — diğer dosyalar import edebilir."""
    if freq >= 80:
        c = COLOR_RAISE
    elif freq >= 50:
        c = QColor("#F59E0B")
    elif freq >= 25:
        c = QColor("#8B5CF6")
    else:
        c = COLOR_FOLD
    return (f"background: {c.name()}; border: 1px solid #0F1419; "
            "border-radius: 3px; padding: 0; font-size: 10px; color: #FAFAFA;")
