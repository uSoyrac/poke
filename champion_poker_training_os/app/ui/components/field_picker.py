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
    QSpinBox, QVBoxLayout, QWidget,
)

from app.engine.bot_brain import BOT_ARCHETYPES, KARMA_MIX, sample_field


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
        self._weights: dict = {}      # arketip → yüzde (havuz dağıtıcı)

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

        # ── HAVUZ DAĞITICI (opsiyonel) — %'ye göre profil dağıt ──────────
        # Varsayılan: hiçbir şey seçilmezse koltuklar Random kalır. Kullanıcı
        # "40% Shark" gibi havuzdan profil + yüzde ekleyip "Dağıt" derse,
        # koltuklar oransal olarak doldurulur (kalan = Random). Seçim görünür.
        dist_title = QLabel("HAVUZ DAĞITICI  ·  opsiyonel")
        dist_title.setObjectName("TLabel")
        dist_title.setStyleSheet(
            "font-family:'JetBrains Mono',monospace; font-size:10px; "
            "letter-spacing:1.5px; color:#8a8f80; background:transparent; padding-top:6px;")
        v.addWidget(dist_title)

        dist = QHBoxLayout()
        dist.setSpacing(6)
        self._dist_combo = QComboBox()
        self._dist_combo.addItems(list(BOT_ARCHETYPES.keys()))   # havuzdaki HERKES
        self._dist_combo.setMinimumWidth(150)
        self._dist_pct = QSpinBox()
        self._dist_pct.setRange(5, 100)
        self._dist_pct.setSingleStep(5)
        self._dist_pct.setValue(40)
        self._dist_pct.setSuffix(" %")
        add_w = QPushButton("+ Ekle")
        add_w.setCursor(Qt.PointingHandCursor)
        add_w.clicked.connect(self._add_weight)
        apply_w = QPushButton("Dağıt")
        apply_w.setCursor(Qt.PointingHandCursor)
        apply_w.setStyleSheet(
            "QPushButton{background:#0f2318;color:#5ad17a;border:1px solid #5ad17a;"
            "font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;"
            "padding:4px 12px;} QPushButton:hover{background:#143020;}")
        apply_w.clicked.connect(self._apply_distribution)
        clear_w = QPushButton("Temizle")
        clear_w.setCursor(Qt.PointingHandCursor)
        clear_w.clicked.connect(self._clear_weights)
        for w_ in (self._dist_combo, self._dist_pct, add_w, apply_w, clear_w):
            dist.addWidget(w_)
        dist.addStretch(1)
        v.addLayout(dist)

        self._dist_label = QLabel("Atanmadı — koltuklar Random (varsayılan).")
        self._dist_label.setObjectName("Muted")
        self._dist_label.setWordWrap(True)
        self._dist_label.setStyleSheet("font-size:11px; color:#5a5e54;")
        v.addWidget(self._dist_label)

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

    # ── havuz dağıtıcı (% composition) ───────────────────────────────

    def _add_weight(self) -> None:
        """Seçili arketip + yüzdeyi ağırlık havuzuna ekle (toplam ≤ %100)."""
        arch = self._dist_combo.currentText()
        pct = float(self._dist_pct.value())
        current = sum(p for a, p in self._weights.items() if a != arch)
        # Toplam %100'ü aşmasın — kalanla sınırla
        pct = min(pct, max(0.0, 100.0 - current))
        if pct <= 0:
            self._dist_label.setText("Toplam %100'e ulaştı — daha fazla eklenemez.")
            return
        self._weights[arch] = pct
        self._update_weight_label()

    def _clear_weights(self) -> None:
        self._weights = {}
        self._update_weight_label()

    def _update_weight_label(self) -> None:
        if not self._weights:
            self._dist_label.setText("Atanmadı — koltuklar Random (varsayılan).")
            return
        assigned = sum(self._weights.values())
        parts = [f"{a} %{p:.0f}" for a, p in self._weights.items()]
        rem = max(0.0, 100.0 - assigned)
        if rem > 0:
            parts.append(f"kalan %{rem:.0f} Random")
        self._dist_label.setText("  ·  ".join(parts) + "   → 'Dağıt' ile uygula")

    def _apply_distribution(self) -> None:
        """Ağırlıkları mevcut bot sayısına oransal dağıt → koltukları doldur."""
        n = len(self._rows)
        if n == 0:
            return
        # Kalan koltuklar 'Random (Karma)' kalsın → her elde yeniden örneklenir;
        # açıkça seçilenler (örn. Shark) sabit.
        self.set_composition(
            sample_field(n, self._weights, random_token=RANDOM_LABEL))

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
