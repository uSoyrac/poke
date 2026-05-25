"""FieldPicker — dynamic seat-by-seat archetype picker.

Replaces the old "PLAYERS combo + single ARCHETYPE combo" pattern with a
seat-list where every opponent can be configured individually. The user
can:

- Add a new seat (max 8 bots = 9-max table including hero)
- Remove a seat (min 1 bot = heads-up)
- Pick any specific archetype per seat
- Pick "Random" — that seat samples from KARMA_MIX every new game

Used by both PlaySessionScreen and TournamentSimulatorScreen so the
setup UX is unified. Returns the resolved archetype list via
`get_archetypes()` — "Random" entries are sampled at call time.
"""
from __future__ import annotations

import random
from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from app.engine.bot_brain import BOT_ARCHETYPES, KARMA_MIX


RANDOM_LABEL = "Random (Karma)"


class _SeatRow(QFrame):
    """One opponent seat — archetype combo + remove button."""

    removed = Signal(object)  # emits self

    def __init__(self, archetype: str = RANDOM_LABEL, can_remove: bool = True):
        super().__init__()
        self.setObjectName("FieldSeatRow")
        self.setStyleSheet(
            "QFrame#FieldSeatRow { background: #0f1210; border: 1px solid #23271f; "
            "padding: 0; }"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 6, 6, 6)
        h.setSpacing(8)

        self.seat_label = QLabel("SEAT")
        self.seat_label.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:10px; "
            "letter-spacing:1.6px; color:#898d80; background:transparent;"
        )
        self.seat_label.setMinimumWidth(44)
        h.addWidget(self.seat_label)

        self.combo = QComboBox()
        self.combo.addItem(RANDOM_LABEL)
        self.combo.setItemData(0, "Her oyunda KARMA_MIX'ten rastgele bir tarz seçilir.", Qt.ToolTipRole)
        for name, prof in BOT_ARCHETYPES.items():
            self.combo.addItem(name)
            self.combo.setItemData(
                self.combo.count() - 1,
                f"{name} — VPIP {prof.vpip}% · PFR {prof.pfr}% · AF {prof.aggression}\n{prof.notes}",
                Qt.ToolTipRole,
            )
        idx = self.combo.findText(archetype)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.setMinimumHeight(28)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h.addWidget(self.combo, 1)

        # Use "REMOVE" rather than a tiny X — more readable, no font fallback risk
        self.remove_btn = QPushButton("REMOVE")
        self.remove_btn.setObjectName("FieldRemoveBtn")
        self.remove_btn.setFixedHeight(28)
        self.remove_btn.setMinimumWidth(74)
        self.remove_btn.setCursor(Qt.PointingHandCursor)
        self.remove_btn.setToolTip("Bu oyuncuyu masadan çıkar")
        self.remove_btn.setStyleSheet(
            "QPushButton#FieldRemoveBtn { background:#1a0e0e; color:#e87474; "
            "border:1px solid #5a2222; font-family:'JetBrains Mono','Menlo',monospace; "
            "font-size:10px; font-weight:700; letter-spacing:1.2px; padding:0 8px; }"
            "QPushButton#FieldRemoveBtn:hover { background:#2a1414; color:#f29090; }"
            "QPushButton#FieldRemoveBtn:disabled { background:#0f1210; color:#33382c; "
            "border-color:#23271f; }"
        )
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self))
        self.remove_btn.setEnabled(can_remove)
        h.addWidget(self.remove_btn)

    def archetype(self) -> str:
        return self.combo.currentText()

    def set_seat_number(self, n: int) -> None:
        self.seat_label.setText(f"S{n}")

    def set_can_remove(self, can: bool) -> None:
        self.remove_btn.setEnabled(can)


