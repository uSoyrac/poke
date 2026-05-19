"""My Mistakes — kullanıcının yaptığı hataları gruplayıp drill yapmaya
yönlendiren ekran. Her hata `mistakes_queue` JSON dosyasından geliyor.

Görünüm:
  ┌─────────────────────────────────────────────────────────────────┐
  │  🩺 My Mistakes (24)              [Tümünü Temizle] [Drill All] │
  ├─────────────────────────────────────────────────────────────────┤
  │  📌 BTN / SRP / raise        (5 örnek)        ⚡ Drill Bunları │
  │     son 5 hata, ortalama EV kaybı 0.42bb                       │
  │  📌 BB / 3BP / call          (3 örnek)        ⚡ Drill Bunları │
  │     ortalama EV kaybı 0.71bb                                    │
  │  ...                                                            │
  └─────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.mistakes_queue import (
    MistakeEntry, load_mistakes, clear_mistakes, grouped_by_leak,
    mark_signature_drilled,
)


# Poke-aligned constants (legacy _C_* names preserved for diff sanity)
from app.ui.theme import poke_tokens as _t
_C_BG     = _t.BG
_C_CARD   = _t.SURFACE
_C_PANEL  = _t.SURFACE
_C_BORDER = _t.LINE
_C_MUTED  = _t.MUTED
_C_TEXT   = _t.INK
_C_CYAN   = _t.ACCENT
_C_GREEN  = _t.ACCENT
_C_RED    = _t.DANGER
_C_BLUE   = _t.INFO
_C_AMBER  = _t.WARN
_C_PURPLE = _t.INFO


def _btn(label: str, primary: bool = False) -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(34)
    b.setCursor(Qt.PointingHandCursor)
    if primary:
        b.setStyleSheet(
            f"QPushButton{{background:{_C_CYAN};color:#061018;border:none;"
            f"border-radius:0;padding:0 18px;font-size:12px;font-weight:800;}}"
            f"QPushButton:hover{{background:#0EA9C2;}}"
        )
    else:
        b.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:0;padding:0 14px;"
            f"font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        )
    return b


def _leak_card(signature: str, mistakes: list[MistakeEntry],
               on_drill, on_resolve=None) -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_C_PANEL};border:1px solid {_C_BORDER};border-radius:0;}}"
        f"QFrame:hover{{border-color:{_C_CYAN};}}"
    )
    v = QVBoxLayout(f)
    v.setContentsMargins(18, 14, 18, 14)
    v.setSpacing(8)

    avg_loss = sum(m.ev_loss for m in mistakes) / max(1, len(mistakes))
    severity_color = _C_GREEN if avg_loss < 0.3 else _C_AMBER if avg_loss < 0.8 else _C_RED

    row1 = QHBoxLayout()
    tag = QLabel("📌  " + signature)
    tag.setStyleSheet(f"color:{_C_TEXT};font-size:15px;font-weight:800;background:transparent;")
    row1.addWidget(tag)
    row1.addStretch(1)
    count = QLabel(f"{len(mistakes)} örnek")
    count.setStyleSheet(f"color:{severity_color};font-size:13px;font-weight:700;background:transparent;")
    row1.addWidget(count)
    drill_btn = _btn("⚡  Drill Bunları", primary=True)
    drill_btn.clicked.connect(lambda: on_drill(signature, mistakes))
    row1.addWidget(drill_btn)
    if on_resolve is not None:
        resolve_btn = _btn("✓ Çözüldü")
        resolve_btn.clicked.connect(lambda: on_resolve(signature))
        row1.addWidget(resolve_btn)
    v.addLayout(row1)

    detail = QLabel(
        f"Ortalama EV kaybı: {avg_loss:.2f}bb  ·  "
        f"En kötü: {max(m.ev_loss for m in mistakes):.2f}bb  ·  "
        f"Son hata: {mistakes[0].logged_at[:16]}"
    )
    detail.setStyleSheet(f"color:{_C_MUTED};font-size:11px;background:transparent;")
    v.addWidget(detail)

    # Up-to-3 example rows
    for m in mistakes[:3]:
        row = QLabel(
            f"   • {m.hero_cards or '??'}  →  sen: {m.hero_action.upper()}  ·  "
            f"GTO: {m.gto_action.upper()}  ·  −{m.ev_loss:.2f}bb"
        )
        row.setStyleSheet(f"color:{_C_TEXT};font-size:11px;background:transparent;font-family:'SF Mono', Monaco, monospace;")
        v.addWidget(row)
    return f


class MyMistakesScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self._state = state
        self.setStyleSheet(f"background:{_C_BG};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(
            f"QFrame{{background:{_C_PANEL};border-bottom:1px solid {_C_BORDER};}}"
        )
        hr = QHBoxLayout(header)
        hr.setContentsMargins(24, 12, 24, 12)
        # Mono eyebrow + section title (compact for the top bar)
        eyebrow = QLabel("21 /")
        eyebrow.setStyleSheet(
            f"color:{_C_MUTED}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-weight: 500; font-size: 10px; "
            f"padding-right: 8px;"
        )
        hr.addWidget(eyebrow)
        self._title_lbl = QLabel("My mistakes")
        self._title_lbl.setStyleSheet(
            f"color:{_C_TEXT}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-weight: 700; font-size: 18px;"
        )
        hr.addWidget(self._title_lbl)
        hr.addStretch(1)

        clear_btn = _btn("Tümünü Temizle")
        clear_btn.clicked.connect(self._clear_all)
        hr.addWidget(clear_btn)

        refresh_btn = _btn("↻  Yenile", primary=True)
        refresh_btn.clicked.connect(self._refresh)
        hr.addWidget(refresh_btn)
        outer.addWidget(header)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:0;min-height:24px;}"
        )
        self._content = QWidget()
        self._content.setStyleSheet(f"background:{_C_BG};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 18, 24, 24)
        self._content_layout.setSpacing(12)
        scroll.setWidget(self._content)
        outer.addWidget(scroll, 1)

        self._refresh()

    # ── helpers ───────────────────────────────────────────────────────

    def _refresh(self) -> None:
        # Clear current cards
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        all_mistakes = load_mistakes()
        # Show only open leaks; drilled mistakes hidden (Welcome counter
        # tracks open vs drilled separately)
        mistakes = [m for m in all_mistakes if not m.drilled]
        drilled_count = len(all_mistakes) - len(mistakes)
        title_extra = f" · {drilled_count} çözüldü" if drilled_count else ""
        self._title_lbl.setText(
            f"My mistakes  ({len(mistakes)} açık{title_extra})"
        )

        if not mistakes:
            empty = QLabel(
                "🎉  Henüz kayıtlı hata yok.\n\n"
                "Tournament Play veya Spot Trainer'da bir hata yaptığında "
                "buraya otomatik düşecek. Sonra benzer spotları drill ederek "
                "leak'leri kapatabilirsin."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                f"color:{_C_MUTED};font-size:14px;padding:80px 20px;background:transparent;"
            )
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch(1)
            return

        # Summary banner
        total_loss = sum(m.ev_loss for m in mistakes)
        banner = QLabel(
            f"📊  Toplam {len(mistakes)} hata kayıtlı  ·  "
            f"toplam EV kaybı {total_loss:.2f}bb  ·  "
            f"{len(grouped_by_leak(mistakes))} farklı leak tipi"
        )
        banner.setStyleSheet(
            f"background:#0E2A1E;color:#6EE7B7;font-size:12px;font-weight:700;"
            f"padding:10px 14px;border-radius:0;border:1px solid #10B981;"
        )
        self._content_layout.addWidget(banner)

        groups = grouped_by_leak(mistakes)
        # Sort by avg EV loss descending — biggest leaks first
        ordered = sorted(
            groups.items(),
            key=lambda kv: -sum(m.ev_loss for m in kv[1]) / max(1, len(kv[1])),
        )
        for sig, group in ordered:
            self._content_layout.addWidget(
                _leak_card(sig, group, self._start_drill, self._resolve_leak)
            )
        self._content_layout.addStretch(1)

    def _resolve_leak(self, signature: str) -> None:
        """Manuel: kullanıcı bu leak'i çözdüğünü düşünüyorsa hepsini drilled işaretle."""
        n = mark_signature_drilled(signature)
        try:
            from app.ui.components.toast import Toast
            Toast.show_success(self.window(),
                f"✓ '{signature}' çözüldü olarak işaretlendi ({n} hata kapatıldı)")
        except Exception:
            pass
        self.coach_message.emit(
            f"✓ '{signature}' çözüldü olarak işaretlendi ({n} hata kapatıldı)."
        )
        self._refresh()

    def _clear_all(self) -> None:
        clear_mistakes()
        self._refresh()

    def _start_drill(self, signature: str, mistakes: list[MistakeEntry]) -> None:
        """Navigate to Spot Trainer focused on similar spots."""
        # Save the active leak signature for the trainer to read
        self._state.active_leak_signature = signature
        self._state.active_leak_mistakes  = [m.id for m in mistakes]
        self.coach_message.emit(
            f"Drilling '{signature}' — {len(mistakes)} kayıtlı hata. "
            f"Spot Trainer'da benzer spotlar açılacak."
        )
        self.navigate_requested.emit("Spot Practice Trainer")
