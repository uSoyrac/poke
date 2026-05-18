"""Spot Practice Trainer — GTO Wizard-style interactive quiz.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │ [UTG fold] [LJ fold] [HJ fold] [CO fold] [BTN 2bb] [BB ●]  │  ← position strip
  ├───────────────────────────┬─────────────────────────────────┤
  │  [Spot List sidebar]      │  [Oval Poker Table]             │
  │  • 25bb LJ RFI vs BB     │  25bb 8Max MTT                  │
  │  • 40bb BTN vs LJ RFI    │  BB vs BTN Open Raise Ante 12.5%│
  │  …                        │  Hero cards + POT label          │
  ├───────────────────────────┴─────────────────────────────────┤
  │   [FOLD]   [CALL]   [RAISE 7.2bb]   [ALL-IN 25bb]          │  ← before answer
  │  After → [CHECK 95.4%] [BET 1.4 4.4%] [BET 23.0 0.1%]     │
  └─────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills, get_spot_categories
from app.solver.csv_importer import get_solver_library
from app.solver.mock_solver import compare_action, solve_spot
from app.training.trainer_scoring import score_decision, skill_label
from app.ui.components.action_buttons import GtoActionButton as _SharedGtoButton
from app.ui.components.action_chip import parse_action_string
from app.ui.components.card_view import CardView
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, OvalTable


# ── colour constants ──────────────────────────────────────────────────────
_C_BG       = "#0C1117"
_C_CARD     = "#131A24"
_C_BORDER   = "#1E2733"
_C_MUTED    = "#6B7280"
_C_TEXT     = "#E5E7EB"
_C_CYAN     = "#22D3EE"
_C_GREEN    = "#10B981"
_C_RED      = "#EF4444"
_C_AMBER    = "#F59E0B"

# Action button colour palettes: (background, border, text)
_BTN_FOLD   = ("#1B2D4A", "#3B82F6", "#93C5FD")
_BTN_CALL   = ("#0E2A1E", "#10B981", "#6EE7B7")
_BTN_RAISE  = ("#2A1B1B", "#EF4444", "#FCA5A5")
_BTN_JAM    = ("#1A0E0E", "#7F1D1D", "#FCA5A5")
_BTN_CHECK  = ("#0E2A1E", "#10B981", "#6EE7B7")
_BTN_BET    = ("#2A1B1B", "#EF4444", "#FCA5A5")


def _action_palette(action: str) -> tuple[str, str, str]:
    a = action.lower()
    if "fold" in a:       return _BTN_FOLD
    if "call" in a:       return _BTN_CALL
    if "check" in a:      return _BTN_CHECK
    if "jam" in a or "all" in a: return _BTN_JAM
    if "raise" in a or "3bet" in a or "4bet" in a: return _BTN_RAISE
    if "bet" in a:        return _BTN_BET
    return (_C_CARD, _C_BORDER, _C_TEXT)


def _action_display(action: str, spot: dict) -> str:
    """Human-readable label: CALL, RAISE 7.2bb, BET 1.4bb, etc."""
    a = action.lower()
    pot = float(spot.get("pot_bb", 10))
    stk = float(spot.get("stack_bb", 40))
    if "small" in a:   return f"BET {pot * 0.33:.1f}bb"
    if "medium" in a:  return f"BET {pot * 0.66:.1f}bb"
    if "large" in a:   return f"BET {pot * 1.10:.1f}bb"
    if "jam" in a or "all-in" in a: return f"ALL-IN {stk:.0f}bb"
    if "raise" in a:   return f"RAISE {pot * 2.4:.1f}bb"
    if "3bet" in a:    return f"3-BET {pot * 3:.1f}bb"
    if "4bet" in a:    return f"4-BET {pot * 4:.1f}bb"
    return action.upper()


class _GtoActionButton(QPushButton):
    """Action button that optionally shows a GTO frequency bar."""

    def __init__(self, label: str, action: str, parent=None):
        super().__init__(label, parent)
        self._action = action
        self._freq: float | None = None
        bg, border, fg = _action_palette(action)
        self._bg = bg; self._border = border; self._fg = fg
        self.setMinimumHeight(64)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._apply_style(False)

    def set_frequency(self, freq: float) -> None:
        """Show GTO % on button after user answers."""
        self._freq = freq
        self._apply_style(True)
        pct = f"{freq * 100:.1f}%"
        self.setText(f"{self.text().split(chr(10))[0]}\n{pct}")
        self.update()

    def _apply_style(self, answered: bool) -> None:
        opacity = "ff" if answered else "cc"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._bg};
                border: 2px solid {self._border};
                border-radius: 10px;
                color: {self._fg};
                font-size: 15px;
                font-weight: 800;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                border-color: {self._cyan_or_border()};
                background: {self._bg}dd;
            }}
        """)

    def _cyan_or_border(self) -> str:
        return _C_CYAN if self._freq is not None else self._border

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        if self._freq is not None and self._freq > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            r = self.rect()
            bar_w = max(4, int(r.width() * self._freq))
            bar_h = 4
            bar_y = r.height() - 8
            painter.setPen(Qt.NoPen)
            col = QColor(self._border)
            col.setAlphaF(0.8)
            painter.setBrush(col)
            painter.drawRoundedRect(8, bar_y, bar_w - 16, bar_h, 2, 2)
            painter.end()


class _PositionChip(QLabel):
    """Small chip showing a position + last action."""

    def __init__(self, position: str, action: str = "", is_hero: bool = False):
        super().__init__()
        self._pos = position
        self._action = action
        self._is_hero = is_hero
        self._refresh()
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(48)
        self.setMinimumWidth(64)

    def update_action(self, action: str, is_hero: bool = False) -> None:
        self._action = action
        self._is_hero = is_hero
        self._refresh()

    def _refresh(self) -> None:
        a = self._action.lower()
        if self._is_hero:
            bg, border, ac_color = "#1B2D4A", _C_CYAN, _C_CYAN
            action_text = "Action"
        elif "fold" in a or a == "f":
            bg, border, ac_color = "#0C1117", "#374151", _C_MUTED
            action_text = "Fold"
        elif a:
            bg, border, ac_color = "#0E2A1E", _C_GREEN, _C_GREEN
            action_text = self._action[:6]
        else:
            bg, border, ac_color = _C_CARD, _C_BORDER, _C_TEXT
            action_text = ""

        pos_html = f'<span style="color:{_C_TEXT};font-size:12px;font-weight:700;">{self._pos}</span>'
        act_html = f'<br><span style="color:{ac_color};font-size:11px;font-weight:600;">{action_text}</span>'
        self.setText(pos_html + (act_html if action_text else ""))
        self.setTextFormat(Qt.RichText)
        self.setStyleSheet(
            f"QLabel {{ background:{bg}; border:1.5px solid {border}; border-radius:8px; padding:4px 8px; }}"
        )


class SpotTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = generate_spot_drills(120)
        # Random start index so every session opens on a different spot
        self.index  = random.randint(0, max(0, len(self.drills) - 1))
        self.seed   = random.randint(1, 99)
        self._rng   = random.Random(self.seed)
        self._answered = False
        self._current_action_buttons: list[_GtoActionButton] = []

        # ── root layout ──────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── position strip (top bar) ─────────────────────────────────────
        pos_bar = QFrame()
        pos_bar.setObjectName("Card")
        pos_bar.setFixedHeight(62)
        pos_bar.setStyleSheet(f"QFrame#Card {{ background:{_C_CARD}; border-bottom:1px solid {_C_BORDER}; border-radius:0; }}")
        pos_row = QHBoxLayout(pos_bar)
        pos_row.setContentsMargins(12, 6, 12, 6)
        pos_row.setSpacing(6)

        # Mode buttons (left side of strip)
        for mode, icon in [("Quick", "⚡"), ("Timed", "⏱"), ("Mistakes", "❌"), ("Boss", "👑")]:
            b = QPushButton(f"{icon} {mode}")
            b.setFixedHeight(34)
            b.setStyleSheet(
                f"QPushButton{{background:{_C_BG};border:1px solid {_C_BORDER};border-radius:7px;"
                f"padding:4px 10px;color:{_C_MUTED};font-size:12px;}}"
                f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
            )
            b.clicked.connect(lambda _, m=mode: self.coach_message.emit(f"{m} modu aktif."))
            pos_row.addWidget(b)

        pos_row.addSpacing(16)
        pos_row.addWidget(_VSep())

        # Position chips (will be updated per spot)
        self._pos_chips: dict[str, _PositionChip] = {}
        positions_8max = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        for p in positions_8max:
            chip = _PositionChip(p, "Fold")
            self._pos_chips[p] = chip
            pos_row.addWidget(chip)

        pos_row.addStretch(1)

        # Source badge + reroll
        self.source_badge = QLabel("⚙ Mock")
        self.source_badge.setStyleSheet(
            f"QLabel{{background:#5C1F22;color:#F87171;font-weight:800;padding:4px 10px;border-radius:8px;font-size:11px;}}"
        )
        reroll = QPushButton("🎲")
        reroll.setFixedSize(36, 36)
        reroll.setToolTip("Reroll seed")
        reroll.setStyleSheet(
            f"QPushButton{{background:{_C_BG};border:1px solid {_C_BORDER};border-radius:8px;font-size:16px;}}"
            f"QPushButton:hover{{border-color:{_C_CYAN};}}"
        )
        reroll.clicked.connect(self._reroll)
        pos_row.addWidget(self.source_badge)
        pos_row.addWidget(reroll)
        root.addWidget(pos_bar)

        # ── main splitter ────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background: #1E2733; }")

        # ── LEFT: spot list ──────────────────────────────────────────────
        left_widget = QWidget()
        left_widget.setFixedWidth(260)
        left_widget.setStyleSheet(f"background:{_C_CARD}; border-right:1px solid {_C_BORDER};")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Format tab filters
        self._fmt_filter = "All"
        fmt_scroll = QScrollArea()
        fmt_scroll.setFixedHeight(44)
        fmt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fmt_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        fmt_scroll.setWidgetResizable(True)
        fmt_inner = QWidget()
        fmt_row = QHBoxLayout(fmt_inner)
        fmt_row.setContentsMargins(8, 6, 8, 6)
        fmt_row.setSpacing(4)
        self._fmt_tab_buttons: dict[str, QPushButton] = {}
        for tag in ["All", "MTT", "Cash", "ICM", "Explo"]:
            b = QPushButton(tag)
            b.setFixedHeight(28)
            b.setCheckable(True)
            b.setChecked(tag == "All")
            b.clicked.connect(lambda _, t=tag: self._set_fmt_filter(t))
            b.setStyleSheet(_tab_btn_style(tag == "All"))
            self._fmt_tab_buttons[tag] = b
            fmt_row.addWidget(b)
        fmt_scroll.setWidget(fmt_inner)
        left_layout.addWidget(fmt_scroll)

        # Street filter
        street_row = QHBoxLayout()
        street_row.setContentsMargins(8, 4, 8, 4)
        street_row.setSpacing(4)
        self._street_filter = "All"
        self._street_btns: dict[str, QPushButton] = {}
        for tag in ["All", "Preflop", "Postflop"]:
            b = QPushButton(tag)
            b.setFixedHeight(26)
            b.setCheckable(True)
            b.setChecked(tag == "All")
            b.clicked.connect(lambda _, t=tag: self._set_street_filter(t))
            b.setStyleSheet(_tab_btn_style(tag == "All", small=True))
            self._street_btns[tag] = b
            street_row.addWidget(b)
        left_layout.addLayout(street_row)

        # Spot list scroll
        spot_scroll = QScrollArea()
        spot_scroll.setWidgetResizable(True)
        spot_scroll.setStyleSheet(
            f"QScrollArea{{border:none;background:{_C_BG};}}"
            "QScrollBar:vertical{width:6px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#2A3A50;border-radius:3px;}"
        )
        self._spot_list_widget = QWidget()
        self._spot_list_widget.setStyleSheet(f"background:{_C_BG};")
        self._spot_list_layout = QVBoxLayout(self._spot_list_widget)
        self._spot_list_layout.setContentsMargins(0, 0, 0, 0)
        self._spot_list_layout.setSpacing(0)
        spot_scroll.setWidget(self._spot_list_widget)
        left_layout.addWidget(spot_scroll, 1)
        splitter.addWidget(left_widget)

        # ── RIGHT: table + actions ────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Oval table — capped so the feedback panel always fits without scroll
        self.oval = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=False)
        self.oval.set_dealer("BTN")
        self.oval.set_seed(self.seed)
        self.oval.setMinimumHeight(340)
        self.oval.setMaximumHeight(480)
        right_layout.addWidget(self.oval, 1)

        # Hero cards bar — visible cards + sizing input
        cards_bar = QFrame()
        cards_bar.setFixedHeight(96)
        cards_bar.setStyleSheet(f"background:#0A0F16;border-top:1px solid {_C_BORDER};")
        cb_row = QHBoxLayout(cards_bar)
        cb_row.setContentsMargins(16, 10, 16, 10)
        cb_row.setSpacing(12)

        cards_label = QLabel("Your hand:")
        cards_label.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        cb_row.addWidget(cards_label)

        self._hero_cards_row = QHBoxLayout()
        self._hero_cards_row.setSpacing(6)
        cards_widget = QWidget()
        cards_widget.setLayout(self._hero_cards_row)
        cb_row.addWidget(cards_widget)
        cb_row.addSpacing(20)

        # Sizing override input (overrides preset bet sizes for raise/bet buttons)
        sizing_label = QLabel("Bet sizing:")
        sizing_label.setStyleSheet(f"color:{_C_MUTED};font-size:12px;")
        cb_row.addWidget(sizing_label)
        self._sizing_input = QLineEdit()
        self._sizing_input.setPlaceholderText("e.g. 50%, 2.5x, 3bb")
        self._sizing_input.setFixedWidth(120)
        self._sizing_input.setFixedHeight(28)
        self._sizing_input.setStyleSheet(
            f"QLineEdit{{background:{_C_CARD};border:1px solid {_C_BORDER};"
            f"border-radius:5px;padding:2px 8px;color:{_C_TEXT};font-size:12px;}}"
            f"QLineEdit:focus{{border-color:{_C_CYAN};}}"
        )
        cb_row.addWidget(self._sizing_input)

        # Quick sizing pills
        for pct in ["33%", "50%", "75%", "100%", "150%"]:
            pill = QPushButton(pct)
            pill.setFixedHeight(28)
            pill.setStyleSheet(
                f"QPushButton{{background:{_C_CARD};color:{_C_TEXT};border:1px solid {_C_BORDER};"
                "border-radius:5px;padding:2px 10px;font-size:11px;}"
                f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
            )
            pill.clicked.connect(lambda _, v=pct: self._sizing_input.setText(v))
            cb_row.addWidget(pill)
        cb_row.addStretch(1)
        right_layout.addWidget(cards_bar)

        # Spot context label
        self.spot_ctx = QLabel()
        self.spot_ctx.setAlignment(Qt.AlignCenter)
        self.spot_ctx.setStyleSheet(
            f"QLabel{{color:{_C_MUTED};font-size:12px;padding:4px 16px;"
            f"background:{_C_BG};border-top:1px solid {_C_BORDER};}}"
        )
        right_layout.addWidget(self.spot_ctx)

        # ── Action buttons row ─────────────────────────────────────────
        self._action_frame = QFrame()
        self._action_frame.setStyleSheet(
            f"QFrame{{background:{_C_BG};border-top:1px solid {_C_BORDER};"
            "padding:12px 16px;}"
        )
        self._action_layout = QHBoxLayout(self._action_frame)
        self._action_layout.setContentsMargins(16, 10, 16, 10)
        self._action_layout.setSpacing(10)
        right_layout.addWidget(self._action_frame)

        # ── Feedback panel — clickable + cursor pointer hint ─────────────
        # Caps max height so it never pushes the action bar off-screen;
        # internal scroll if explanation is very long.
        self._feedback_frame = QFrame()
        self._feedback_frame.setObjectName("FbFrame")
        self._feedback_frame.setStyleSheet(
            f"QFrame#FbFrame{{background:{_C_CARD};border-top:2px solid {_C_CYAN};}}"
            f"QFrame#FbFrame:hover{{background:#1A2230;}}"
        )
        self._feedback_frame.setCursor(Qt.PointingHandCursor)
        self._feedback_frame.mousePressEvent = lambda ev: (
            self._next_spot() if self._feedback_frame.maximumHeight() > 0 else None
        )
        self._feedback_frame.setMaximumHeight(0)
        self._feedback_layout = QVBoxLayout(self._feedback_frame)
        self._feedback_layout.setContentsMargins(16, 10, 16, 10)
        self._feedback_layout.setSpacing(6)
        right_layout.addWidget(self._feedback_frame, 0)

        # ── Multi-modal 'next spot' keyboard shortcuts ──────────────
        from PySide6.QtGui import QShortcut, QKeySequence
        for keyseq in ("Space", "Return", "Enter", "N"):
            sc = QShortcut(QKeySequence(keyseq), self)
            sc.activated.connect(self._kbd_next_spot)

        splitter.addWidget(right_widget)
        splitter.setSizes([260, 900])
        root.addWidget(splitter, 1)

        # ── Populate ──────────────────────────────────────────────────
        self._apply_drill_filters()
        self._jump_to_pending()
        self._rebuild_spot_list()
        self.load_spot()

    # ── show event ───────────────────────────────────────────────────────
    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        if self._jump_to_pending():
            self.load_spot()

    def _jump_to_pending(self) -> bool:
        target = getattr(self.state, "pending_spot_id", None)
        if not target:
            return False
        for i, d in enumerate(self.drills):
            if d.get("id") == target:
                self.index = i
                self.state.pending_spot_id = None
                return True
        self.state.pending_spot_id = None
        return False

    # ── filters ──────────────────────────────────────────────────────────
    def _apply_drill_filters(self) -> None:
        filt = getattr(self.state, "drill_filters", None)
        if not filt:
            return
        positions = set(filt.get("positions") or [])
        starting  = filt.get("starting_spot")
        preflop   = filt.get("preflop_action")
        if positions:
            self.drills = [d for d in self.drills if d.get("position") in positions] or self.drills
        if starting and starting != "Custom":
            target = starting.lower()
            filtered = [d for d in self.drills if d.get("street", "").lower() == target]
            if filtered:
                self.drills = filtered
        if preflop and preflop != "Any":
            # New catalog uses short codes ("SRP", "3BP", "4BP", "Limp", "Squeeze")
            mapped = {
                "SRP":     ("SRP", "single raised pot"),
                "3-bet":   ("3BP", "3bet pot"),
                "4-bet":   ("4BP", "4bet pot"),
                "Squeeze": ("SQZ", "squeezed pot"),
                "Limp":    ("Limp", "limped pot"),
                "Iso":     ("Iso", "iso pot"),
            }
            tags = mapped.get(preflop, ())
            if tags:
                filtered = [d for d in self.drills
                            if any(t.lower() in (d.get("pot_type", "") or "").lower() for t in tags)]
                if filtered:
                    self.drills = filtered

    def _set_fmt_filter(self, tag: str) -> None:
        self._fmt_filter = tag
        for t, b in self._fmt_tab_buttons.items():
            b.setChecked(t == tag)
            b.setStyleSheet(_tab_btn_style(t == tag))
        self._rebuild_spot_list()

    def _set_street_filter(self, tag: str) -> None:
        self._street_filter = tag
        for t, b in self._street_btns.items():
            b.setChecked(t == tag)
            b.setStyleSheet(_tab_btn_style(t == tag, small=True))
        self._rebuild_spot_list()

    def _filtered_drills(self) -> list[dict]:
        result = self.drills
        if self._fmt_filter != "All":
            tag = self._fmt_filter
            if tag == "MTT":
                result = [d for d in result if d.get("format", "").upper() in ("MTT", "SNG", "PKO")]
            elif tag == "Cash":
                result = [d for d in result if d.get("format", "").lower() in ("cash", "heads-up")]
            elif tag == "ICM":
                result = [d for d in result if "ICM" in d.get("category", "") or "Bubble" in d.get("category", "") or d.get("icm", "off") != "off"]
            elif tag == "Explo":
                result = [d for d in result if "Explo" in d.get("category", "")]
        if self._street_filter == "Preflop":
            result = [d for d in result if d.get("street") == "preflop"]
        elif self._street_filter == "Postflop":
            result = [d for d in result if d.get("street") != "preflop"]
        return result

    # ── spot list rebuild ─────────────────────────────────────────────────
    def _rebuild_spot_list(self) -> None:
        _clear_layout(self._spot_list_layout)
        drills = self._filtered_drills()
        # Group by category
        categories: dict[str, list[dict]] = {}
        for d in drills:
            cat = d.get("category", "General Spots")
            categories.setdefault(cat, []).append(d)

        current_id = self.drills[self.index % len(self.drills)].get("id") if self.drills else ""
        for cat, spots in categories.items():
            # Category header
            hdr = QLabel(cat)
            hdr.setStyleSheet(
                f"QLabel{{background:#0C1117;color:{_C_MUTED};font-size:11px;font-weight:700;"
                "padding:6px 12px;border-bottom:1px solid #1E2733;}"
            )
            self._spot_list_layout.addWidget(hdr)
            for spot in spots:
                row = _SpotRow(spot, is_active=(spot.get("id") == current_id))
                row.clicked.connect(lambda s=spot: self._jump_to_spot(s))
                self._spot_list_layout.addWidget(row)

        self._spot_list_layout.addStretch(1)

    def _jump_to_spot(self, spot: dict) -> None:
        for i, d in enumerate(self.drills):
            if d.get("id") == spot.get("id"):
                self.index = i
                break
        self._answered = False
        self._feedback_frame.setMaximumHeight(0)
        self._rebuild_spot_list()
        self.load_spot()

    # ── core: load spot ───────────────────────────────────────────────────
    def _open_coach_deepdive(self, spot: dict, action: str, result: dict) -> None:
        """User clicked '🤖 Coach Açıkla' → navigate to AI Coach with context."""
        self.state.selected_spot = spot
        # Stash decision context so AI Coach screen can render an analysis
        self.state.coach_deepdive_context = {
            "spot":         spot,
            "hero_action":  action,
            "gto_action":   result.get("best_action", ""),
            "ev_loss":      result.get("ev_loss", 0.0),
            "is_correct":   result.get("is_correct", False),
        }
        # Pre-fill coach panel with the explanation
        try:
            self.coach_message.emit(explain_spot(spot, action))
        except Exception:
            pass
        win = self.window()
        if hasattr(win, "navigate"):
            win.navigate("AI Poker Coach")

    def showEvent(self, event) -> None:
        """Pick up an active leak signature set by My Mistakes screen and
        filter the spot list to matching position/pot_type/action."""
        super().showEvent(event)
        sig = getattr(self.state, "active_leak_signature", "") or ""
        if sig and not getattr(self, "_leak_filter_applied", False):
            self._apply_leak_filter(sig)
            self._leak_filter_applied = True

    def _apply_leak_filter(self, signature: str) -> None:
        """Smart multi-tier leak filter — tight (pos+pot+stack) → medium
        (pos+pot) → loose (pos) until at least 3-5 spots are found.

        Also enters 'leak drill mode': tracks correct streak so 3 correct
        in a row marks every matching mistake as drilled automatically.
        """
        self._active_leak_drill = signature   # track for auto-resolve
        self._leak_drill_correct = 0
        from app.db.mistakes_queue import filter_spots_by_signature, load_mistakes
        # Try to derive an average stack from saved mistakes with this signature
        mistakes = [m for m in load_mistakes() if m.leak_signature == signature]
        avg_stack = (sum(m.stack_bb for m in mistakes) / len(mistakes)
                     if mistakes else None)
        full = generate_spot_drills(120)
        filtered = filter_spots_by_signature(signature, full, avg_stack)
        if filtered:
            self.drills = filtered
            self.index = 0
            tier = ("TIGHT" if len(filtered) >= 5 else
                    "MEDIUM" if len(filtered) >= 3 else "LOOSE")
            self.coach_message.emit(
                f"🎯 My Mistakes drill modu [{tier}]: '{signature}'\n"
                f"   {len(filtered)} benzer spot yüklendi"
                + (f" (~{avg_stack:.0f}bb)" if avg_stack else "")
                + ". Hatalarını burada kapatabilirsin."
            )
            self.state.active_leak_signature = ""
            self.state.active_leak_mistakes = []
            self.load_spot()

    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self._answered = False
        self._feedback_frame.setMaximumHeight(0)
        self._refresh_source_badge(spot)

        # Context label
        stack   = spot.get("stack_bb", 40)
        fmt     = spot.get("format", "MTT")
        table   = spot.get("table", "8-max")
        pos     = spot.get("position", "BTN")
        pot_t   = spot.get("pot_type", "SRP")
        street  = spot.get("street", "preflop").title()
        name    = spot.get("name") or spot.get("title", spot.get("id", ""))
        self.spot_ctx.setText(
            f"{stack}bb {table} {fmt}  ·  {pos}  ·  {pot_t}  ·  {street}  —  {name}"
        )

        # Render hero cards (visible)
        _clear_layout(self._hero_cards_row)
        hero_cards_str = spot.get("hero_cards", "")
        # Format: 'AsKh' → ['As', 'Kh']  (2-char tokens)
        if hero_cards_str:
            tokens: list[str] = []
            i = 0
            while i < len(hero_cards_str) - 1:
                if hero_cards_str[i].isspace():
                    i += 1; continue
                tokens.append(hero_cards_str[i:i+2])
                i += 2
            for tok in tokens[:2]:
                self._hero_cards_row.addWidget(CardView(tok))
        # If no cards in spot, show face-down placeholders
        if self._hero_cards_row.count() == 0:
            for _ in range(2):
                self._hero_cards_row.addWidget(CardView("", face_down=True))

        # Update oval table — full poker context (stacks, bets, chips, hero cards, pot)
        self.oval.populate_from_spot(spot)
        comm: list[str] = []
        # Use the REAL board from the spot when available — falls back to
        # face-down placeholders only when the spot didn't supply cards.
        board_str = (spot.get("board") or "").strip()
        street    = (spot.get("street") or "preflop").lower()
        expected  = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}.get(street, 0)
        comm: list[str] = []
        if board_str:
            i = 0
            while i < len(board_str) - 1 and len(comm) < expected:
                if board_str[i].isspace():
                    i += 1
                    continue
                comm.append(board_str[i:i+2])
                i += 2
        # Pad with face-downs if the spot was under-specified
        while len(comm) < expected:
            comm.append("W")
        self.oval.set_community_cards(comm)
        spr = round(stack / max(spot.get("pot_bb", 1), 1), 1)
        po  = round(100 * 0.33 / (1 + 2 * 0.33), 1)
        self.oval.set_spr_po(spr=spr, po=po)

        # Update position chips
        all_pos = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
        for p, chip in self._pos_chips.items():
            if p == pos:
                chip.update_action("Action", is_hero=True)
            elif p in ("BTN",) and pos != "BTN":
                chip.update_action(f"{stack:.0f}bb")
            else:
                chip.update_action("Fold")

        # Action buttons (before answer: no frequencies)
        _clear_layout(self._action_layout)
        self._current_action_buttons = []
        for action in spot["options"]:
            label = self._action_display_with_sizing(action, spot)
            btn = _GtoActionButton(label, action)
            btn.clicked.connect(lambda _, a=action: self.answer(a))
            self._action_layout.addWidget(btn)
            self._current_action_buttons.append(btn)
        # Wire universal 1/2/3/4 keyboard shortcuts (pro player muscle memory)
        try:
            from app.ui.components.action_buttons import attach_action_shortcuts
            attach_action_shortcuts(self, self._current_action_buttons)
        except Exception:
            pass

    def _action_display_with_sizing(self, action: str, spot: dict) -> str:
        """Like _action_display but respects user-entered sizing override."""
        custom = (self._sizing_input.text() or "").strip() if hasattr(self, "_sizing_input") else ""
        a = action.lower()
        if not custom or a in ("fold", "check", "call"):
            return _action_display(action, spot)
        pot = float(spot.get("pot_bb", 10))
        stk = float(spot.get("stack_bb", 40))
        # Parse custom sizing
        try:
            if custom.endswith("%"):
                pct = float(custom[:-1]) / 100.0
                size = pot * pct
            elif custom.lower().endswith("x"):
                multiplier = float(custom[:-1])
                size = pot * multiplier
            elif custom.lower().endswith("bb"):
                size = float(custom[:-2])
            else:
                size = float(custom)
        except Exception:
            return _action_display(action, spot)
        size = min(size, stk)
        verb = "ALL-IN" if size >= stk - 0.5 else ("RAISE" if "raise" in a or "3bet" in a or "4bet" in a else "BET")
        return f"{verb} {size:.1f}"

    def _refresh_source_badge(self, spot: dict) -> None:
        lib = get_solver_library()
        sid = str(spot.get("id", ""))
        if lib.has(sid):
            result = lib.get(sid)
            label = (result.source_confidence if result else "Imported") or "Imported"
            self.source_badge.setText(f"✓ {label}")
            self.source_badge.setStyleSheet(
                "QLabel{background:#0E2A1E;color:#10B981;font-weight:800;padding:4px 10px;"
                "border-radius:8px;font-size:11px;}"
            )
        else:
            self.source_badge.setText("⚙ Mock solver")
            self.source_badge.setStyleSheet(
                "QLabel{background:#5C1F22;color:#F87171;font-weight:800;padding:4px 10px;"
                "border-radius:8px;font-size:11px;}"
            )

    # ── answer + feedback ─────────────────────────────────────────────────
    def answer(self, action: str) -> None:
        if self._answered:
            return
        self._answered = True
        spot   = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        score  = score_decision(result["ev_loss"], result["solver_frequency"])

        self.state.record_decision(
            result["is_correct"], result["ev_loss"],
            f"{spot['id']} {action}: -{result['ev_loss']:.2f}bb",
        )

        # Adaptive engine
        engine = self.state.adaptive_engine()
        engine.record_attempt(
            spot_id=spot["id"],
            correct=result["is_correct"],
            ev_loss=result["ev_loss"],
            tags=(spot.get("street", ""), spot.get("position", ""), spot.get("pot_type", "")),
        )
        try:
            engine.save_to_db()
        except Exception:
            pass

        # ── Leak-drill mode: auto-resolve after 3 correct in a row ────
        active_sig = getattr(self, "_active_leak_drill", "") or ""
        if active_sig:
            if result["is_correct"]:
                self._leak_drill_correct = getattr(self, "_leak_drill_correct", 0) + 1
                if self._leak_drill_correct >= 3:
                    try:
                        from app.db.mistakes_queue import mark_signature_drilled
                        n = mark_signature_drilled(active_sig)
                        if n:
                            # Toast notification — visible + non-blocking
                            try:
                                from app.ui.components.toast import Toast
                                Toast.show_success(
                                    self.window(),
                                    f"🎉 Leak çözüldü! '{active_sig}' — {n} hata kapatıldı",
                                    duration_ms=5000,
                                )
                            except Exception:
                                pass
                            self.coach_message.emit(
                                f"🎉 Leak çözüldü! '{active_sig}' işaretlendi "
                                f"({n} hata kapatıldı). Welcome'da 'Açık Leak' "
                                f"sayısı düşecek."
                            )
                    except Exception:
                        pass
                    # Exit leak drill mode after resolving
                    self._active_leak_drill = ""
                    self._leak_drill_correct = 0
            else:
                # Wrong answer during leak drill → reset streak
                self._leak_drill_correct = 0

        # ── Persist wrong decisions to the global My Mistakes queue ──
        if not result["is_correct"]:
            try:
                from datetime import datetime
                from app.db.mistakes_queue import (
                    MistakeEntry as MqEntry, add_mistake, new_id as new_mistake_id,
                )
                best_act = result.get("best_action", "")
                add_mistake(MqEntry(
                    id           = new_mistake_id(),
                    logged_at    = datetime.now().isoformat(timespec="seconds"),
                    context      = "spot_trainer",
                    spot_id      = spot.get("id", ""),
                    position     = (spot.get("position") or "").upper(),
                    stack_bb     = float(spot.get("stack_bb", 40)),
                    pot_type     = (spot.get("pot_type") or "SRP").upper(),
                    hero_cards   = spot.get("hero_cards", ""),
                    hero_action  = action.lower(),
                    gto_action   = best_act.lower(),
                    ev_loss      = round(float(result["ev_loss"]), 2),
                    why          = self._build_why_explanation(spot, action, result)[:240],
                ))
                try:
                    from app.ui.components.toast import Toast
                    Toast.show_warning(
                        self.window(),
                        f"❌ Hata kaydedildi  ·  −{result['ev_loss']:.2f}bb  ·  GTO: {best_act.upper()}"
                    )
                except Exception:
                    pass
            except Exception:
                pass

        # ── Show GTO frequencies on buttons ──────────────────────────
        solver_actions = result["solver"]["actions"]
        freq_map = {a["action"]: a["frequency"] for a in solver_actions}
        for btn in self._current_action_buttons:
            freq = freq_map.get(btn._action, 0.0)
            btn.set_frequency(freq)
            # Disable further clicks (keep visual)
            btn.setEnabled(False)

        # ── Feedback panel ────────────────────────────────────────────
        # Cap to ~260px so the panel never pushes content off-screen.
        # WHY explanation can scroll inside the panel if needed.
        self._feedback_frame.setMaximumHeight(260)
        _clear_layout(self._feedback_layout)

        is_correct = result["is_correct"]
        ev_loss    = result["ev_loss"]
        best_act   = result["best_action"]
        hero_ev    = result["hero_ev"]
        best_ev    = result["best_ev"]

        # ── Streak tracking ──────────────────────────────────────────
        if is_correct:
            self._streak = getattr(self, "_streak", 0) + 1
        else:
            self._streak = 0
        self._best_streak = max(getattr(self, "_best_streak", 0), self._streak)

        # Verdict row — Türkçe ve learning-friendly
        verdict_row = QHBoxLayout()
        if is_correct:
            icon = QLabel("✅")
            icon.setStyleSheet("font-size:22px;")
            streak_text = (f"  🔥 {self._streak} doğru üst üste!"
                           if self._streak >= 3 else "")
            msg = QLabel(
                f"Harika — Doğru karar!  EV kayıp: {ev_loss:.2f}bb  ·  "
                f"{skill_label(score)}{streak_text}"
            )
            msg.setStyleSheet(f"color:{_C_GREEN};font-size:14px;font-weight:800;")
        else:
            icon = QLabel("❌")
            icon.setStyleSheet("font-size:22px;")
            msg = QLabel(
                f"Daha iyisi var — Sen {action.upper()} dedin, GTO {best_act.upper()}  "
                f"·  EV kayıp: {ev_loss:.2f}bb"
            )
            msg.setStyleSheet(f"color:{_C_RED};font-size:14px;font-weight:800;")
        verdict_row.addWidget(icon)
        verdict_row.addWidget(msg, 1)
        next_btn = QPushButton("Next Spot →")
        next_btn.setFixedHeight(38)
        next_btn.setStyleSheet(
            f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:8px;"
            "font-weight:800;font-size:13px;padding:4px 18px;}"
            f"QPushButton:hover{{background:#06B6D4;}}"
        )
        next_btn.clicked.connect(self._next_spot)

        # Deep-dive: open AI Coach with this spot loaded for detailed analysis
        deep_btn = QPushButton("🤖 Coach Açıkla")
        deep_btn.setFixedHeight(38)
        deep_btn.setStyleSheet(
            f"QPushButton{{background:#0F141C;color:{_C_TEXT};"
            f"border:1px solid {_C_BORDER};border-radius:8px;"
            f"font-weight:700;font-size:12px;padding:4px 14px;}}"
            f"QPushButton:hover{{border-color:#A78BFA;color:#A78BFA;}}"
        )
        deep_btn.clicked.connect(lambda: self._open_coach_deepdive(spot, action, result))
        next_btn.setToolTip("Klavye: Space / Enter / N — veya panele tıkla")
        next_btn.setCursor(Qt.PointingHandCursor)
        verdict_row.addWidget(deep_btn)
        verdict_row.addWidget(next_btn)
        self._feedback_layout.addLayout(verdict_row)

        # Multi-modal hint
        hint = QLabel("⌨  Space / Enter / N  ·  veya panele tıkla  ·  veya butona bas")
        hint.setStyleSheet(
            f"color:{_C_MUTED};font-size:10px;font-style:italic;padding:2px 4px;"
        )
        hint.setAlignment(Qt.AlignCenter)
        self._feedback_layout.addWidget(hint)

        # ── WHY explanation (only when wrong) ─────────────────────────
        if not is_correct:
            why = self._build_why_explanation(spot, action, result)
            why_label = QLabel(why)
            why_label.setWordWrap(True)
            why_label.setStyleSheet(
                f"QLabel{{background:#0C1117;color:{_C_TEXT};font-size:13px;"
                "padding:10px 14px;border-radius:8px;border:1px solid #1E2733;"
                "}"
            )
            self._feedback_layout.addWidget(why_label)

        # GTO frequency summary
        freq_row = QHBoxLayout()
        for a_dict in solver_actions:
            freq = a_dict["frequency"]
            ev   = a_dict["ev"]
            act  = a_dict["action"]
            pct  = f"{freq * 100:.1f}%"
            bg, border, fg = _action_palette(act)
            pill = QLabel(f"{_action_display(act, spot)}\n{pct} | EV {ev:+.2f}bb")
            pill.setAlignment(Qt.AlignCenter)
            pill.setStyleSheet(
                f"QLabel{{background:{bg};border:2px solid {border};"
                f"color:{fg};border-radius:8px;padding:6px 12px;font-size:12px;"
                "font-weight:700;}"
            )
            freq_row.addWidget(pill)
        self._feedback_layout.addLayout(freq_row)

        self.coach_message.emit(explain_spot(spot, action))

        # Queue next
        self._advance_queue(spot)

    def _build_why_explanation(self, spot: dict, hero_action: str, result: dict) -> str:
        best   = result["best_action"]
        ev_loss = result["ev_loss"]
        hero_ev = result["hero_ev"]
        best_ev = result["best_ev"]
        best_freq = result["best_frequency"]
        street  = spot.get("street", "preflop")
        pos     = spot.get("position", "BTN")
        pot_t   = spot.get("pot_type", "SRP")
        texture = spot.get("board_texture", "dynamic")
        stack   = spot.get("stack_bb", 40)
        r_adv   = spot.get("range_advantage", "neutral")
        nut_adv = spot.get("nut_advantage", "neutral")

        lines = [f"💡  GTO Analysis — Why '{best}' ({best_freq*100:.0f}%) is better:"]

        # Action class mismatch explanation
        hero_a = hero_action.lower()
        best_a = best.lower()

        if "fold" in hero_a and "fold" not in best_a:
            lines.append(f"• Overfold: You folded in a spot where GTO calls/raises {best_freq*100:.0f}% of the time.")
            lines.append(f"  At {stack}bb effective, your range has sufficient equity to continue here.")
        elif "call" in hero_a and ("bet" in best_a or "raise" in best_a or "jam" in best_a):
            lines.append(f"• Missed value / too passive: GTO prefers aggression ({best}) {best_freq*100:.0f}% here.")
            lines.append(f"  Your hand is strong enough to build the pot and deny equity.")
        elif ("bet" in hero_a or "raise" in hero_a) and ("check" in best_a or "call" in best_a):
            lines.append(f"• Over-bluffing / thin value: GTO prefers {best} {best_freq*100:.0f}% on this texture.")
            lines.append(f"  On a {texture} board your range advantage doesn't justify this aggression.")
        elif "check" in hero_a and ("bet" in best_a or "raise" in best_a):
            lines.append(f"• Under-betting: GTO wants to be betting {best_freq*100:.0f}% here on {texture} texture.")
            lines.append(f"  Checking allows villain to realise equity for free.")
        else:
            lines.append(f"• Action mismatch: GTO prefers '{best}' {best_freq*100:.0f}% of the time.")

        # EV context
        lines.append(f"• EV difference: Your action ({hero_action}) = {hero_ev:+.2f}bb vs GTO ({best}) = {best_ev:+.2f}bb → {ev_loss:.2f}bb EV loss.")

        # Positional / range context
        if street != "preflop":
            lines.append(f"• Board: {texture}  |  Range advantage: {r_adv}  |  Nut advantage: {nut_adv}")
        lines.append(f"• Position: {pos}  ·  Pot type: {pot_t}  ·  Stack: {stack}bb")

        if ev_loss > 1.0:
            lines.append("⚠️  This is a high-EV-loss spot — add to your drill queue and revisit regularly.")
        elif ev_loss > 0.3:
            lines.append("📌  Moderate EV loss — worth reviewing the GTO frequency breakdown above.")

        return "\n".join(lines)

    def _advance_queue(self, spot: dict) -> None:
        next_id: str | None = None
        queue = getattr(self.state, "pending_spot_queue", None) or []
        if queue and queue[0] == spot["id"]:
            queue.pop(0)
        if queue:
            next_id = queue[0]
            self.state.pending_spot_id = next_id
        else:
            candidates = [d["id"] for d in self.drills]
            engine = self.state.adaptive_engine()
            next_id = engine.next_drill(candidates, exclude=[spot["id"]])
        if next_id:
            for i, d in enumerate(self.drills):
                if d["id"] == next_id:
                    self.index = i
                    break
            else:
                self.index += 1
        else:
            self.index += 1

    def _kbd_next_spot(self) -> None:
        """Keyboard shortcut → next spot (only when feedback panel visible)."""
        if self._feedback_frame.maximumHeight() > 0:
            self._next_spot()

    def _next_spot(self) -> None:
        self._rebuild_spot_list()
        self.load_spot()

    def _reroll(self) -> None:
        self.seed = random.randint(1, 99)
        self._rng = random.Random(self.seed)
        self.oval.set_seed(self.seed)
        self.index = self._rng.randint(0, len(self.drills) - 1)
        self._answered = False
        self._feedback_frame.setMaximumHeight(0)
        self._rebuild_spot_list()
        self.load_spot()
        self.coach_message.emit(f"Seed {self.seed}: yeni rastgele spot.")


