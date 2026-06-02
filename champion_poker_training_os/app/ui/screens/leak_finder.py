from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.repository import get_leak_analysis, get_player_stats
from app.training.drill_library import DrillLibrary
from app.ui.components.metric_card import MetricCard


def _infer_category(name: str) -> str:
    """Leak adından kaba kategori çıkar (data-driven leak'lerde category yoksa)."""
    n = (name or "").lower()
    # Karar-bazlı leak'ler adlarında "(vs 3-bet)" gibi parantez taşır
    if "(" in name and ")" in name:
        inside = name[name.rfind("(") + 1:name.rfind(")")].strip()
        if inside:
            return inside
    if "preflop" in n or "loose" in n or "tight" in n or "rfi" in n:
        return "Preflop"
    if "showdown" in n or "river" in n:
        return "River"
    if "postflop" in n or "cbet" in n or "turn" in n or "flop" in n:
        return "Postflop"
    if "icm" in n or "final table" in n or "short stack" in n or "mtt" in n:
        return "MTT"
    return "General"


def _normalize_leak(raw: dict) -> dict:
    """get_leak_analysis() çıktısını tablo şemasına dönüştür."""
    from app.poker.playbook import playbook_ref_for_leak
    name = raw.get("name", "")
    category = raw.get("category") or _infer_category(name)
    return {
        "name": name,
        "severity": raw.get("severity", "Medium"),
        "category": category,
        "sample_size": int(raw.get("sample_size", 0) or 0),
        "ev_lost": float(raw.get("ev_lost", 0) or 0),
        "frequency_deviation": raw.get("frequency_deviation", "—"),
        "why": raw.get("detail", "") or raw.get("why", ""),
        "fix": raw.get("fix", ""),
        "repair_days": int(raw.get("repair_days", 5) or 5),
        # Hangi uzun-vade Playbook ilkesini ihlal ettiğini bağla
        "playbook": playbook_ref_for_leak(name, category),
    }


# Fallback örnek katalog — gerçek el verisi yetersizken gösterilir.
EXTENDED_LEAKS = [
    {
        "name": "BB underdefend vs BTN min-raise",
        "severity": "High",
        "category": "Preflop",
        "sample_size": 58,
        "ev_lost": 18.4,
        "frequency_deviation": "-14%",
        "why": "Range folds too many suited gappers and wheel Ax hands with enough equity.",
        "fix": "Run 7-day BB defend repair: 15bb, 25bb and 40bb defend drills.",
        "repair_days": 7,
    },
    {
        "name": "River overbluff into calling stations",
        "severity": "Critical",
        "category": "River",
        "sample_size": 31,
        "ev_lost": 26.2,
        "frequency_deviation": "+19%",
        "why": "Villain profile has high call-down tendency; blocker logic is ignored.",
        "fix": "Switch to value-heavy exploit and require nut blockers before large river bluffs.",
        "repair_days": 5,
    },
    {
        "name": "Final table call-off too loose",
        "severity": "High",
        "category": "ICM",
        "sample_size": 14,
        "ev_lost": 21.7,
        "frequency_deviation": "+11%",
        "why": "chipEV instincts are overriding $EV risk premium near pay jumps.",
        "fix": "ICM bootcamp: medium stack risk premium and big stack pressure packs.",
        "repair_days": 7,
    },
    {
        "name": "Turn overbarrel on paired boards",
        "severity": "Medium",
        "category": "Turn",
        "sample_size": 44,
        "ev_lost": 9.5,
        "frequency_deviation": "+8%",
        "why": "Board-pairing turns shift nut advantage toward caller range.",
        "fix": "Classify paired turns before firing second barrel.",
        "repair_days": 3,
    },
    {
        "name": "Thin value missed vs capped ranges",
        "severity": "Medium",
        "category": "River",
        "sample_size": 39,
        "ev_lost": 7.8,
        "frequency_deviation": "-10%",
        "why": "Showdown-value hands are checked back when villain has capped bluff-catcher range.",
        "fix": "Run thin value master combat pack for river half-pot bets.",
        "repair_days": 4,
    },
    {
        "name": "Preflop loose call from SB",
        "severity": "Medium",
        "category": "Preflop",
        "sample_size": 67,
        "ev_lost": 12.3,
        "frequency_deviation": "+9%",
        "why": "SB flats hands that should 3bet or fold. Playing OOP without initiative is expensive.",
        "fix": "SB 3bet or fold discipline drill: remove flat-calling range except deep-stacked spots.",
        "repair_days": 5,
    },
    {
        "name": "Too passive out of position",
        "severity": "High",
        "category": "Postflop",
        "sample_size": 52,
        "ev_lost": 15.6,
        "frequency_deviation": "-12%",
        "why": "Check-call line too often when range advantage supports leading or check-raising.",
        "fix": "OOP aggression drill: practice check-raise and donk-lead spots.",
        "repair_days": 6,
    },
    {
        "name": "Wrong board cbet frequency",
        "severity": "Medium",
        "category": "Flop",
        "sample_size": 85,
        "ev_lost": 11.2,
        "frequency_deviation": "+7%",
        "why": "Cbetting too often on boards that favor caller's range (low connected, paired).",
        "fix": "Board texture cbet discipline: study solver cbet frequency by board type.",
        "repair_days": 4,
    },
    {
        "name": "Short stack impatience",
        "severity": "High",
        "category": "MTT",
        "sample_size": 23,
        "ev_lost": 19.8,
        "frequency_deviation": "+15%",
        "why": "Jamming too wide at 12-18bb instead of waiting for better spots or fold equity.",
        "fix": "Short stack push/fold drill: study Nash equilibrium ranges by position.",
        "repair_days": 5,
    },
    {
        "name": "Multiway pot overaggression",
        "severity": "Medium",
        "category": "Postflop",
        "sample_size": 34,
        "ev_lost": 8.9,
        "frequency_deviation": "+10%",
        "why": "Bluffing into multiway pots where at least one caller has a strong range.",
        "fix": "Multiway caution drill: value-bet only in multiway, bluff rarely.",
        "repair_days": 3,
    },
]


class LeakFinderScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.data_driven = False
        self.all_leaks = []
        self._selected_leak: dict | None = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        title = QLabel("Leak Finder")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_btn = QPushButton("↻ Refresh")
        self.refresh_btn.clicked.connect(self.reload)
        header.addWidget(self.refresh_btn)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort by EV Lost", "Sort by Severity", "Sort by Category", "Sort by Sample Size"])
        self.sort_combo.currentTextChanged.connect(self._render)
        self.category_filter = QComboBox()
        self.category_filter.currentTextChanged.connect(self._render)
        header.addWidget(self.sort_combo)
        header.addWidget(self.category_filter)
        layout.addLayout(header)

        # Data-source banner (real vs example catalog)
        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setObjectName("Muted")
        layout.addWidget(self.banner)

        # GTO progress trend strip (son N gün doğruluk eğilimi)
        self.trend_label = QLabel()
        self.trend_label.setWordWrap(True)
        self.trend_label.setTextFormat(Qt.TextFormat.RichText)
        self.trend_label.setStyleSheet(
            "font-family:'JetBrains Mono',Menlo,monospace; font-size:11px;")
        layout.addWidget(self.trend_label)

        # Summary stats (MetricCards refreshed in _render via _update_summary)
        self.stats_grid = QGridLayout()
        self.metric_ev = MetricCard("Total EV Lost", "0.0bb", "0 leaks detected", "Red")
        self.metric_crit = MetricCard("Critical Leaks", "0", "fix immediately", "Red")
        self.metric_high = MetricCard("High Severity", "0", "fix this week", "Amber")
        self.metric_hands = MetricCard("Hands Analyzed", "0", "play to gather data", "Green")
        self.stats_grid.addWidget(self.metric_ev, 0, 0)
        self.stats_grid.addWidget(self.metric_crit, 0, 1)
        self.stats_grid.addWidget(self.metric_high, 0, 2)
        self.stats_grid.addWidget(self.metric_hands, 0, 3)
        layout.addLayout(self.stats_grid)

        # Leak table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Leak", "Severity", "Category", "EV Lost", "Deviation", "Sample"])
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._select_leak)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        _hdr = self.table.horizontalHeader()
        _hdr.setStretchLastSection(False)
        _hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)        # Leak name fills
        for _c in (1, 2, 3, 4, 5):
            _hdr.setSectionResizeMode(_c, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Detail panel
        self.detail_frame = QFrame()
        self.detail_frame.setObjectName("DataPanel")
        detail_layout = QVBoxLayout(self.detail_frame)
        self.detail_title = QLabel("Select a leak to see details")
        self.detail_title.setObjectName("SectionTitle")
        self.detail_why = QLabel()
        self.detail_why.setWordWrap(True)
        self.detail_why.setObjectName("Muted")
        self.detail_fix = QLabel()
        self.detail_fix.setWordWrap(True)
        self.detail_fix.setObjectName("Green")

        # Hangi uzun-vade Playbook ilkesini ihlal ettiğini gösterir
        self.detail_playbook = QLabel()
        self.detail_playbook.setWordWrap(True)
        self.detail_playbook.setStyleSheet(
            "color:#5ad1ce; font-size:12px; padding-top:4px;")

        # Repair plan visualization
        self.repair_bar = QProgressBar()
        self.repair_bar.setRange(0, 100)
        self.repair_bar.setValue(0)
        self.repair_bar.setFormat("Repair: 0%")

        btn_row = QHBoxLayout()
        repair_btn = QPushButton("🔧 Hatalarımdan Drill Üret")
        repair_btn.setObjectName("PrimaryButton")
        repair_btn.setToolTip("Tüm gerçek leak'lerinden ağırlıklı bir tamir "
                              "paketi üret (ağır leak → daha çok tekrar).")
        repair_btn.clicked.connect(self._create_repair_pack)
        drill_btn = QPushButton("Seçili Leak → Drill")
        drill_btn.clicked.connect(self._create_drill)
        combat_btn = QPushButton("Start Combat Repair")
        combat_btn.clicked.connect(lambda: self.navigate_requested.emit("Combat Trainer"))
        coach_btn = QPushButton("Ask AI Coach")
        coach_btn.clicked.connect(self._ask_coach)
        self.playbook_btn = QPushButton("📖 Playbook'u Aç")
        self.playbook_btn.setToolTip("Bu leak'in ihlal ettiği uzun-vade ilkeyi "
                                     "Strategy Playbook'ta aç.")
        self.playbook_btn.clicked.connect(
            lambda: self.navigate_requested.emit("Strategy Playbook"))
        btn_row.addWidget(repair_btn)
        btn_row.addWidget(drill_btn)
        btn_row.addWidget(combat_btn)
        btn_row.addWidget(coach_btn)
        btn_row.addWidget(self.playbook_btn)

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_why)
        detail_layout.addWidget(self.detail_fix)
        detail_layout.addWidget(self.detail_playbook)
        detail_layout.addWidget(self.repair_bar)
        detail_layout.addLayout(btn_row)
        layout.addWidget(self.detail_frame)

        self.reload()

    # ── Data loading ────────────────────────────────────────────────────
    def reload(self) -> None:
        """Gerçek el verisinden leak'leri yeniden yükle (Refresh / ekran açılış)."""
        self._load_leaks()
        # Kategori filtresini mevcut leak'lere göre güncelle
        cats = sorted({l["category"] for l in self.all_leaks})
        cur = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItems(["All Categories"] + cats)
        idx = self.category_filter.findText(cur)
        self.category_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.category_filter.blockSignals(False)
        self._update_summary()
        self._update_trend()
        self._render()

    def _update_trend(self) -> None:
        """GTO ilerleme şeridi — son günlerin doğruluk eğilimi (sparkline)."""
        try:
            from app.db.repository import get_gto_accuracy_trend
            trend = get_gto_accuracy_trend(days=14)
        except Exception:
            trend = []
        if not trend:
            self.trend_label.setText(
                "<span style='color:#898d80'>GTO İLERLEME: henüz veri yok — "
                "Real Experience Mode'da el oyna, gün gün doğruluğun burada "
                "görünecek.</span>")
            return
        blocks = "▁▂▃▄▅▆▇█"
        spark = "".join(
            blocks[min(7, int(d["accuracy"] / 12.5))] for d in trend
        )
        first = trend[0]["accuracy"]
        last = trend[-1]["accuracy"]
        delta = last - first
        if delta > 3:
            arrow, acol = "↑", "#5ad17a"
        elif delta < -3:
            arrow, acol = "↓", "#e87474"
        else:
            arrow, acol = "→", "#d6c668"
        today = trend[-1]
        self.trend_label.setText(
            f"<span style='color:#5ad1ce; font-weight:700'>GTO İLERLEME</span> "
            f"<span style='color:#898d80'>(son {len(trend)} gün)</span>  "
            f"<span style='color:#5ad17a'>{spark}</span>  "
            f"<span style='color:{acol}; font-weight:700'>%{first:.0f} → "
            f"%{last:.0f} {arrow}</span>  "
            f"<span style='color:#898d80'>· bugün {today['decisions']} karar · "
            f"ort. EV kaybı {today['avg_ev_loss']:.1f}bb</span>"
        )

    def _load_leaks(self) -> None:
        """get_leak_analysis() → tablo leak'leri. Veri yoksa örnek katalog."""
        try:
            raw = get_leak_analysis()
        except Exception:
            raw = []
        # "Info" placeholder'ları (Not enough data / No major leaks) gerçek leak değil
        real = [r for r in raw if r.get("severity") not in (None, "Info")]
        if real:
            self.data_driven = True
            self.all_leaks = [_normalize_leak(r) for r in real]
            info = next((r for r in raw if r.get("severity") == "Info"), None)
            extra = f"  {info['detail']}" if info else ""
            self.banner.setText(
                f"✅  Gerçek oyun verinden {len(self.all_leaks)} leak tespit edildi."
                f"{extra}  ·  Daha çok el oyna, analiz keskinleşir."
            )
        else:
            self.data_driven = False
            self.all_leaks = [_normalize_leak(r) for r in EXTENDED_LEAKS]
            info = next((r for r in raw if r.get("severity") == "Info"), None)
            note = info["detail"] if info else "Daha fazla el oyna."
            self.banner.setText(
                f"ⓘ  Henüz yeterli veri yok — aşağıdakiler ÖRNEK katalog (gerçek "
                f"sonuçların değil). {note}  Play Session / Tournament'ta el oyna, "
                f"sonra ↻ Refresh'e bas."
            )

    def _update_summary(self) -> None:
        total_ev = sum(l["ev_lost"] for l in self.all_leaks)
        critical = sum(1 for l in self.all_leaks if l["severity"] == "Critical")
        high = sum(1 for l in self.all_leaks if l["severity"] == "High")
        try:
            hands = get_player_stats().get("total_hands", 0)
        except Exception:
            hands = 0
        src = "from your hands" if self.data_driven else "example catalog"
        self.metric_ev.set_value(f"{total_ev:.1f}bb")
        self.metric_ev.set_detail(f"{len(self.all_leaks)} leaks · {src}")
        self.metric_crit.set_value(str(critical))
        self.metric_high.set_value(str(high))
        self.metric_hands.set_value(str(hands))
        self.metric_hands.set_detail(
            "data-driven" if self.data_driven else "play to gather data")

    def _get_filtered_leaks(self) -> list[dict]:
        category = self.category_filter.currentText()
        filtered = self.all_leaks
        if category != "All Categories":
            filtered = [l for l in filtered if l["category"] == category]

        sort_key = self.sort_combo.currentText()
        if "EV" in sort_key:
            filtered = sorted(filtered, key=lambda l: l["ev_lost"], reverse=True)
        elif "Severity" in sort_key:
            order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            filtered = sorted(filtered, key=lambda l: order.get(l["severity"], 9))
        elif "Category" in sort_key:
            filtered = sorted(filtered, key=lambda l: l["category"])
        elif "Sample" in sort_key:
            filtered = sorted(filtered, key=lambda l: l["sample_size"], reverse=True)
        return filtered

    def _render(self) -> None:
        filtered = self._get_filtered_leaks()
        self.table.setRowCount(len(filtered))
        self.table.setProperty("filtered_leaks", filtered)
        for row, leak in enumerate(filtered):
            self.table.setItem(row, 0, QTableWidgetItem(leak["name"]))
            severity_item = QTableWidgetItem(leak["severity"])
            self.table.setItem(row, 1, severity_item)
            self.table.setItem(row, 2, QTableWidgetItem(leak["category"]))
            self.table.setItem(row, 3, QTableWidgetItem(f"{leak['ev_lost']:.1f}bb"))
            self.table.setItem(row, 4, QTableWidgetItem(leak["frequency_deviation"]))
            n = leak.get("sample_size", 0)
            self.table.setItem(row, 5, QTableWidgetItem(f"{n} hands" if n else "—"))

    def _select_leak(self, row: int, _col: int) -> None:
        filtered = self.table.property("filtered_leaks") or self.all_leaks
        if row < len(filtered):
            leak = filtered[row]
            self._selected_leak = leak
            self.detail_title.setText(f"{leak['name']} | {leak['severity']} | {leak['category']}")
            n = leak.get("sample_size", 0)
            ev = leak.get("ev_lost", 0)
            meta = f"Sample: {n} hands" if n else "Sample: —"
            if ev:
                meta += f" | EV lost: {ev:.1f}bb"
            self.detail_why.setText(f"Why: {leak['why']}\n\n{meta}")
            self.detail_fix.setText(f"Fix: {leak['fix']}")
            pb = leak.get("playbook")
            if pb:
                fmt = "MTT" if pb["format"] == "mtt" else "Cash"
                self.detail_playbook.setText(
                    f"📖 İhlal edilen ilke — Playbook ({fmt}) → {pb['section']}\n"
                    f"    {pb['principle']}")
                self.playbook_btn.setEnabled(True)
            else:
                self.detail_playbook.setText("")
                self.playbook_btn.setEnabled(False)
            self.repair_bar.setFormat("Combat repair plan available")
            self.repair_bar.setValue(0)

    def _create_repair_pack(self) -> None:
        """Tüm gerçek leak'lerden ağırlıklı tamir paketi üret (spaced-rep)."""
        leaks = [l for l in self.all_leaks if l.get("severity") in
                 ("Critical", "High", "Medium")]
        if not leaks:
            self.coach_message.emit(
                "Drill üretecek leak yok. Önce birkaç el oyna (Play/Tournament), "
                "sonra ↻ Refresh ile leak analizi oluştur."
            )
            return
        lib = DrillLibrary.instance()
        pack = lib.generate_repair_pack(leaks)
        if not self.data_driven:
            note = " (örnek katalogdan — gerçek veri için daha çok el oyna)"
        else:
            note = " (gerçek oyun hatalarından)"
        names = ", ".join(dict.fromkeys(l["name"] for l in leaks[:3]))
        self.coach_message.emit(
            f"🔧 {len(pack)} drill'lik tamir paketi oluşturuldu{note}. Ağır "
            f"leak'lere daha çok tekrar düştü. Öncelik: {names}. "
            "Spot Practice Trainer → Drill Library'de seni bekliyor!"
        )
        self.navigate_requested.emit("Spot Practice Trainer")

    def _create_drill(self) -> None:
        leak = self._selected_leak
        if leak is None:
            self.coach_message.emit(
                "Önce tabloda bir leak seç, sonra 'Seçili Leak → Drill' butonuna bas."
            )
            return
        lib = DrillLibrary.instance()
        new_drills = lib.generate_from_leak(leak)
        n = len(new_drills)
        self.coach_message.emit(
            f"✓  {n} yeni drill oluşturuldu: \"{leak['name']}\" leakine özel. "
            "Spot Practice Trainer → Drill Library'de seni bekliyor — oynayabilirsin!"
        )
        self.navigate_requested.emit("Spot Practice Trainer")

    def _ask_coach(self) -> None:
        leaks = self._get_filtered_leaks()
        if not leaks:
            self.coach_message.emit(
                "Henüz leak verisi yok. Play Session / Tournament'ta birkaç el oyna, "
                "sonra Leak Finder → ↻ Refresh ile analiz oluştur."
            )
            return
        top = leaks[:3]
        src = ("Gerçek oyun verinden" if self.data_driven
               else "Örnek katalogdan (henüz yeterli el yok)")
        lines = "  ".join(
            f"{i+1}) {l['name']} ({l['ev_lost']:.1f}bb, {l['severity']})"
            for i, l in enumerate(top)
        )
        self.coach_message.emit(
            f"{src} öncelikli leak'ler: {lines}.  "
            f"İlk hedef: \"{top[0]['name']}\" — {top[0]['fix']}  "
            "Günde 30dk leak-specific drill + 20dk hand review öner."
        )
