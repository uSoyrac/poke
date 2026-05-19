"""TopStatusBar — Poke brutalist editorial topbar.

Anatomy (mirrors theme.css `.top` rules):

    ┌──────────────────────────────────────────────────────────────────┐
    │ 01 /  Dashboard   Search…           │ RTA-GUARD ✓ │ AI: local   │
    └──────────────────────────────────────────────────────────────────┘
      └─ left crumbs ────────────────────┘ └─ right status cells ──┘

  • 56 px tall (Poke standard)
  • Mono numeric eyebrow + Space Grotesk title + mono sub
  • Right side: status cells separated by 1-px vertical hairlines
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QWidget

from app.core.app_state import AppState
from app.core.rta_guard import RtaGuardStatus
from app.ui.theme import poke_tokens as t


# Slot number for the eyebrow — derived from NAV_ITEMS position when set
_DEFAULT_NUM = "00"


def _vsep() -> QWidget:
    """1-px vertical line — Poke uses hairlines between status cells."""
    sep = QFrame()
    sep.setFixedWidth(1)
    sep.setStyleSheet(f"background: {t.LINE};")
    return sep


class ComplianceStatusBadge(QLabel):
    """RTA-Guard cell — green when active, red when locked."""

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._set("STRICT ACTIVE", t.ACCENT)

    def _set(self, text: str, color: str) -> None:
        self.setText(f"●  {text}")
        self.setStyleSheet(
            f"color: {color}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f"font-weight: 600; padding: 0 16px;"
        )

    def set_status(self, status: RtaGuardStatus) -> None:
        self._set(status.label.upper(),
                   t.DANGER_2 if status.locked else t.ACCENT)


class TopStatusBar(QFrame):
    """Brutalist editorial topbar."""

    # Emitted when the user clicks the IMPORT cell — MainWindow opens
    # the hand-history import dialog on this signal.
    import_clicked = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self._state_ref = state
        self.setObjectName("TopBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(t.TOPBAR_H)
        self.setStyleSheet(
            f"#TopBar {{ background: {t.BG}; "
            f"border-bottom: 1px solid {t.LINE}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Left side: crumbs (num · title · sub) ────────────────────
        crumbs = QFrame()
        crumbs.setStyleSheet(f"QFrame {{ background: transparent; }}")
        crumbs_h = QHBoxLayout(crumbs)
        crumbs_h.setContentsMargins(22, 0, 22, 0)
        crumbs_h.setSpacing(14)
        crumbs_h.setAlignment(Qt.AlignVCenter)

        self.num_label = QLabel(_DEFAULT_NUM + " /")
        self.num_label.setStyleSheet(
            f"color: {t.DIM}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f"font-weight: 500;"
        )
        crumbs_h.addWidget(self.num_label)

        self.mode_label = QLabel(state.active_mode)
        self.mode_label.setStyleSheet(
            f"color: {t.INK}; background: transparent; "
            f"font-family: 'Space Grotesk'; font-size: 16px; "
            f"font-weight: 600;"
        )
        crumbs_h.addWidget(self.mode_label)

        # Search input — mono, no radius, focus accent border
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search spots, leaks, hands…")
        self.search.setFixedWidth(280)
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {t.BG_2}; color: {t.INK}; "
            f"border: 1px solid {t.LINE_2}; padding: 6px 10px; "
            f"font-family: 'JetBrains Mono'; font-size: 12px; }}"
            f"QLineEdit:focus {{ border-color: {t.ACCENT}; }}"
        )
        crumbs_h.addWidget(self.search)
        crumbs_h.addStretch(1)
        layout.addWidget(crumbs, 1)

        # ── Right side: status cells with hairline separators ────────
        right = QFrame()
        right.setStyleSheet(
            f"QFrame {{ background: transparent; "
            f"border-left: 1px solid {t.LINE}; }}"
        )
        right_h = QHBoxLayout(right)
        right_h.setContentsMargins(0, 0, 0, 0)
        right_h.setSpacing(0)

        # Compliance cell
        self.compliance = ComplianceStatusBadge()
        right_h.addWidget(self._wrap_cell(self.compliance))
        right_h.addWidget(_vsep())

        # Last import cell — clickable. Opens the import dialog.
        self.import_label = QLabel(
            f"▸  IMPORT  {state.last_import}".upper()
        )
        self.import_label.setStyleSheet(
            f"color: {t.INK_2}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f"font-weight: 500; padding: 0 16px;"
        )
        self.import_label.setCursor(Qt.PointingHandCursor)
        self.import_label.setToolTip(
            "Click to import PokerStars / CoinPoker / GG hand histories"
        )
        # QLabel doesn't emit signals natively — wrap mousePressEvent so a
        # click on the cell fires our import_clicked signal.
        def _label_clicked(_ev, sig=self.import_clicked):
            sig.emit()
        self.import_label.mousePressEvent = _label_clicked
        right_h.addWidget(self._wrap_cell(self.import_label))
        right_h.addWidget(_vsep())

        # AI provider cell
        self.ai_label = QLabel(f"AI  {state.ai_provider}".upper())
        self.ai_label.setStyleSheet(
            f"color: {t.ACCENT}; background: transparent; "
            f"font-family: 'JetBrains Mono'; font-size: 11px; "
            f"font-weight: 600; padding: 0 16px;"
        )
        right_h.addWidget(self._wrap_cell(self.ai_label))

        layout.addWidget(right)

    # ── helpers ──────────────────────────────────────────────────────

    def _wrap_cell(self, content: QLabel) -> QFrame:
        """Each status cell stretches to full topbar height for the
        vertical separators to land cleanly."""
        f = QFrame()
        f.setStyleSheet("QFrame { background: transparent; }")
        h = QHBoxLayout(f)
        h.setContentsMargins(0, 0, 0, 0)
        h.setAlignment(Qt.AlignVCenter)
        h.addWidget(content)
        return f

    def set_mode(self, mode: str) -> None:
        self.mode_label.setText(mode)
        # Try to derive the slot number from NAV_ITEMS position
        try:
            from app.main import NAV_ITEMS
            if mode in NAV_ITEMS:
                idx = NAV_ITEMS.index(mode)
                self.num_label.setText(f"{idx:02d} /")
        except Exception:
            self.num_label.setText(_DEFAULT_NUM + " /")
