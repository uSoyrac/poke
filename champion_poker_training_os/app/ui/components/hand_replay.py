"""Street-by-street hand replay component.

Takes an `imported_hand` dict (or any dict with hero_cards, board, position,
pot_bb, hero_profit_bb, and per-street action codes), and offers playback
controls (← Prev / Next →, jump to street). Surfaces an oval table preview
with action chips per position, the running pot, current street, and an
AI Coach panel with per-street commentary.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.ui.components.action_chip import ActionSequence, parse_action_string
from app.ui.components.mini_card import MiniCard, MiniCardRow
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, DEFAULT_POSITIONS_6, OvalTable


STREETS = ["preflop", "flop", "turn", "river"]
STREET_LABELS = {"preflop": "Preflop", "flop": "Flop", "turn": "Turn", "river": "River"}


@dataclass
class StreetSnapshot:
    name: str
    actions_by_position: dict[str, list[str]]
    community: list[str]
    pot_bb: float
    commentary: str


def _board_chunks(board: str) -> list[str]:
    """'Ah7c2d9s4c' -> ['Ah','7c','2d','9s','4c']. Strips suits if absent."""
    if not board:
        return []
    if any(c in "hdscHDSC" for c in board):
        # 2-char card pairs
        return [board[i:i + 2] for i in range(0, len(board) - len(board) % 2, 2)]
    # Just ranks like 'Q875T2' — assign synthetic suits per position
    suits = ["h", "d", "s", "c", "h"]
    return [r + suits[i % len(suits)] for i, r in enumerate(board)]


def _explode_actions(codes: str, hero_pos: str, villain_pool: list[str]) -> dict[str, list[str]]:
    """Distribute compact action codes onto hero + a deterministic villain.

    The parsed `*_actions` strings concatenate every player's action that street,
    in order. Without per-action attribution we can't perfectly reconstruct who
    acted, but we can still hand-render to hero + a villain alternation that
    matches the screenshot UX (hero in foreground, villain reacting).
    """
    if not codes:
        return {}
    tokens = parse_action_string(codes)
    villain = villain_pool[0] if villain_pool else "BB"
    out: dict[str, list[str]] = {hero_pos: [], villain: []}
    # Alternate: villain first if hero is in position; hero first OOP.
    hero_first = hero_pos in {"BTN", "CO", "HJ", "LJ"}
    for i, t in enumerate(tokens):
        owner = (hero_pos if (i % 2 == 0) == hero_first else villain)
        out[owner].append(t)
    return {p: a for p, a in out.items() if a}


def _street_commentary(street: str, hand: dict) -> str:
    """Generate quick coach commentary for a street based on the hand context."""
    pos = hand.get("hero_position", "?")
    cards = hand.get("hero_cards", "??")
    pot_type = hand.get("pot_type", "?")
    code = hand.get(f"{street}_actions", "")
    if not code and street != "preflop":
        return f"{STREET_LABELS[street]}: Bu street'e gelinmedi."
    if street == "preflop":
        return (
            f"Preflop: {pos} pozisyonunda {cards} ile {pot_type} bir pot oluşturuldu. "
            f"Aksiyon dizisi: {code or '—'}. Range advantage'ı pozisyonun lehine mi sorgula."
        )
    intro = {
        "flop": "Flop: range vs range eşitsizliği belirleyici. Hero pozisyonun, board doku ve nut adv'ı düşün.",
        "turn": "Turn: villain range'i daralttı; barreling dengesi (value/bluff) kritik.",
        "river": "River: blocker'lar ve MDF burada işler. Bluff catcher mı yoksa thin value mı?",
    }
    return f"{STREET_LABELS[street]}: {intro.get(street, '')} Aksiyon dizisi: {code}."


class StreetTab(QPushButton):
    """A pill-style toggle in the street strip (Preflop / Flop / Turn / River)."""

    def __init__(self, label: str, enabled_actions: bool):
        super().__init__(label)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._enabled_actions = enabled_actions
        self._refresh()
        self.toggled.connect(lambda _: self._refresh())

    def _refresh(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                "QPushButton { background: #1B2A3D; border: 1px solid #22D3EE; "
                "border-radius:0; padding: 6px 16px; color: #22D3EE; font-weight: 800; }"
            )
        else:
            base_color = "#E5E7EB" if self._enabled_actions else "#4B5563"
            self.setStyleSheet(
                f"QPushButton {{ background: #131A24; border: 1px solid #1E2733; "
                f"border-radius:0; padding: 6px 16px; color: {base_color}; font-weight: 600; }}"
                "QPushButton:hover { color: #22D3EE; border-color: #2A3647; }"
            )


class HandReplay(QWidget):
    """Reusable hand replay widget. Emits coach_message for each street snapshot."""

    coach_message = Signal(str)
    practice_requested = Signal(dict)  # emits the hand for "Practice similar" wiring

    def __init__(self):
        super().__init__()
        self.hand: dict | None = None
        self.snapshots: list[StreetSnapshot] = []
        self.current = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Header summary
        self.header_card = QFrame()
        self.header_card.setObjectName("Card")
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(14, 10, 14, 10)
        self.title_label = QLabel("Select a hand to replay")
        self.title_label.setObjectName("SectionTitle")
        h_layout.addWidget(self.title_label, 1)
        self.profit_label = QLabel("")
        self.profit_label.setStyleSheet("font-weight: 800; font-size: 16px;")
        h_layout.addWidget(self.profit_label)
        layout.addWidget(self.header_card)

        # Street tabs
        self.street_row = QHBoxLayout()
        self.street_row.setSpacing(6)
        self.street_buttons: list[StreetTab] = []
        self.street_row.addStretch(1)
        for s in STREETS:
            btn = StreetTab(STREET_LABELS[s], False)
            btn.clicked.connect(lambda _checked=False, name=s: self.jump_to(name))
            self.street_row.addWidget(btn)
            self.street_buttons.append(btn)
        self.street_row.addStretch(1)
        layout.addLayout(self.street_row)

        # Oval table preview
        self.table = OvalTable(positions=DEFAULT_POSITIONS_6, selectable=False)
        self.table.set_dealer("BTN")
        layout.addWidget(self.table, 1)

        # Hero hole cards row
        cards_row = QHBoxLayout()
        cards_row.addStretch(1)
        self.cards_label = QLabel("Hero")
        self.cards_label.setObjectName("Muted")
        cards_row.addWidget(self.cards_label)
        self._hero_cards_box = QHBoxLayout()
        self._hero_cards_box.setSpacing(4)
        cards_row.addLayout(self._hero_cards_box)
        cards_row.addStretch(1)
        layout.addLayout(cards_row)

        # Action sequence row for current street
        self.action_card = QFrame()
        self.action_card.setObjectName("Card")
        a_layout = QVBoxLayout(self.action_card)
        a_layout.setContentsMargins(14, 10, 14, 10)
        self.action_title = QLabel("Action")
        self.action_title.setObjectName("SectionTitle")
        a_layout.addWidget(self.action_title)
        self._action_holder = QVBoxLayout()
        a_layout.addLayout(self._action_holder)
        layout.addWidget(self.action_card)

        # Coach commentary
        self.coach_card = QFrame()
        self.coach_card.setObjectName("Card")
        c_layout = QVBoxLayout(self.coach_card)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_title = QLabel("AI Coach")
        c_title.setObjectName("SectionTitle")
        c_layout.addWidget(c_title)
        self.coach_text = QLabel("")
        self.coach_text.setWordWrap(True)
        self.coach_text.setStyleSheet("color: #9CA3AF;")
        c_layout.addWidget(self.coach_text)
        layout.addWidget(self.coach_card)

        # Playback controls
        ctrl_row = QHBoxLayout()
        self.prev_btn = QPushButton("◀  Prev")
        self.prev_btn.clicked.connect(lambda: self.step(-1))
        self.next_btn = QPushButton("Next  ▶")
        self.next_btn.clicked.connect(lambda: self.step(1))
        self.next_btn.setObjectName("PrimaryButton")
        self.review_btn = QPushButton("🤖  Full AI Review")
        self.review_btn.clicked.connect(self._emit_full_review)
        self.practice_btn = QPushButton("▶  Practice similar")
        self.practice_btn.clicked.connect(self._emit_practice)
        ctrl_row.addWidget(self.prev_btn)
        ctrl_row.addWidget(self.next_btn)
        ctrl_row.addStretch(1)
        ctrl_row.addWidget(self.review_btn)
        ctrl_row.addWidget(self.practice_btn)
        layout.addLayout(ctrl_row)

    # --- public API ------------------------------------------------------
    def load_hand(self, hand: dict) -> None:
        """Build snapshots from the hand and render the first one."""
        self.hand = hand
        self.snapshots = self._build_snapshots(hand)
        self.current = 0
        self._sync_header()
        self._sync_hero_cards()
        # Enable street tabs based on whether actions exist for that street
        for i, s in enumerate(STREETS):
            has = bool(hand.get(f"{s}_actions"))
            btn = self.street_buttons[i]
            btn.setEnabled(has or s == "preflop")
            btn._enabled_actions = has or s == "preflop"
            btn._refresh()
        self._render_snapshot()

    def step(self, delta: int) -> None:
        if not self.snapshots:
            return
        new = max(0, min(len(self.snapshots) - 1, self.current + delta))
        if new != self.current:
            self.current = new
            self._render_snapshot()

    def jump_to(self, street_name: str) -> None:
        for i, snap in enumerate(self.snapshots):
            if snap.name == street_name:
                self.current = i
                self._render_snapshot()
                return

    # --- helpers ---------------------------------------------------------
    def _build_snapshots(self, hand: dict) -> list[StreetSnapshot]:
        board = _board_chunks(hand.get("board", ""))
        hero_pos = (hand.get("hero_position") or "BTN").upper()
        villain_pool = [p for p in DEFAULT_POSITIONS_6 if p != hero_pos]
        snaps: list[StreetSnapshot] = []
        # community card counts per street
        cuts = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
        running_pot = 0.0
        target_pot = float(hand.get("pot_bb") or 0)
        for street in STREETS:
            actions_codes = hand.get(f"{street}_actions", "") or ""
            if not actions_codes and street != "preflop":
                # Skip streets that didn't happen
                continue
            actions_by_pos = _explode_actions(actions_codes, hero_pos, villain_pool)
            community = board[: cuts[street]] if board else (
                ["W", "W", "W"] if street == "flop" else
                ["W", "W", "W", "W"] if street == "turn" else
                ["W", "W", "W", "W", "W"] if street == "river" else []
            )
            # crude running pot estimate
            running_pot += target_pot * (0.30 if street == "preflop" else 0.25)
            running_pot = min(running_pot, target_pot)
            snaps.append(StreetSnapshot(
                name=street,
                actions_by_position=actions_by_pos,
                community=community,
                pot_bb=round(running_pot, 1),
                commentary=_street_commentary(street, hand),
            ))
        return snaps

    def _sync_header(self) -> None:
        if not self.hand:
            return
        hand_id = self.hand.get("external_id") or self.hand.get("id", "")
        cards = self.hand.get("hero_cards", "??")
        pos = self.hand.get("hero_position", "?")
        fmt = (self.hand.get("format") or "")[:30]
        self.title_label.setText(f"#{hand_id}  ·  {pos} {cards}  ·  {fmt}")
        profit = float(self.hand.get("hero_profit_bb") or 0)
        if profit >= 0:
            self.profit_label.setText(f"+{profit:.1f}bb")
            self.profit_label.setStyleSheet("color: #10B981; font-weight: 800; font-size: 16px;")
        else:
            self.profit_label.setText(f"{profit:.1f}bb")
            self.profit_label.setStyleSheet("color: #EF4444; font-weight: 800; font-size: 16px;")

    def _sync_hero_cards(self) -> None:
        # Clear
        while self._hero_cards_box.count():
            item = self._hero_cards_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        cards = (self.hand or {}).get("hero_cards", "")
        chunks = [cards[i:i + 2] for i in range(0, len(cards) - len(cards) % 2, 2)]
        for c in chunks[:2]:
            self._hero_cards_box.addWidget(MiniCard(c, size=30))

    def _render_snapshot(self) -> None:
        if not self.snapshots:
            return
        snap = self.snapshots[self.current]
        # Toggle street tabs
        for i, s in enumerate(STREETS):
            self.street_buttons[i].setChecked(s == snap.name)
        # Update oval table
        self.table.set_actions(snap.actions_by_position)
        self.table.set_community_cards(snap.community)
        if self.hand:
            self.table.set_hero(self.hand.get("hero_position", "BTN"))
        self.table.set_spr_po(spr=round(snap.pot_bb / max(1.0, snap.pot_bb * 0.4 or 1.0), 1) if snap.pot_bb else None,
                              po=33.3 if snap.pot_bb else None)
        # Action card
        while self._action_holder.count():
            item = self._action_holder.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for pos, acts in snap.actions_by_position.items():
            row = QHBoxLayout()
            label = QLabel(pos)
            label.setObjectName("Muted")
            label.setFixedWidth(40)
            row.addWidget(label)
            row.addWidget(ActionSequence(acts, scale=1.0))
            wrapper = QWidget()
            wrapper.setLayout(row)
            self._action_holder.addWidget(wrapper)
        if not snap.actions_by_position:
            empty = QLabel("Bu street'te kayıt yok.")
            empty.setObjectName("Muted")
            self._action_holder.addWidget(empty)
        # Coach
        self.coach_text.setText(snap.commentary)
        self.coach_message.emit(snap.commentary)
        # Buttons enable/disable
        self.prev_btn.setEnabled(self.current > 0)
        self.next_btn.setEnabled(self.current < len(self.snapshots) - 1)

    def _emit_full_review(self) -> None:
        if not self.hand:
            return
        parts = [f"Hand #{self.hand.get('external_id', '?')} full review:"]
        for snap in self.snapshots:
            parts.append("• " + snap.commentary)
        parts.append(
            f"Net result: {self.hand.get('hero_profit_bb', 0):+.1f}bb "
            f"({'win' if (self.hand.get('hero_profit_bb') or 0) >= 0 else 'loss'})."
        )
        self.coach_message.emit("\n".join(parts))

    def _emit_practice(self) -> None:
        if self.hand:
            # Mark this hand as a "to-study" entry in the adaptive engine. The hand
            # represents a real spot the user wants to drill — register it as a
            # mistake-priority spot so next_drill() surfaces it.
            try:
                from app.core.app_state import AppState  # local import to avoid cycle
                # Hand_id is stored as external_id from the parser
                spot_id = f"REPLAY-{self.hand.get('external_id') or self.hand.get('id', '?')}"
                # We can't reach AppState directly from a component, but the parent
                # screen is responsible for piping practice_requested into the engine.
                # We attach a hint dict so the receiver knows to register it.
                self.hand["_replay_spot_id"] = spot_id
            except Exception:
                pass
            self.practice_requested.emit(self.hand)