# ── Study Library redesign ─────────────────────────────────────────────────

class _SpotRow(QFrame):
    """Single clickable row in the spot list."""
    clicked = Signal()

    def __init__(self, spot: dict, is_active: bool = False):
        super().__init__()
        self._spot = spot
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 0, 8, 0)
        h.setSpacing(6)

        name = spot.get("name") or spot.get("title", spot.get("id", ""))
        tag  = spot.get("format_tag", spot.get("format", "MTT"))

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{'#E5E7EB' if is_active else '#C9D1DC'};font-size:13px;"
            f"font-weight:{'700' if is_active else '400'};"
        )
        h.addWidget(name_lbl, 1)

        played = spot.get("hands_played", 0)
        ev     = spot.get("ev_delta", 0.0)

        if played:
            p_lbl = QLabel(str(played))
            p_lbl.setStyleSheet(f"color:{_C_MUTED};font-size:12px;min-width:30px;")
            p_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(p_lbl)

            color = _C_GREEN if ev >= 0 else _C_RED
            sign  = "+" if ev >= 0 else ""
            ev_lbl = QLabel(f"{sign}{ev:.1f}")
            ev_lbl.setStyleSheet(f"color:{color};font-size:12px;font-weight:700;min-width:50px;")
            ev_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(ev_lbl)
        else:
            dash = QLabel("—")
            dash.setStyleSheet(f"color:{_C_MUTED};font-size:12px;min-width:80px;")
            dash.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(dash)

        # Active indicator
        if is_active:
            self.setStyleSheet(
                f"QFrame{{background:#1B2D4A;border-left:3px solid {_C_CYAN};}}"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{background:transparent;border-left:3px solid transparent;}}"
                f"QFrame:hover{{background:#131A24;border-left:3px solid {_C_BORDER};}}"
            )

    def mousePressEvent(self, event):  # type: ignore[override]
        self.clicked.emit()
        super().mousePressEvent(event)


