"""GTO Range Chart ekranı.

GTOWizard tarzı 13×13 grid + pozisyon/stack/scenario/mod seçici.
- Sol panel: kontroller (pozisyon, scenario, stack depth, mode)
- Merkez: 13×13 grid (kırmızı=raise, yeşil=call, mavi=fold, split=mixed)
- Sağ panel: seçili el için detaylı açıklama + frekans bar'ı
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSplitter, QVBoxLayout, QWidget,
)


class FrequencyBar(QWidget):
    """Tek-widget bar: arka plan + dolum oranı (QPainter ile)."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._bg = QColor("#1F2937")
        self._pct = 0
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_percentage(self, pct: int) -> None:
        self._pct = max(0, min(100, int(pct)))
        self.update()

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect()
        # Yuvarlatılmış arka plan
        p.setPen(Qt.NoPen)
        p.setBrush(self._bg)
        p.drawRoundedRect(rect, 4, 4)
        # Dolum kısmı
        if self._pct > 0:
            fill_w = max(2, int(rect.width() * self._pct / 100))
            from PySide6.QtCore import QRect
            fill_rect = QRect(rect.x(), rect.y(), fill_w, rect.height())
            p.setBrush(self._color)
            p.drawRoundedRect(fill_rect, 4, 4)

from app.core.app_state import AppState
from app.poker.gto_ranges import (
    MODES, POSITIONS_6MAX, POSITIONS_8MAX, SCENARIOS, STACK_DEPTHS,
    get_action,
)
from app.ui.components.range_grid import RangeGrid


