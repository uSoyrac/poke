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
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.ui.components.metric_card import MetricCard


PLAN_TEMPLATES = {
    "90-day world-class training plan": {
        "description": "Kapsamlı 90 günlük program: preflop → postflop → ICM → exploit. Her ay farklı odak.",
        "weeks": [
            {"week": "Week 1-2", "focus": "Preflop Foundation", "blocks": ["30dk range trainer", "20dk math reflex", "20dk fast play", "10dk AI coach"], "target": "Preflop accuracy >80%"},
            {"week": "Week 3-4", "focus": "Flop Strategy", "blocks": ["30dk postflop trainer", "20dk cbet discipline", "20dk hand review", "10dk leak check"], "target": "Flop accuracy >70%"},
            {"week": "Week 5-6", "focus": "Turn Mastery", "blocks": ["30dk turn barrel drill", "20dk probe/delay cbet", "20dk simulator", "10dk coach review"], "target": "Turn EV loss <0.5bb"},
            {"week": "Week 7-8", "focus": "River Decisions", "blocks": ["30dk river trainer", "20dk blocker analysis", "20dk thin value pack", "10dk MDF drill"], "target": "River score >75%"},
            {"week": "Week 9-10", "focus": "ICM & Tournament", "blocks": ["30dk ICM trainer", "20dk bubble drills", "20dk final table sim", "10dk push/fold"], "target": "ICM discipline >80%"},
            {"week": "Week 11-12", "focus": "Exploit & Integrate", "blocks": ["30dk combat packs", "20dk hand analyzer", "20dk bot volume", "10dk weekly review"], "target": "Skill score >800"},
        ],
    },
    "MTT low stakes crusher": {
        "description": "MTT odaklı program: stack management, ICM, bubble play, final table pressure.",
        "weeks": [
            {"week": "Week 1", "focus": "MTT Preflop Adjustments", "blocks": ["30dk MTT range trainer", "20dk short stack push/fold", "20dk tournament sim"], "target": "Push/fold accuracy >85%"},
            {"week": "Week 2", "focus": "ICM Awareness", "blocks": ["30dk ICM trainer", "20dk bubble scenarios", "20dk pay jump analysis"], "target": "Zero ICM punts"},
            {"week": "Week 3", "focus": "Final Table", "blocks": ["30dk final table sim", "20dk HU practice", "20dk big stack pressure"], "target": "FT score >70%"},
            {"week": "Week 4", "focus": "Volume & Review", "blocks": ["30dk fast play MTT", "20dk hand review", "20dk leak repair"], "target": "50+ tournament spots reviewed"},
        ],
    },
    "River decision repair": {
        "description": "River kararlarını düzeltmeye odaklı yoğun program.",
        "weeks": [
            {"week": "Week 1", "focus": "Bluff-catch Discipline", "blocks": ["30dk river trainer", "20dk MDF drills", "20dk blocker analysis"], "target": "Bluff-catch accuracy >65%"},
            {"week": "Week 2", "focus": "Thin Value & Sizing", "blocks": ["30dk thin value pack", "20dk overbet response", "20dk block bet drill"], "target": "Thin value spots identified"},
            {"week": "Week 3", "focus": "Bluff Selection", "blocks": ["30dk river bluff drill", "20dk unblocker analysis", "20dk combat pack"], "target": "Bluff frequency within 5% of solver"},
        ],
    },
    "Preflop bootcamp": {
        "description": "Preflop range'leri ve 3bet/4bet dinamiklerini öğrenmeye odaklı.",
        "weeks": [
            {"week": "Day 1-2", "focus": "RFI Ranges", "blocks": ["30dk range trainer RFI", "20dk position drills", "10dk math reflex"], "target": "All RFI ranges memorized"},
            {"week": "Day 3-4", "focus": "BB Defense", "blocks": ["30dk BB defend trainer", "20dk SB strategy", "10dk fold equity drills"], "target": "BB defend within 5% of solver"},
            {"week": "Day 5-6", "focus": "3Bet Dynamics", "blocks": ["30dk 3bet trainer", "20dk squeeze drills", "10dk cold call analysis"], "target": "3bet frequency calibrated"},
            {"week": "Day 7", "focus": "Integration", "blocks": ["30dk mixed preflop quiz", "20dk fast play", "10dk review"], "target": "Preflop accuracy >85%"},
        ],
    },
    "ICM bootcamp": {
        "description": "ICM, bubble play, pay jump ve PKO bounty hesaplaması yoğun programı.",
        "weeks": [
            {"week": "Day 1-2", "focus": "ICM Fundamentals", "blocks": ["30dk ICM theory drills", "20dk risk premium calc", "10dk push/fold"], "target": "ICM concepts mastered"},
            {"week": "Day 3-4", "focus": "Bubble Mastery", "blocks": ["30dk bubble sim", "20dk medium stack decisions", "10dk satellite bubble"], "target": "Zero bubble punts"},
            {"week": "Day 5-6", "focus": "Final Table & PKO", "blocks": ["30dk final table sim", "20dk PKO bounty calc", "10dk HU pressure"], "target": "FT ICM discipline >80%"},
            {"week": "Day 7", "focus": "Review & Test", "blocks": ["30dk ICM quiz", "20dk tournament sim", "10dk AI coach review"], "target": "ICM bootcamp complete"},
        ],
    },
    "Math bootcamp": {
        "description": "Pot odds, Alpha, MDF, EV, Bayes ve combo counting yoğun matemek programı.",
        "weeks": [
            {"week": "Day 1-2", "focus": "Pot Odds & Alpha", "blocks": ["30dk pot odds trainer", "20dk alpha drill", "10dk speed calc"], "target": "Math reflex >85%"},
            {"week": "Day 3-4", "focus": "MDF & EV", "blocks": ["30dk MDF trainer", "20dk EV calculator", "10dk break-even drill"], "target": "MDF/EV within 3% accuracy"},
            {"week": "Day 5-6", "focus": "Combos & Blockers", "blocks": ["30dk combo counter", "20dk blocker trainer", "10dk range removal"], "target": "Combo counting <5sec"},
            {"week": "Day 7", "focus": "Bayes & Integration", "blocks": ["30dk Bayes update drill", "20dk mixed math quiz", "10dk variance sim"], "target": "Math bootcamp complete"},
        ],
    },
    "Leak repair week": {
        "description": "En büyük 3 leak'e odaklı 7 günlük yoğun tamir programı.",
        "weeks": [
            {"week": "Day 1-2", "focus": "Leak #1: River Overbluff", "blocks": ["30dk river bluff discipline", "20dk calling station exploit", "10dk blocker review"], "target": "Overbluff freq -10%"},
            {"week": "Day 3-4", "focus": "Leak #2: BB Underdefend", "blocks": ["30dk BB defend expansion", "20dk suited gapper drills", "10dk wheel ace practice"], "target": "BB defend +8%"},
            {"week": "Day 5-6", "focus": "Leak #3: ICM Call-off", "blocks": ["30dk ICM call-off tightening", "20dk risk premium practice", "10dk pay jump awareness"], "target": "ICM punts = 0"},
            {"week": "Day 7", "focus": "Validation", "blocks": ["30dk mixed leak test", "20dk hand review", "10dk AI coach summary"], "target": "All 3 leaks improved"},
        ],
    },
}


class StudyPlannerScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        from app.ui.components.poke import PokePageHeader as _PokePageHeader
        page_header = _PokePageHeader(
            num="25 / Study Plan",
            title="Plan your <em>week</em>.",
            sub="Pick a 7-day template · daily focus · trackable targets.",
        )
        root.addWidget(page_header)

        # Plan controls row
        header = QHBoxLayout()
        self.plan_type = QComboBox()
        self.plan_type.addItems(list(PLAN_TEMPLATES.keys()))
        self.plan_type.currentTextChanged.connect(self.render)
        regenerate = QPushButton("Generate Personal Plan")
        regenerate.setObjectName("PrimaryButton")
        regenerate.clicked.connect(self.render)
        start_btn = QPushButton("Start Today's Session")
        start_btn.setObjectName("SuccessButton")
        start_btn.clicked.connect(lambda: self.navigate_requested.emit("Spot Practice Trainer"))
        header.addWidget(self.plan_type)
        header.addWidget(regenerate)
        header.addWidget(start_btn)
        root.addLayout(header)

        # Plan description
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("Muted")
        root.addWidget(self.description)

        # Progress overview
        progress_row = QGridLayout()
        self.prog_overall = MetricCard("Overall Progress", "0%", "just started", "Cyan")
        self.prog_week = MetricCard("Current Week", "Week 1", "in progress", "Green")
        self.prog_drills = MetricCard("Drills Target", "35/day", "maintain pace")
        self.prog_ev = MetricCard("EV Loss Target", "<20bb/100", "per decision", "Amber")
        progress_row.addWidget(self.prog_overall, 0, 0)
        progress_row.addWidget(self.prog_week, 0, 1)
        progress_row.addWidget(self.prog_drills, 0, 2)
        progress_row.addWidget(self.prog_ev, 0, 3)
        root.addLayout(progress_row)

        # Schedule scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.schedule_body = QWidget()
        self.schedule_layout = QVBoxLayout(self.schedule_body)
        scroll.setWidget(self.schedule_body)
        root.addWidget(scroll, 1)

        self.render()

    def render(self) -> None:
        plan_name = self.plan_type.currentText()
        template = PLAN_TEMPLATES.get(plan_name, list(PLAN_TEMPLATES.values())[0])

        self.description.setText(f"📋 {plan_name}\n{template['description']}")

        # Clear schedule
        while self.schedule_layout.count():
            item = self.schedule_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Render weeks
        for idx, week in enumerate(template["weeks"]):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)

            # Week header
            week_header = QHBoxLayout()
            week_title = QLabel(f"{week['week']} — {week['focus']}")
            week_title.setObjectName("SectionTitle")
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(max(0, 100 - idx * 20))  # Demo progress
            progress.setFormat(f"{max(0, 100 - idx * 20)}%")
            progress.setMaximumWidth(150)
            week_header.addWidget(week_title, 1)
            week_header.addWidget(progress)
            card_layout.addLayout(week_header)

            # Blocks
            blocks_layout = QGridLayout()
            for bidx, block in enumerate(week["blocks"]):
                block_label = QLabel(f"• {block}")
                block_label.setObjectName("Cyan")
                blocks_layout.addWidget(block_label, bidx // 2, bidx % 2)
            card_layout.addLayout(blocks_layout)

            # Target
            target = QLabel(f"🎯 Target: {week['target']}")
            target.setObjectName("Green")
            card_layout.addWidget(target)

            self.schedule_layout.addWidget(card)

        self.schedule_layout.addStretch(1)

        # Update progress cards
        total_weeks = len(template["weeks"])
        current = min(1, total_weeks)
        _update_card(self.prog_week, f"Week {current}", f"of {total_weeks}")


def _update_card(card: MetricCard, value: str, detail: str) -> MetricCard:
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
        elif child.objectName() in ("Cyan", "Green", "Amber", "Red"):
            child.setText(detail)
    return card