class FieldPicker(QFrame):
    """Seat-by-seat opponent archetype picker.

    Emits ``composition_changed`` whenever the seat list changes so the
    parent screen can refresh things like a "TOTAL PLAYERS: N" label.
    """

    MIN_BOTS = 1   # heads-up minimum
    MAX_BOTS = 8   # 9-max table (hero + 8 bots)

    composition_changed = Signal(int)  # total players (hero + bots)

    def __init__(self, default_bots: int = 5, default_archetype: str = RANDOM_LABEL):
        super().__init__()
        self.setObjectName("FieldPicker")
        self.setStyleSheet(
            "QFrame#FieldPicker { background: transparent; border: none; }"
        )
        self._rows: List[_SeatRow] = []

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Header row — title + counter + add button
        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel("FIELD COMPOSITION")
        title.setObjectName("TLabel")
        header.addWidget(title)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:10px; "
            "letter-spacing:1.5px; color:#5ad17a; background:transparent;"
        )
        header.addWidget(self.count_label)
        header.addStretch(1)

        self.add_btn = QPushButton("+  ADD SEAT")
        self.add_btn.setObjectName("FieldAddBtn")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setMinimumHeight(28)
        self.add_btn.setStyleSheet(
            "QPushButton#FieldAddBtn { background:#0f2318; color:#5ad17a; "
            "border:1px solid #5ad17a; font-family:'JetBrains Mono',monospace; "
            "font-size:11px; font-weight:700; letter-spacing:1.4px; padding:4px 12px; }"
            "QPushButton#FieldAddBtn:hover { background:#143020; }"
            "QPushButton#FieldAddBtn:disabled { background:#0f1210; color:#33382c; "
            "border-color:#23271f; }"
        )
        self.add_btn.clicked.connect(self._add_random_seat)
        header.addWidget(self.add_btn)
        v.addLayout(header)

        # Rows container
        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(4)
        v.addLayout(self._rows_box)

        # Tip line
        tip = QLabel(
            "Her seat için tarz seç veya 'Random' bırak — random olanlar her elde "
            "Karma havuzundan farklı bir karakter alır. + ile yeni rakip ekle, × ile çıkar."
        )
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        tip.setStyleSheet("font-size: 11px; color: #5a5e54; padding-top: 2px;")
        v.addWidget(tip)

        # Build defaults
        n = max(self.MIN_BOTS, min(default_bots, self.MAX_BOTS))
        for _ in range(n):
            self._append_seat(default_archetype)
        self._renumber_and_emit()

    # ── public API ──────────────────────────────────────────────────

    def get_archetypes(self) -> List[str]:
        """Return resolved archetype list — 'Random' entries are sampled now."""
        out: List[str] = []
        for r in self._rows:
            a = r.archetype()
            if a == RANDOM_LABEL:
                out.append(random.choice(KARMA_MIX))
            else:
                out.append(a)
        return out

    def total_players(self) -> int:
        """Hero + bots."""
        return len(self._rows) + 1

    def set_composition(self, archetypes: List[str]) -> None:
        """Replace the current seats with a new list (used by templates)."""
        while self._rows:
            self._remove_row(self._rows[-1], silent=True)
        for a in archetypes[: self.MAX_BOTS]:
            self._append_seat(a)
        self._renumber_and_emit()

    # ── internal ────────────────────────────────────────────────────

    def _append_seat(self, archetype: str) -> None:
        row = _SeatRow(archetype=archetype, can_remove=True)
        row.removed.connect(lambda r: self._remove_row(r))
        self._rows.append(row)
        self._rows_box.addWidget(row)

    def _add_random_seat(self) -> None:
        if len(self._rows) >= self.MAX_BOTS:
            return
        self._append_seat(RANDOM_LABEL)
        self._renumber_and_emit()

    def _remove_row(self, row: _SeatRow, silent: bool = False) -> None:
        if len(self._rows) <= self.MIN_BOTS and not silent:
            return
        if row in self._rows:
            self._rows.remove(row)
            row.setParent(None)
            row.deleteLater()
            if not silent:
                self._renumber_and_emit()

    def _renumber_and_emit(self) -> None:
        for i, r in enumerate(self._rows, start=1):
            r.set_seat_number(i)
            r.set_can_remove(len(self._rows) > self.MIN_BOTS)
        total = self.total_players()
        self.count_label.setText(f"TOTAL  {total}  ·  HERO + {len(self._rows)} BOTS")
        self.add_btn.setEnabled(len(self._rows) < self.MAX_BOTS)
        self.composition_changed.emit(total)
