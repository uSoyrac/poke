from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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
from app.db.seed_data import leaks
from app.ui.components.leak_card import LeakCard
from app.ui.components.metric_card import MetricCard


# Extended leak catalog matching the prompt's full list
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
        self.all_leaks = EXTENDED_LEAKS

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
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Sort by EV Lost", "Sort by Severity", "Sort by Category", "Sort by Sample Size"])
        self.sort_combo.currentTextChanged.connect(self._render)
        self.category_filter = QComboBox()
        categories = sorted(set(l["category"] for l in self.all_leaks))
        self.category_filter.addItems(["All Categories"] + categories)
        self.category_filter.currentTextChanged.connect(self._render)
        header.addWidget(self.sort_combo)
        header.addWidget(self.category_filter)
        layout.addLayout(header)

        # Summary stats
        stats = QGridLayout()
        total_ev = sum(l["ev_lost"] for l in self.all_leaks)
        critical = sum(1 for l in self.all_leaks if l["severity"] == "Critical")
        high = sum(1 for l in self.all_leaks if l["severity"] == "High")
        stats.addWidget(MetricCard("Total EV Lost", f"{total_ev:.1f}bb", f"{len(self.all_leaks)} leaks detected", "Red"), 0, 0)
        stats.addWidget(MetricCard("Critical Leaks", str(critical), "fix immediately", "Red"), 0, 1)
        stats.addWidget(MetricCard("High Severity", str(high), "fix this week", "Amber"), 0, 2)
        stats.addWidget(MetricCard("Repair Progress", "0%", "start repair drills", "Green"), 0, 3)
        layout.addLayout(stats)

        # Leak table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Leak", "Severity", "Category", "EV Lost", "Deviation", "Repair Days"])
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._select_leak)
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

        # Repair plan visualization
        self.repair_bar = QProgressBar()
        self.repair_bar.setRange(0, 100)
        self.repair_bar.setValue(0)
        self.repair_bar.setFormat("Repair: 0%")

        btn_row = QHBoxLayout()
        drill_btn = QPushButton("Create Drill Pack")
        drill_btn.setObjectName("PrimaryButton")
        drill_btn.clicked.connect(self._create_drill)
        combat_btn = QPushButton("Start Combat Repair")
        combat_btn.clicked.connect(lambda: self.navigate_requested.emit("Combat Trainer"))
        coach_btn = QPushButton("Ask AI Coach")
        coach_btn.clicked.connect(self._ask_coach)
        btn_row.addWidget(drill_btn)
        btn_row.addWidget(combat_btn)
        btn_row.addWidget(coach_btn)

        detail_layout.addWidget(self.detail_title)
        detail_layout.addWidget(self.detail_why)
        detail_layout.addWidget(self.detail_fix)
        detail_layout.addWidget(self.repair_bar)
        detail_layout.addLayout(btn_row)
        layout.addWidget(self.detail_frame)

        self._render()

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
            self.table.setItem(row, 5, QTableWidgetItem(f"{leak['repair_days']} days"))

    def _select_leak(self, row: int, _col: int) -> None:
        filtered = self.table.property("filtered_leaks") or self.all_leaks
        if row < len(filtered):
            leak = filtered[row]
            self.detail_title.setText(f"{leak['name']} | {leak['severity']} | {leak['category']}")
            self.detail_why.setText(f"Why: {leak['why']}\n\nSample size: {leak['sample_size']} decisions | EV lost: {leak['ev_lost']:.1f}bb")
            self.detail_fix.setText(f"Fix: {leak['fix']}")
            self.repair_bar.setFormat(f"Repair plan: {leak['repair_days']} days")
            self.repair_bar.setValue(0)

    def _create_drill(self) -> None:
        self.coach_message.emit(
            "Leak repair drill pack oluşturuldu. 20 spot seçildi: leak kategorisine uygun "
            "board texture, pozisyon ve pot type ile filtrelendi. Spot Trainer'da hazır."
        )

    def _ask_coach(self) -> None:
        self.coach_message.emit(
            "Leak analizi: En büyük EV kaybı river overbluff (26.2bb). "
            "Öncelik sırası: 1) River bluff disiplini 2) BB defend genişletme 3) ICM call-off sıkılaştırma. "
            "7 günlük repair planı önerisi: günde 30dk leak-specific drill + 20dk hand review."
        )
