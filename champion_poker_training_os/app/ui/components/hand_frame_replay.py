"""Hand Frame-by-Frame Replay — adımlı animasyonlu el geçmişi.

Action log'daki her aksiyona göre OvalTable state'i kuruyor, kullanıcı:
  ◀◀  ilk adım     (mouse veya Home tuşu)
  ◀   önceki       (mouse veya Sol ok)
  ▶   sonraki      (mouse, Sağ ok, Space, Enter, N)
  ▶▶  son adım     (mouse veya End tuşu)
  ⏯   otomatik oynat (1.5sn aralıkla)

Her frame'de OvalTable:
  • İlgili street'in board kartları gözükür (preflop→flop→turn→river)
  • Sıradaki aktör halo ile vurgulanır
  • Aksiyon chip'i o seat'te belirir (R / C / X / B / F)
  • Pot büyür
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.ui.components.oval_table import OvalTable


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


def _ctrl_btn(label: str, tooltip: str = "") -> QPushButton:
    b = QPushButton(label)
    b.setFixedSize(48, 38)
    b.setCursor(Qt.PointingHandCursor)
    if tooltip:
        b.setToolTip(tooltip)
    b.setStyleSheet(
        f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};"
        f"border:1px solid {_C_BORDER};border-radius:0;font-size:14px;font-weight:700;}}"
        f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        f"QPushButton:disabled{{color:#374151;border-color:#1E2733;}}"
    )
    return b


def _board_for_street(board_str: str, street: str) -> list[str]:
    """Slice the full board string based on which street we're rendering."""
    cards = [board_str[i:i+2] for i in range(0, len(board_str) - 1, 2)]
    st = street.lower()
    if st == "preflop": return []
    if st == "flop":    return cards[:3]
    if st == "turn":    return cards[:4]
    if st == "river":   return cards[:5]
    return cards