class _VSep(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(1)
        self.setFixedHeight(36)
        self.setStyleSheet(f"background:{_C_BORDER};")


# ── helpers ───────────────────────────────────────────────────────────────

def _tab_btn_style(active: bool, small: bool = False) -> str:
    h = "26px" if small else "28px"
    px = "8px 12px" if small else "4px 14px"
    fs = "11px" if small else "12px"
    if active:
        return (
            f"QPushButton{{background:{_C_CYAN};color:#000;border-radius:6px;"
            f"font-weight:700;font-size:{fs};padding:{px};border:none;height:{h};}}"
        )
    return (
        f"QPushButton{{background:{_C_CARD};color:{_C_MUTED};border-radius:6px;"
        f"font-weight:500;font-size:{fs};padding:{px};border:1px solid {_C_BORDER};height:{h};}}"
        f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_TEXT};}}"
    )


def _spread_actions_for_spot(spot: dict, rng: random.Random) -> dict[str, list[str]]:
    """Derive per-position action chips from the spot's metadata.

    Reads name/action_history to figure out preflop story:
      • "RFI" / open spots          → all earlier positions fold, hero raises
      • "vs BTN" / "vs LJ" defense  → that position raised, intermediate fold,
                                      hero (BB/SB/BTN) faces decision
      • "3-bet" defense             → opener raises, 3-bettor 3bets, hero decides
    """
    order = ["UTG", "UTG1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
    hero_pos = spot.get("position") or "BTN"
    if hero_pos == "UTG+1":
        hero_pos = "UTG1"
    if hero_pos not in order:
        hero_pos = "BTN"

    name    = (spot.get("name", "") + " " + spot.get("action_history", "") + " " + spot.get("title", "")).upper()
    street  = (spot.get("street", "preflop") or "preflop").lower()
    pot_t   = (spot.get("pot_type", "") or "").upper()
    layout: dict[str, list[str]] = {}

    # Detect "vs X" pattern
    vs_pos = None
    for v in ("UTG1", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"):
        if f"VS {v}" in name or f"VS {v} " in name:
            vs_pos = v; break

    # ── Preflop dynamics ──────────────────────────────────────────────
    hero_idx = order.index(hero_pos)

    if "3-BET" in name or pot_t == "3BP":
        # Opener (some earlier pos) raised, hero 3bet target now defends/4bets
        opener = vs_pos or order[max(0, hero_idx - 2)]
        if opener not in order: opener = "BTN"
        for p in order:
            if p == opener:
                layout[p] = ["R 2.3"]
            elif p == hero_pos:
                layout[p] = ["3B 8"]
            elif order.index(p) < order.index(opener):
                layout[p] = ["F"]
            else:
                # Folded between opener and 3-bettor
                if order.index(p) < hero_idx and p != opener:
                    layout[p] = ["F"]
    elif vs_pos and hero_pos in ("BB", "SB"):
        # Defense spot: villain raised, hero is in blind
        for p in order:
            if p == vs_pos:
                layout[p] = ["R 2.3"]
            elif p == hero_pos:
                pass  # Hero acts now — no chip yet
            elif order.index(p) < order.index(vs_pos):
                layout[p] = ["F"]
            else:
                # Positions between villain and blinds fold
                if p not in ("BB", "SB"):
                    layout[p] = ["F"]
        # SB folds if hero is BB and vs_pos != SB
        if hero_pos == "BB" and vs_pos != "SB":
            layout.setdefault("SB", ["F"])
    elif street == "preflop":
        # Open spot: hero RFI, all earlier positions fold
        for p in order:
            if p == hero_pos:
                continue
            if order.index(p) < hero_idx:
                layout[p] = ["F"]
        # Hero raises
        layout[hero_pos] = ["R 2.3"]
    else:
        # Postflop: just mark dealer + hero
        for p in order:
            if p != hero_pos:
                layout[p] = ["F"] if rng.random() < 0.7 else []
        layout[hero_pos] = ["C"]

    return {k: v for k, v in layout.items() if v}


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        cl = item.layout()
        if w:
            w.deleteLater()
        if cl:
            _clear_layout(cl)
