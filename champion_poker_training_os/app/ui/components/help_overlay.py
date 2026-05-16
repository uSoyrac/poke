"""Global keyboard-shortcut help overlay.

Nielsen heuristik #10 (Help & Documentation) + #6 (Recognition rather than
recall). Press '?' anywhere in the app → semi-transparent overlay listing
every keyboard shortcut grouped by screen.

Press '?' or Esc again to close.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter
from PySide6.QtWidgets import (
    QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)


_SHORTCUTS = [
    ("Genel", [
        ("?",          "Bu yardım ekranını aç/kapa"),
        ("Esc",        "Aktif diyalogu/menüyü kapat"),
        ("Ctrl+1…9",   "Sidebar nav (1=Welcome, 2=Dashboard, …)"),
    ]),
    ("Karar ekranları (Spot / GTO / Tournament)", [
        ("1",                  "FOLD"),
        ("2",                  "CHECK / CALL"),
        ("3",                  "RAISE / BET"),
        ("4",                  "ALL-IN / JAM"),
        ("Space / Enter / N",  "Sonraki el / spot — feedback gösterilince"),
        ("Panele tık",         "Feedback paneline tık → sonraki (mouse alternatifi)"),
    ]),
    ("Tournament Play", [
        ("Auto: AÇIK", "Üst bardaki ⏵ Auto butonu — eller otomatik akar"),
        ("📁 Past",     "Geçmiş turnuvaları gör (çift tık → el geçmişi)"),
    ]),
    ("My Mistakes / Drilling", [
        ("⚡ Drill Bunları", "Spot Trainer'ı leak signature ile filtreli aç"),
        ("✓ Çözüldü",        "Leak'i manuel olarak drilled işaretle"),
        ("3 doğru üst üste", "AUTO drilled — leak otomatik kapanır"),
    ]),
]


class HelpOverlay(QDialog):
    """Keyboard-shortcut cheat sheet."""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Klavye Kısayolları")
        self.setMinimumSize(780, 720)
        self.resize(820, 800)
        self.setStyleSheet(
            "QDialog{background:#0A0E14;}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header pinned at the top (doesn't scroll)
        head_frame = QFrame()
        head_frame.setStyleSheet("QFrame{background:#0A0E14;border-bottom:1px solid #1E2733;}")
        hdr = QHBoxLayout(head_frame)
        hdr.setContentsMargins(28, 18, 28, 14)
        title = QLabel("⌨  Klavye Kısayolları")
        title.setStyleSheet("color:#E5E7EB;font-size:22px;font-weight:800;")
        hdr.addWidget(title)
        hdr.addStretch(1)
        close = QPushButton("Kapat (Esc)")
        close.setFixedHeight(34)
        close.setStyleSheet(
            "QPushButton{background:#0F141C;color:#E5E7EB;border:1px solid #1E2733;"
            "border-radius:6px;padding:0 18px;font-size:12px;}"
            "QPushButton:hover{border-color:#22D3EE;color:#22D3EE;}"
        )
        close.clicked.connect(self.accept)
        hdr.addWidget(close)
        outer.addWidget(head_frame)

        # Scrollable body — never clip even at small dialog sizes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:4px;min-height:24px;}"
        )
        body_w = QWidget()
        body_w.setStyleSheet("background:transparent;")
        root = QVBoxLayout(body_w)
        root.setContentsMargins(28, 18, 28, 22)
        root.setSpacing(18)
        scroll.setWidget(body_w)
        outer.addWidget(scroll, 1)

        # Sections
        for section_title, shortcuts in _SHORTCUTS:
            block = QFrame()
            block.setStyleSheet(
                "QFrame{background:#0F141C;border:1px solid #1E2733;border-radius:8px;}"
            )
            v = QVBoxLayout(block)
            v.setContentsMargins(16, 12, 16, 12)
            v.setSpacing(6)
            sh = QLabel(section_title)
            sh.setStyleSheet(
                "color:#22D3EE;font-size:13px;font-weight:800;"
                "letter-spacing:1px;background:transparent;"
            )
            v.addWidget(sh)
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(8)
            grid.setColumnMinimumWidth(0, 160)   # key pill column (room for "Space / Enter / N")
            grid.setColumnStretch(0, 0)
            grid.setColumnStretch(1, 1)          # description fills rest
            for i, (key, desc) in enumerate(shortcuts):
                # Wrap pill in a small left-aligned container so it doesn't stretch
                k_wrap = QHBoxLayout()
                k_wrap.setContentsMargins(0, 0, 0, 0)
                k_lbl = QLabel(key)
                k_lbl.setStyleSheet(
                    "background:#1B2330;color:#22D3EE;font-family:'SF Mono',Monaco,monospace;"
                    "font-size:11px;font-weight:700;padding:3px 10px;"
                    "border:1px solid #2A3441;border-radius:4px;"
                )
                k_lbl.setAlignment(Qt.AlignCenter)
                k_lbl.setFixedHeight(22)
                k_wrap.addWidget(k_lbl, 0, Qt.AlignLeft)
                k_wrap.addStretch(1)
                k_wrap_w = QWidget(); k_wrap_w.setLayout(k_wrap)
                d_lbl = QLabel(desc)
                d_lbl.setStyleSheet("color:#E5E7EB;font-size:12px;background:transparent;")
                d_lbl.setWordWrap(True)
                grid.addWidget(k_wrap_w, i, 0)
                grid.addWidget(d_lbl, i, 1)
            v.addLayout(grid)
            root.addWidget(block)

        root.addStretch(1)

        # Bottom note about usability standards
        note = QLabel(
            "💡 Bu app Nielsen 10 heuristic + NASA-TLX + SUS ölçeklerine "
            "göre tasarlandı. Eksik bulduğun ergonomi sorunlarını paylaş."
        )
        note.setStyleSheet(
            "color:#9CA3AF;font-size:11px;font-style:italic;"
            "padding:6px;background:transparent;"
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        root.addWidget(note)

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() in (Qt.Key_Escape, Qt.Key_Question):
            self.accept()
            return
        super().keyPressEvent(ev)
