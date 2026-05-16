"""Toast notification widget — non-blocking ephemeral feedback.

Nielsen heuristik #1 (Visibility of System Status): kullanıcı bir aksiyon
yaptığında ortada modal pencere açmak yerine alt-sağda 3 sn beliren ve
otomatik kaybolan toast — akışı kesmez ama 'bir şey oldu' sinyalini verir.

Kullanım:
    Toast.show_info(parent, "Ayarlar kaydedildi")
    Toast.show_success(parent, "🎉 Leak çözüldü!")
    Toast.show_warning(parent, "⚠ Bağlantı zayıf")
    Toast.show_error(parent, "❌ Kart yüklenemedi")
"""
from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)


_PALETTES = {
    "info":    ("#0F141C", "#22D3EE", "#E5E7EB"),
    "success": ("#0E2A1E", "#10B981", "#6EE7B7"),
    "warning": ("#2A1F0E", "#F59E0B", "#FBBF24"),
    "error":   ("#2A0E0E", "#DC2626", "#FCA5A5"),
}


class Toast(QFrame):
    """Self-dismissing notification, fades in 200ms, lives N seconds, fades out 300ms."""

    def __init__(self, parent: QWidget, message: str, kind: str = "info",
                 duration_ms: int = 3000):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        bg, border, fg = _PALETTES.get(kind, _PALETTES["info"])
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {border};"
            f"border-radius:8px;}}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        lbl = QLabel(message)
        lbl.setStyleSheet(
            f"color:{fg};font-size:13px;font-weight:600;background:transparent;"
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # Opacity effect for fade-in/out animation
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        # Position bottom-right of parent
        self.adjustSize()
        if parent:
            pw = parent.width(); ph = parent.height()
            margin = 24
            x = max(margin, pw - self.width() - margin)
            y = max(margin, ph - self.height() - margin - 50)
            self.move(parent.mapToGlobal(self.rect().topLeft()).x() + x,
                      parent.mapToGlobal(self.rect().topLeft()).y() + y)

        # Fade-in
        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(200)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.start()

        # Schedule fade-out
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._begin_dismiss)
        self._dismiss_timer.start(duration_ms)

    def _begin_dismiss(self) -> None:
        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(300)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.deleteLater)
        self._fade_out.start()

    # ── Convenience factories ─────────────────────────────────────────

    @classmethod
    def show_info(cls, parent: QWidget, message: str, duration_ms: int = 3000) -> "Toast":
        t = cls(parent, message, "info", duration_ms)
        t.show()
        return t

    @classmethod
    def show_success(cls, parent: QWidget, message: str, duration_ms: int = 3000) -> "Toast":
        t = cls(parent, message, "success", duration_ms)
        t.show()
        return t

    @classmethod
    def show_warning(cls, parent: QWidget, message: str, duration_ms: int = 3500) -> "Toast":
        t = cls(parent, message, "warning", duration_ms)
        t.show()
        return t

    @classmethod
    def show_error(cls, parent: QWidget, message: str, duration_ms: int = 4500) -> "Toast":
        t = cls(parent, message, "error", duration_ms)
        t.show()
        return t