class GTORangeChartScreen(QWidget):
    """Hem free explore hem quiz olarak kullanılabilen GTO chart."""

    coach_message = Signal(str)

    def __init__(self, state: AppState | None = None):
        super().__init__()
        self.state = state
        self._position = "BTN"
        self._scenario = "RFI"
        self._stack_depth = 100
        self._mode = "cash"
        self._table_max = 6   # 6max default

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # Başlık
        title = QLabel("GTO Preflop Range Chart")
        title.setObjectName("Title")
        subtitle = QLabel("Solver-derived ranges  ·  Upswing / GTOWizard public konsensus")
        subtitle.setObjectName("Muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        # Üst kontrol bar
        root.addLayout(self._build_controls())

        # Ana içerik: splitter ile sol grid + sağ detay
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)

        # Sol: range grid
        self.range_grid = RangeGrid(
            position=self._position, scenario=self._scenario,
            stack_depth=self._stack_depth, mode=self._mode,
        )
        self.range_grid.hand_clicked.connect(self._on_hand_clicked)
        grid_wrap = QWidget()
        gw_layout = QVBoxLayout(grid_wrap)
        gw_layout.setContentsMargins(0, 0, 0, 0)
        gw_layout.addWidget(self.range_grid)
        splitter.addWidget(grid_wrap)

        # Sağ: detail panel
        self.detail_panel = self._build_detail_panel()
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)

        # İlk hand seçimi
        self._on_hand_clicked("AA")

    # ── KONTROLLER ────────────────────────────────────────────────────

    def _build_controls(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(14)

        # Mode (cash/MTT)
        h.addWidget(self._label("Mode"))
        self.mode_box = QComboBox()
        self.mode_box.addItems(["Cash", "MTT"])
        self.mode_box.currentTextChanged.connect(
            lambda t: self._update_config(mode=t.lower())
        )
        h.addWidget(self.mode_box)

        # Table max (6max / 8max)
        h.addWidget(self._label("Table"))
        self.table_box = QComboBox()
        self.table_box.addItems(["6-max", "8-max"])
        self.table_box.currentTextChanged.connect(self._on_table_changed)
        h.addWidget(self.table_box)

        # Position
        h.addWidget(self._label("Position"))
        self.pos_box = QComboBox()
        self.pos_box.addItems(POSITIONS_6MAX)
        self.pos_box.setCurrentText("BTN")
        self.pos_box.currentTextChanged.connect(
            lambda t: self._update_config(position=t)
        )
        h.addWidget(self.pos_box)

        # Stack depth
        h.addWidget(self._label("Stack"))
        self.stack_box = QComboBox()
        self.stack_box.addItems([f"{d}bb" for d in STACK_DEPTHS])
        self.stack_box.setCurrentText("100bb")
        self.stack_box.currentTextChanged.connect(
            lambda t: self._update_config(stack_depth=int(t.replace("bb", "")))
        )
        h.addWidget(self.stack_box)

        # Scenario
        h.addWidget(self._label("Scenario"))
        self.scen_box = QComboBox()
        self.scen_box.addItems(SCENARIOS)
        self.scen_box.currentTextChanged.connect(
            lambda t: self._update_config(scenario=t)
        )
        h.addWidget(self.scen_box)

        h.addStretch(1)

        # Quiz butonu (placeholder)
        quiz_btn = QPushButton("🎯 Quiz Modu")
        quiz_btn.setToolTip("Random el → 3sn'de aksiyon → GTO ile karşılaştır (yakında)")
        quiz_btn.setEnabled(False)
        h.addWidget(quiz_btn)

        return h

    def _label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
        return lbl

    def _on_table_changed(self, text: str) -> None:
        new_max = 6 if text == "6-max" else 8
        if new_max == self._table_max:
            return
        self._table_max = new_max
        positions = POSITIONS_6MAX if new_max == 6 else POSITIONS_8MAX
        current = self.pos_box.currentText()
        self.pos_box.blockSignals(True)
        self.pos_box.clear()
        self.pos_box.addItems(positions)
        if current in positions:
            self.pos_box.setCurrentText(current)
        else:
            self.pos_box.setCurrentText("BTN")
        self.pos_box.blockSignals(False)
        self._update_config(position=self.pos_box.currentText())

    def _update_config(self, **kwargs) -> None:
        if "position" in kwargs:
            self._position = kwargs["position"]
        if "scenario" in kwargs:
            self._scenario = kwargs["scenario"]
        if "stack_depth" in kwargs:
            self._stack_depth = kwargs["stack_depth"]
        if "mode" in kwargs:
            self._mode = kwargs["mode"]
        self.range_grid.set_config(
            self._position, self._scenario, self._stack_depth, self._mode
        )
        # Detay panelini de güncelle
        if hasattr(self, "_selected_hand"):
            self._on_hand_clicked(self._selected_hand)

    # ── DETAIL PANEL ──────────────────────────────────────────────────

    def _build_detail_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.StyledPanel)
        panel.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #1F2937; "
            "border-radius: 8px; padding: 12px; }"
        )
        v = QVBoxLayout(panel)
        v.setSpacing(10)

        self.hand_label = QLabel("Seç bir el")
        self.hand_label.setStyleSheet(
            "color: #FAFAFA; font-size: 28px; font-weight: 700;"
        )
        v.addWidget(self.hand_label)

        # Frekans bar'ları
        self.bar_raise = self._make_freq_bar("Raise", "#DC2626")
        self.bar_call = self._make_freq_bar("Call", "#10B981")
        self.bar_fold = self._make_freq_bar("Fold", "#2563EB")
        v.addWidget(self.bar_raise["row"])
        v.addWidget(self.bar_call["row"])
        v.addWidget(self.bar_fold["row"])

        # Açıklama
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #1F2937; max-height: 1px;")
        v.addWidget(sep)

        self.explanation = QLabel("")
        self.explanation.setWordWrap(True)
        self.explanation.setStyleSheet(
            "color: #CBD5E1; font-size: 12px; line-height: 1.5;"
        )
        v.addWidget(self.explanation)

        v.addStretch(1)
        return panel

    def _make_freq_bar(self, label: str, color: str) -> dict:
        row = QWidget()
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        lbl = QLabel(label)
        lbl.setFixedWidth(70)
        lbl.setStyleSheet("color: #CBD5E1; font-size: 12px; font-weight: 600;")
        bar = FrequencyBar(color)
        bar.setMinimumWidth(120)   # ensure layout reserves space for the bar
        pct_lbl = QLabel("0%")
        pct_lbl.setFixedWidth(56)
        pct_lbl.setStyleSheet(
            "color: #FAFAFA; font-size: 13px; font-weight: 700; "
            "padding-right: 4px;"
        )
        pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lbl)
        h.addWidget(bar, 1)
        h.addWidget(pct_lbl)
        return {"row": row, "bar": bar, "pct": pct_lbl}

    def _on_hand_clicked(self, hand: str) -> None:
        self._selected_hand = hand
        action = get_action(
            self._position, hand, self._scenario,
            self._stack_depth, self._mode,
        )
        self.hand_label.setText(hand)
        for bar_dict, key in [(self.bar_raise, "raise"),
                               (self.bar_call, "call"),
                               (self.bar_fold, "fold")]:
            pct = action.get(key, 0)
            bar_dict["bar"].set_percentage(pct)
            bar_dict["pct"].setText(f"{pct}%")
        # Açıklama metni
        self.explanation.setText(self._build_explanation(hand, action))

    def _build_explanation(self, hand: str, action: dict) -> str:
        r = action.get("raise", 0)
        c = action.get("call", 0)
        f = action.get("fold", 0)
        pos = self._position
        scen = self._scenario
        depth = self._stack_depth
        mode = self._mode

        if r == 100:
            return (f"<b>{hand}</b> bu spotta saf RAISE. {pos}'den {scen} senaryosunda "
                    f"{depth}bb stack ile {mode.upper()} oyununda her zaman aç. "
                    f"Bu el range'inin üst dilimi — value heavy.")
        if f == 100:
            return (f"<b>{hand}</b> bu spotta saf FOLD. {pos}'den oynamak için yeterince "
                    f"güçlü değil. Daha geç pozisyonda (CO/BTN) açılabilir.")
        if c == 100:
            return (f"<b>{hand}</b> saf CALL — flat strategy. Range protection için bu "
                    f"hand'i raise yerine call ediyorsun.")
        # Mixed strategy
        parts = []
        if r > 0:
            parts.append(f"%{r} raise")
        if c > 0:
            parts.append(f"%{c} call")
        if f > 0:
            parts.append(f"%{f} fold")
        return (f"<b>{hand}</b> mixed strategy: " + ", ".join(parts) + ". "
                f"Solver bu hand'i indifference noktasına yakın görüyor — uzun vadede "
                f"oranlara sadık kalmak için RNG kullan (örn. saat saniyesi son rakam).")


# ── BACKWARDS COMPAT ──────────────────────────────────────────────────
# Eski main.py importu RangeTrainerScreen alias'ını arıyor olabilir
RangeTrainerScreen = GTORangeChartScreen