class HandFrameReplayDialog(QDialog):
    """Animasyonlu el replay dialogu — her aksiyon bir frame."""

    def __init__(self, parent: Optional[QWidget], hand_record: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Replay  ·  El #{hand_record.get('hand_no', '?')}")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"QDialog{{background:{_C_BG};}}")
        self._hand = hand_record
        self._actions = list(hand_record.get("actions") or [])
        self._idx = -1   # -1 = initial state (no actions yet)
        self._auto_playing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Header ─────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(
            f"🎬  El #{hand_record.get('hand_no', '?')}  ·  "
            f"L{hand_record.get('level', 1)} {hand_record.get('blinds', '')}  ·  "
            f"Pos: {hand_record.get('hero_pos', '?')}  ·  "
            f"Elin: {hand_record.get('hero_cards', '????')}"
        )
        title.setStyleSheet(f"color:{_C_TEXT};font-size:15px;font-weight:800;")
        hdr.addWidget(title)
        hdr.addStretch(1)
        close = QPushButton("Kapat (Esc)")
        close.setFixedHeight(34)
        close.setStyleSheet(
            f"QPushButton{{background:{_C_PANEL};color:{_C_TEXT};border:1px solid {_C_BORDER};"
            f"border-radius:0;padding:0 16px;}}"
            f"QPushButton:hover{{border-color:{_C_CYAN};color:{_C_CYAN};}}"
        )
        close.clicked.connect(self.accept)
        hdr.addWidget(close)
        root.addLayout(hdr)

        # ── Oval table ─────────────────────────────────────────────
        self._oval = OvalTable()
        self._oval.setMinimumHeight(440)
        root.addWidget(self._oval, 1)

        # ── Frame info ─────────────────────────────────────────────
        self._frame_lbl = QLabel("Başlangıç durumu")
        self._frame_lbl.setStyleSheet(
            f"color:{_C_AMBER};font-size:13px;font-weight:700;padding:4px;"
        )
        self._frame_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self._frame_lbl)

        # ── Controls ───────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.addStretch(1)
        self._btn_first = _ctrl_btn("◀◀", "İlk frame (Home)")
        self._btn_prev  = _ctrl_btn("◀",  "Önceki (Sol ok)")
        self._btn_play  = _ctrl_btn("▶",  "Otomatik oynat (P)")
        self._btn_next  = _ctrl_btn("▶",  "Sonraki (Sağ ok / Space)")
        self._btn_last  = _ctrl_btn("▶▶", "Son frame (End)")
        # Disambiguate the icons
        self._btn_play.setText("⏯")
        self._btn_first.clicked.connect(self._go_first)
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_play.clicked.connect(self._toggle_play)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_last.clicked.connect(self._go_last)
        for b in (self._btn_first, self._btn_prev, self._btn_play,
                  self._btn_next, self._btn_last):
            controls.addWidget(b)
        controls.addStretch(1)
        root.addLayout(controls)

        # Progress label
        self._progress = QLabel()
        self._progress.setStyleSheet(f"color:{_C_MUTED};font-size:11px;")
        self._progress.setAlignment(Qt.AlignCenter)
        root.addWidget(self._progress)

        # ── Auto-play timer ────────────────────────────────────────
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(1500)
        self._auto_timer.timeout.connect(self._auto_step)

        # ── Keyboard shortcuts ─────────────────────────────────────
        for keyseq, fn in [
            ("Right", self._go_next), ("Space", self._go_next),
            ("Return", self._go_next), ("Enter", self._go_next), ("N", self._go_next),
            ("Left", self._go_prev),
            ("Home", self._go_first),
            ("End", self._go_last),
            ("P", self._toggle_play),
        ]:
            sc = QShortcut(QKeySequence(keyseq), self)
            sc.activated.connect(fn)

        # Initial render
        self._render_frame()

    # ── Navigation ────────────────────────────────────────────────

    def _go_first(self) -> None: self._idx = -1; self._render_frame()
    def _go_prev(self) -> None:  self._idx = max(-1, self._idx - 1); self._render_frame()
    def _go_next(self) -> None:
        if self._idx < len(self._actions) - 1:
            self._idx += 1
            self._render_frame()
        elif self._auto_playing:
            self._toggle_play()   # stop at end
    def _go_last(self) -> None:  self._idx = len(self._actions) - 1; self._render_frame()

    def _toggle_play(self) -> None:
        self._auto_playing = not self._auto_playing
        if self._auto_playing:
            self._auto_timer.start()
            self._btn_play.setText("⏸")
        else:
            self._auto_timer.stop()
            self._btn_play.setText("⏯")

    def _auto_step(self) -> None:
        if self._idx >= len(self._actions) - 1:
            self._toggle_play()
            return
        self._go_next()

    # ── Rendering ─────────────────────────────────────────────────

    def _render_frame(self) -> None:
        # Determine current street from action history up to idx
        current_action = self._actions[self._idx] if self._idx >= 0 else None
        street = (current_action or {}).get("street", "PREFLOP").upper()

        # Synthesise a spot for populate_from_spot
        spot = {
            "position":   self._hand.get("hero_pos", "BTN"),
            "stack_bb":   self._hand.get("hero_stack_in", 2000) / 20,  # rough bb
            "pot_bb":     self._hand.get("pot_final", 0) / 20,
            "street":     street.lower(),
            "hero_cards": self._hand.get("hero_cards", ""),
            "board":      "",   # we set community separately below
            "name":       "",
            "pot_type":   "SRP",
            "action_history": "",
        }
        self._oval.populate_from_spot(spot)
        # Set board for the street
        board = _board_for_street(self._hand.get("board", ""), street)
        self._oval.set_community_cards(board)

        # Apply all actions up to and including self._idx
        for i, a in enumerate(self._actions):
            if i > self._idx:
                break
            seat = a.get("pos", "")
            verb = a.get("action", "").lower()
            amt  = a.get("amount", 0)
            if seat in self._oval.seats:
                s = self._oval.seats[seat]
                if verb == "fold":
                    s.folded = True
                    s.actions = ["F"]
                    s.current_bet = 0
                elif verb in ("check",):
                    s.actions = ["X"]
                elif verb in ("call",):
                    s.actions = [f"C {amt:.0f}"] if amt else ["C"]
                    s.current_bet = float(amt)
                elif verb in ("bet", "raise"):
                    code = "R" if verb == "raise" else "B"
                    s.actions = [f"{code} {amt:.0f}"]
                    s.current_bet = float(amt)
                elif "jam" in verb or "all" in verb:
                    s.actions = ["AI"]
                    s.current_bet = float(amt)

        # Highlight the seat that just acted
        if current_action is not None:
            actor = current_action.get("pos", "")
            for p, s in self._oval.seats.items():
                s.selected = (p == actor)
        self._oval.update()

        # Frame label
        if current_action is None:
            self._frame_lbl.setText("⏱  Başlangıç — el dağıtıldı, henüz aksiyon yok")
        else:
            verb = current_action.get("action", "?").upper()
            pos  = current_action.get("pos", "?")
            name = current_action.get("name", "")
            amt  = current_action.get("amount", 0)
            amt_str = f" {amt:.0f}" if amt else ""
            st   = current_action.get("street", "?").title()
            self._frame_lbl.setText(
                f"▸ {st}  ·  {pos} ({name}) → {verb}{amt_str}"
            )

        # Progress
        total = len(self._actions)
        cur   = self._idx + 1
        self._progress.setText(f"Frame {cur} / {total}")

        # Button enable/disable
        self._btn_first.setEnabled(self._idx > -1)
        self._btn_prev.setEnabled(self._idx > -1)
        self._btn_next.setEnabled(self._idx < total - 1)
        self._btn_last.setEnabled(self._idx < total - 1)

    def keyPressEvent(self, ev: QKeyEvent) -> None:
        if ev.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev) -> None:
        # Stop auto-play timer before closing
        if self._auto_timer.isActive():
            self._auto_timer.stop()
        super().closeEvent(ev)
