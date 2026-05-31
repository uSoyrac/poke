"""HandRangeSelector — tıklanabilir 13×13 preflop el-aralığı seçici.

Hero'nun hangi ellerden deal edileceğini chart'tan seçmek için. Varsayılan
TÜM eller seçili; 'Sıfırla' boşaltır, hücreye tıklayınca aç/kapa, sürükleyerek
çoklu seçim. selected_hands() → set[str] (örn. {'AA','AKs',...}). 169 elin
tamamı seçiliyse filtre yok demektir (motor 'tüm eller' kabul eder).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialogButtonBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

_RANKS = "AKQJT98765432"


def all_hand_keys() -> set:
    out = set()
    for i, hi in enumerate(_RANKS):
        for j, lo in enumerate(_RANKS):
            if i == j:
                out.add(hi + lo)
            elif i < j:
                out.add(hi + lo + "s")
            else:
                out.add(lo + hi + "o")
    return out


def _cell_key(r: int, c: int) -> str:
    hi, lo = _RANKS[r], _RANKS[c]
    if r == c:
        return hi + lo                 # pair
    if r < c:
        return hi + lo + "s"           # suited (hi yüksek)
    return lo + hi + "o"               # offsuit (yüksek önce)


class HandRangeSelector(QWidget):
    """13×13 tıklanabilir el-aralığı grid'i."""

    changed = Signal(int)   # seçili el sayısı

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells: dict[str, QPushButton] = {}
        self._selected: set = all_hand_keys()   # varsayılan: hepsi

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Üst: Tümü / Sıfırla / özet
        bar = QHBoxLayout()
        btn_all = QPushButton("Tümü")
        btn_all.clicked.connect(self.select_all)
        btn_none = QPushButton("Sıfırla")
        btn_none.clicked.connect(self.clear_all)
        for b in (btn_all, btn_none):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{background:#15181a;color:#cdd2c4;border:1px solid #2a2e26;"
                "border-radius:4px;padding:4px 14px;font-weight:600;}"
                "QPushButton:hover{border-color:#5ad17a;color:#5ad17a;}")
        bar.addWidget(btn_all)
        bar.addWidget(btn_none)
        bar.addStretch(1)
        self._summary = QLabel()
        self._summary.setStyleSheet("color:#94A3B8;font-size:12px;font-weight:600;")
        bar.addWidget(self._summary)
        root.addLayout(bar)

        # 13×13 grid
        grid = QGridLayout()
        grid.setSpacing(2)
        for r in range(13):
            for c in range(13):
                key = _cell_key(r, c)
                btn = QPushButton(key)
                btn.setCheckable(True)
                btn.setChecked(True)
                btn.setFixedSize(46, 30)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _=False, k=key: self._toggle(k))
                self._cells[key] = btn
                grid.addWidget(btn, r, c)
        root.addLayout(grid)

        self._restyle_all()

    # ── public API ──
    def selected_hands(self) -> set:
        return set(self._selected)

    def set_selected(self, hands) -> None:
        self._selected = {str(h) for h in hands} if hands else set()
        for k, b in self._cells.items():
            b.setChecked(k in self._selected)
        self._restyle_all()

    def select_all(self) -> None:
        self.set_selected(all_hand_keys())

    def clear_all(self) -> None:
        self.set_selected(set())

    def is_full(self) -> bool:
        return len(self._selected) >= 169

    # ── internal ──
    def _toggle(self, key: str) -> None:
        if key in self._selected:
            self._selected.discard(key)
        else:
            self._selected.add(key)
        self._restyle_cell(key)
        self._update_summary()
        self.changed.emit(len(self._selected))

    def _restyle_cell(self, key: str) -> None:
        b = self._cells[key]
        on = key in self._selected
        # pair=sarı, suited=yeşil, offsuit=mavi tonları (seçiliyken dolu)
        if len(key) == 2:
            base = "#f4c842"
        elif key.endswith("s"):
            base = "#5ad17a"
        else:
            base = "#5a9eef"
        if on:
            b.setStyleSheet(
                f"QPushButton{{background:{base};color:#0a0c0a;border:none;"
                f"border-radius:3px;font-size:11px;font-weight:700;}}")
        else:
            b.setStyleSheet(
                "QPushButton{background:#15181a;color:#5a5e54;border:1px solid #23271f;"
                "border-radius:3px;font-size:11px;font-weight:600;}")

    def _restyle_all(self) -> None:
        for k in self._cells:
            self._restyle_cell(k)
        self._update_summary()

    def _update_summary(self) -> None:
        n = len(self._selected)
        pct = 100.0 * n / 169
        tag = "  ·  TÜM ELLER (filtre yok)" if n >= 169 else ""
        self._summary.setText(f"{n}/169 el  ·  %{pct:.0f}{tag}")


class HandRangeDialog(QDialog):
    """HandRangeSelector'ı saran OK/İptal diyaloğu."""

    def __init__(self, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hero El Aralığı — chart'tan seç")
        self.setStyleSheet("QDialog{background:#0d100e;}")
        v = QVBoxLayout(self)
        info = QLabel("Hero'nun deal edileceği elleri seç. Varsayılan: tüm eller. "
                      "Belirli elleri çalışmak için 'Sıfırla' deyip seç.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#94A3B8;font-size:12px;")
        v.addWidget(info)
        self.selector = HandRangeSelector()
        if initial:
            self.selector.set_selected(initial)
        v.addWidget(self.selector)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def selected_hands(self) -> set:
        return self.selector.selected_hands()
