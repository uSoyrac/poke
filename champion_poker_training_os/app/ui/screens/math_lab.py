from __future__ import annotations

import random
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.app_state import AppState
from app.db.seed_data import generate_math_drills


CATEGORY_LABELS = {
    "all": "All",
    "pot odds": "Pot Odds",
    "alpha": "Alpha (bluff freq)",
    "MDF": "MDF (defend freq)",
    "EV": "Expected Value",
    "Bayes": "Bayes Update",
}


class CategoryCard(QFrame):
    """Clickable filter card. Lights up when active."""

    clicked = Signal(str)

    def __init__(self, key: str, title: str, hint: str):
        super().__init__()
        self.key = key
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("SectionTitle")
        self.hint_lbl = QLabel(hint)
        self.hint_lbl.setObjectName("Muted")
        self.hint_lbl.setWordWrap(True)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.hint_lbl)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        self.active = active
        if active:
            self.setStyleSheet(
                "QFrame#Card { border: 1px solid #22D3EE; background: #1A2433; }"
            )
            self.title_lbl.setObjectName("Cyan")
        else:
            self.setStyleSheet("")
            self.title_lbl.setObjectName("SectionTitle")
        self.title_lbl.style().unpolish(self.title_lbl)
        self.title_lbl.style().polish(self.title_lbl)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.key)
        super().mousePressEvent(event)


class MathLabScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.setObjectName('MathLabScreenRoot')
        from app.ui.theme import poke_tokens as _pt_bg
        from PySide6.QtCore import Qt as _Qt_bg
        self.setAttribute(_Qt_bg.WA_StyledBackground, True)
        self.setStyleSheet(f"#MathLabScreenRoot {{ background: {_pt_bg.BG}; }}")
        self.state = state
        self.all_drills = generate_math_drills(60)
        self.active_category = "all"
        self.drills = list(self.all_drills)
        random.shuffle(self.drills)
        self.index = 0
        self.correct = 0
        self.answered = 0
        self.streak = 0
        self.best_streak = 0

        # Timer mode
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self.deadline: float | None = None
        self.time_limit = 0
        self.timed_correct = 0
        self.timed_total = 0

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

        from app.ui.components.poke import PokePageHeader as _PokePageHeader
        from app.ui.components.poke import PokeTag as _PokeTag
        self.streak_tag = _PokeTag("STREAK 0 · BEST 0", tone="g")
        page_header = _PokePageHeader(
            num="17 / Math Lab",
            title="Sharpen the <em>reflex</em>.",
            sub="MDF · pot odds · alpha · ICM math — solve under time pressure.",
            actions=self.streak_tag,
        )
        layout.addWidget(page_header)
        # Keep the streak_label name so downstream setters still work
        self.streak_label = self.streak_tag

        # Category filter cards
        cat_grid = QGridLayout()
        cat_grid.setHorizontalSpacing(10)
        cat_grid.setVerticalSpacing(10)
        self.cards: dict[str, CategoryCard] = {}
        cards_def = [
            ("all", "All", "Karışık 60 soruluk havuz"),
            ("pot odds", "Pot Odds", "Required equity to call"),
            ("alpha", "Alpha", "Required fold % for bluff"),
            ("MDF", "MDF", "Minimum defense vs bet"),
            ("EV", "EV", "Win% × reward − Lose% × risk"),
            ("Bayes", "Bayes", "Posterior after villain action"),
            ("combos", "Combos", "Pair=6, suited=4, offsuit=12"),
            ("variance", "Variance", "Bankroll & swings reflex"),
        ]
        for idx, (key, label, hint) in enumerate(cards_def):
            card = CategoryCard(key, label, hint)
            card.clicked.connect(self._set_category)
            cat_grid.addWidget(card, idx // 4, idx % 4)
            self.cards[key] = card
        self.cards["all"].set_active(True)
        layout.addLayout(cat_grid)

        # Quick-fire toggles
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Quick-fire:"))
        for seconds, label in [(0, "Off"), (10, "10s"), (20, "20s"), (40, "40s")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, s=seconds: self._set_timer(s))
            mode_row.addWidget(btn)
            if seconds == 0:
                btn.setChecked(True)
                self._timer_buttons = [btn]
            else:
                self._timer_buttons.append(btn)
        mode_row.addStretch(1)
        self.timer_label = QLabel("⏱ Off")
        self.timer_label.setObjectName("Muted")
        mode_row.addWidget(self.timer_label)
        layout.addLayout(mode_row)

        # Quiz panel
        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        self.prompt = QLabel()
        self.prompt.setObjectName("SectionTitle")
        self.prompt.setWordWrap(True)
        self.answer = QDoubleSpinBox()
        self.answer.setDecimals(3)
        self.answer.setRange(-1000, 1000)
        self.answer.setSingleStep(0.01)
        self.feedback = QLabel("Cevabı gir. Yüzde için ondalık kullan: 0.33 = %33.")
        self.feedback.setWordWrap(True)
        self.feedback.setObjectName("Muted")

        actions = QHBoxLayout()
        submit = QPushButton("Check Answer")
        submit.setObjectName("PrimaryButton")
        submit.clicked.connect(self.check)
        skip = QPushButton("Skip / Next")
        skip.clicked.connect(self.next_drill)
        similar = QPushButton("Similar 5 Questions")
        similar.clicked.connect(
            lambda: self.coach_message.emit(
                "Benzer 5 matematik sorusu sıraya alındı: aynı formül, farklı pot/risk değerleri."
            )
        )
        actions.addWidget(self.answer, 1)
        actions.addWidget(submit)
        actions.addWidget(skip)
        actions.addWidget(similar)

        panel_layout.addWidget(self.prompt)
        panel_layout.addLayout(actions)
        panel_layout.addWidget(self.feedback)
        layout.addWidget(panel)

        # Stats footer
        stats = QFrame()
        stats.setObjectName("Card")
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(14, 10, 14, 10)
        self.stat_answered = QLabel("Answered: 0")
        self.stat_correct = QLabel("Correct: 0")
        self.stat_score = QLabel("Math Reflex Score: —")
        self.stat_score.setObjectName("Green")
        for w in (self.stat_answered, self.stat_correct, self.stat_score):
            stats_layout.addWidget(w)
        stats_layout.addStretch(1)
        layout.addWidget(stats)

        layout.addStretch(1)
        self.next_drill()

    # --- handlers --------------------------------------------------------
    def _set_category(self, key: str) -> None:
        for k, card in self.cards.items():
            card.set_active(k == key)
        self.active_category = key
        if key in ("combos", "variance", "all"):
            self.drills = list(self.all_drills)
        else:
            self.drills = [d for d in self.all_drills if d["kind"] == key]
            if not self.drills:
                self.drills = list(self.all_drills)
        random.shuffle(self.drills)
        self.index = 0
        if key == "combos":
            self.feedback.setText(
                "Combos hatırlatma: pocket pair=6, offsuit unpaired=12, suited unpaired=4. "
                "Sadece okuma — sorular için Pot Odds/Alpha/MDF/EV kartlarını seç."
            )
        elif key == "variance":
            self.feedback.setText(
                "Variance pratiği için Reports → Bankroll panel + standart sapma hesabı önerilir. "
                "Hızlı refleks için Pot Odds/EV kartlarına dön."
            )
        else:
            self.next_drill()

    def _set_timer(self, seconds: int) -> None:
        self.time_limit = seconds
        for btn in self._timer_buttons:
            btn.setChecked(btn.text() == ("Off" if seconds == 0 else f"{seconds}s"))
        if seconds == 0:
            self.timer.stop()
            self.deadline = None
            self.timer_label.setText("⏱ Off")
        else:
            self.deadline = time.monotonic() + seconds
            self.timer_label.setText(f"⏱ {seconds}.0s")
            self.timer.start()

    def _tick(self) -> None:
        if self.deadline is None:
            return
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.timer_label.setText("⏱ 0.0s — time's up")
            self.timer.stop()
            self.feedback.setObjectName("Red")
            self.feedback.style().unpolish(self.feedback)
            self.feedback.style().polish(self.feedback)
            self.feedback.setText("Süre doldu — quick-fire kuralı: cevap saymıyor. Sonraki soruya geç.")
            self.streak = 0
            self.streak_label.setText(f"STREAK 0 · BEST {self.best_streak}")
            self.deadline = None
            return
        self.timer_label.setText(f"⏱ {remaining:0.1f}s")

    def _start_round_timer(self) -> None:
        if self.time_limit > 0:
            self.deadline = time.monotonic() + self.time_limit
            self.timer.start()

    def next_drill(self) -> None:
        if not self.drills:
            return
        drill = self.drills[self.index % len(self.drills)]
        self.prompt.setText(f"{drill['id']} | {CATEGORY_LABELS.get(drill['kind'], drill['kind']).title()}: {drill['prompt']}")
        self.answer.setValue(0)
        self.feedback.setObjectName("Muted")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText("Yeni soru hazır. Cevabı gir veya skip ile geç.")
        self._start_round_timer()

    def check(self) -> None:
        if not self.drills:
            return
        drill = self.drills[self.index % len(self.drills)]
        timed_out = self.time_limit > 0 and (self.deadline is None or self.deadline <= time.monotonic())
        if timed_out:
            ok = False
        else:
            value = self.answer.value()
            ok = abs(value - drill["answer"]) <= drill["tolerance"]

        self.timer.stop()
        self.deadline = None

        self.answered += 1
        if ok:
            self.correct += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0
        reflex = int(100 * self.correct / self.answered)
        self.feedback.setObjectName("Green" if ok else "Red")
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        verdict = "Correct" if ok else ("Time's up" if timed_out else "Review")
        self.feedback.setText(
            f"{verdict} | Answer {drill['answer']} | "
            f"Math Reflex Score {reflex}. {drill['explanation']}"
        )
        self.coach_message.emit(
            f"Math Coach: {drill['kind']} sorusunda doğru cevap {drill['answer']}. "
            f"{drill['explanation']} Bu refleksi offline geliştiriyoruz, masada karar vermek için değil."
        )
        self.stat_answered.setText(f"Answered: {self.answered}")
        self.stat_correct.setText(f"Correct: {self.correct}")
        self.stat_score.setText(f"Math Reflex Score: {reflex}")
        self.streak_label.setText(f"STREAK {self.streak} · BEST {self.best_streak}")
        self.state.completed_drills += 1

        self.index += 1
        # Auto-advance after a brief delay would be nice; for now wait for user click.

    # alias for backward-compat with original load() name
    def load(self) -> None:
        self.next_drill()
