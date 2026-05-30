from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.poker.gto_ranges import all_hand_keys, get_action
from app.ui.components.range_grid import RangeGrid


# Aksiyon renkleri (matris legend'i ile aynı)
_ACTION_COLOR = {"raise": "#DC2626", "call": "#10B981", "fold": "#2563EB"}
_ACTION_LABEL = {"raise": "Raise / Jam", "call": "Call", "fold": "Fold"}


# Filtre değerleri → GTO motoru parametreleri eşlemesi
_FORMAT_TO_MODE = {
    "cash": "cash", "MTT": "MTT", "SNG": "MTT", "PKO": "MTT", "heads-up": "cash",
}
_POT_TO_SCENARIO = {
    "SRP": "RFI", "3BP": "vs 3-bet", "4BP": "vs 3-bet",
    "limped": "RFI", "multiway": "RFI",
}
# 8-max pozisyon adlarını motorun 6-max curated setine indirger
_POS_ALIAS = {"LJ": "MP", "HJ": "CO"}


def _node_summary(position: str, scenario: str, stack: int, mode: str) -> dict:
    """Seçili node'un tüm 1326 kombo üzerinden ağırlıklı aksiyon dağılımı.

    Matris ile birebir aynı get_action çağrılarını kullanır → sol panel
    (özet) ile sağ panel (matris) her zaman tutarlı.
    """
    tot = 0
    agg = {"raise": 0.0, "call": 0.0, "fold": 0.0}
    for hand in all_hand_keys():
        combos = 6 if len(hand) == 2 else (4 if hand.endswith("s") else 12)
        a = get_action(position, hand, scenario, stack, mode)
        tot += combos
        for k in agg:
            agg[k] += combos * a.get(k, 0) / 100
    tot = max(tot, 1)
    return {k: round(100 * v / tot, 1) for k, v in agg.items()}


class StudyLibraryScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)

        title = QLabel("GTO Study Library")
        title.setObjectName("Title")
        layout.addWidget(title)
        sub = QLabel(
            "Filtreyi değiştir → range matrisi ve özet anında güncellenir. "
            "Curated chart'lar (pro konsensus ~%95) + heuristic motor tüm "
            "spotları kapsar."
        )
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # ── FİLTRELER ──
        filters = QHBoxLayout()
        self.filter_boxes = {}
        for label, values in {
            "Format": ["cash", "MTT", "SNG", "PKO", "heads-up"],
            "Position": ["BTN", "CO", "HJ", "LJ", "MP", "UTG", "SB", "BB"],
            "Scenario": ["SRP", "3BP"],
            "Stack": ["100bb", "60bb", "40bb", "20bb", "15bb", "10bb"],
        }.items():
            box = QComboBox()
            box.addItems(values)
            box.currentTextChanged.connect(self._apply_filters)
            self.filter_boxes[label] = box
            filters.addWidget(QLabel(label))
            filters.addWidget(box)
        filters.addStretch(1)
        layout.addLayout(filters)

        # ── ANA İÇERİK: sol özet + sağ matris ──
        main = QHBoxLayout()
        left = QFrame()
        left.setObjectName("DataPanel")
        left_layout = QVBoxLayout(left)
        self.node_title = QLabel()
        self.node_title.setObjectName("SectionTitle")
        self.node_meta = QLabel()
        self.node_meta.setWordWrap(True)
        self.node_meta.setObjectName("Muted")
        self.range_summary = QLabel()
        self.range_summary.setObjectName("Muted")
        # Kalıcı frekans satırları (her filtrede yeniden yaratmak yerine güncelle
        # → deleteLater gecikmesinden kaynaklı üst üste binme olmaz)
        self.freq_box = QVBoxLayout()
        self.freq_box.setSpacing(10)
        self._freq_rows = {}
        for action in ("raise", "call", "fold"):
            lbl, bar = self._make_freq_row(action)
            self._freq_rows[action] = (lbl, bar)

        buttons = QHBoxLayout()
        for label, target in [
            ("Practice this spot", "Spot Practice Trainer"),
            ("Ask coach why", ""),
            ("Compare my hands", "Hand History Analyzer"),
        ]:
            button = QPushButton(label)
            if label == "Ask coach why":
                button.clicked.connect(
                    lambda: self.coach_message.emit(explain_spot(self._current_spot())))
            elif label == "Practice this spot":
                button.clicked.connect(self._practice_this_spot)
            elif target:
                button.clicked.connect(
                    lambda checked=False, t=target: self.navigate_requested.emit(t))
            buttons.addWidget(button)

        left_layout.addWidget(self.node_title)
        left_layout.addWidget(self.node_meta)
        left_layout.addWidget(self.range_summary)
        left_layout.addLayout(self.freq_box)
        left_layout.addStretch(1)
        left_layout.addLayout(buttons)

        self.range_grid = RangeGrid(position="BTN", scenario="RFI",
                                    stack_depth=100, mode="cash")
        main.addWidget(left, 1)
        main.addWidget(self.range_grid, 1)
        layout.addLayout(main)

        self._apply_filters()

    # ── FİLTRE → NODE ──
    def _derive_node(self) -> dict:
        fmt = self.filter_boxes["Format"].currentText()
        pos = self.filter_boxes["Position"].currentText()
        scen_key = self.filter_boxes["Scenario"].currentText()
        stack_txt = self.filter_boxes["Stack"].currentText()

        mode = _FORMAT_TO_MODE.get(fmt, "cash")
        stack = int(stack_txt.replace("bb", "")) if stack_txt.endswith("bb") else 100
        position = _POS_ALIAS.get(pos, pos)
        # Kısa stack + MTT → push/fold node'u en öğretici olan
        if mode == "MTT" and stack <= 20 and scen_key == "SRP":
            scenario = "Push/Fold"
        else:
            scenario = _POT_TO_SCENARIO.get(scen_key, "RFI")
        return {"format": fmt, "position": position, "scenario": scenario,
                "stack": stack, "mode": mode}

    def _practice_this_spot(self) -> None:
        """Seçili node'u Spot Trainer'a taşı (tek seferlik handoff) ve geç."""
        self.state.practice_spot = self._current_spot()
        self.navigate_requested.emit("Spot Practice Trainer")

    def _current_spot(self) -> dict:
        """Koç açıklaması için sentetik spot dict'i (filtrelerden)."""
        n = self._derive_node()
        return {
            "id": "STUDY", "title": f"{n['position']} {n['scenario']}",
            "format": n["format"], "table": "6-max",
            "stack_bb": n["stack"], "position": n["position"],
            "pot_type": "3BP" if n["scenario"] == "vs 3-bet" else "SRP",
            "street": "preflop", "board_texture": "—",
            "icm": "off", "scenario": n["scenario"],
        }

    def _apply_filters(self, *_) -> None:
        n = self._derive_node()
        # Sağ panel: range matrisi
        self.range_grid.set_config(n["position"], n["scenario"],
                                   n["stack"], n["mode"])
        # Sol panel: node başlığı + yol + özet
        self.node_title.setText(
            f"{n['position']} — {n['scenario']}  ·  {n['stack']}bb  ·  "
            f"{n['mode'].upper()}")
        self.node_meta.setText(
            f"Node path: {n['format']} / {n['position']} / {n['stack']}bb / "
            f"{n['scenario']} / preflop")
        summary = _node_summary(n["position"], n["scenario"],
                                n["stack"], n["mode"])
        played = round(summary["raise"] + summary["call"], 1)
        self.range_summary.setText(
            f"Range: {played}%   ·   Raise {summary['raise']}%   ·   "
            f"Call {summary['call']}%   ·   Fold {summary['fold']}%")

        # Aksiyon frekans çubukları — kalıcı satırları güncelle (yeniden yaratma yok)
        for action in ("raise", "call", "fold"):
            lbl, bar = self._freq_rows[action]
            pct = summary[action]
            lbl.setText(f"{_ACTION_LABEL[action]}  ·  %{pct:.1f}")
            bar.setValue(int(round(pct)))

        # Koç bağlamı için state'e yaz
        self.state.selected_spot = self._current_spot()

    def _make_freq_row(self, action: str):
        """Tek aksiyon için kalıcı renkli frekans satırı (sahte EV yok).

        freq_box'a label + bar ekler; (label, bar) referanslarını döndürür.
        """
        color = _ACTION_COLOR[action]
        lbl = QLabel(f"{_ACTION_LABEL[action]}  ·  %0.0")
        lbl.setStyleSheet(f"color:{color}; font-weight:700; font-size:13px;")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        bar.setStyleSheet(
            f"QProgressBar{{background:#1F2937;border:none;border-radius:5px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
        self.freq_box.addWidget(lbl)
        self.freq_box.addWidget(bar)
        return lbl, bar
