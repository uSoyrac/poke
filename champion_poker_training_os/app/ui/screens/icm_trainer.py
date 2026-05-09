from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.repository import save_decision_review
from app.poker.icm import (
    bubble_factor,
    chip_ev_vs_dollar_ev,
    malmuth_harville,
    push_fold_range_width,
    risk_premium,
)
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import compare_action
from app.training.decision_review import analyze_training_spot_decision
from app.ui.components.poker_table import PokerTableView
from app.ui.components.metric_card import MetricCard


# ICM-specific drill data
ICM_SPOT_TYPES = [
    "10bb push/fold",
    "15-25bb rejam",
    "Bubble call/fold",
    "Final table call-off",
    "Big stack pressure",
    "Medium stack risk",
    "Short stack survival",
    "Satellite bubble",
    "PKO bounty call",
    "PKO bounty jam",
    "chipEV vs $EV divergence",
]


def _generate_icm_drills(count: int = 40) -> list[dict]:
    """Generate ICM-specific drills with proper payouts and stack distributions."""
    base = generate_spot_drills(count)
    drills = []
    payouts_sets = [
        [50, 30, 20],
        [40, 25, 18, 12, 5],
        [45, 27, 16, 8, 4],
        [100],  # satellite — winner takes all
        [35, 22, 16, 12, 8, 4, 3],
    ]
    for idx, spot in enumerate(base):
        stage = ["bubble", "final table", "PKO", "satellite", "chipEV"][idx % 5]
        spot_type = ICM_SPOT_TYPES[idx % len(ICM_SPOT_TYPES)]
        players_left = [9, 6, 4, 3, 2, 15, 25, 47][idx % 8]
        payouts = payouts_sets[idx % len(payouts_sets)]

        # Create realistic stack distributions
        hero_stack = [10, 15, 20, 25, 30, 40, 60, 8][idx % 8]
        avg_stack = 25 + (idx % 5) * 5
        stacks = [float(hero_stack)]
        for j in range(min(players_left - 1, 7)):
            stacks.append(float(avg_stack + ((idx + j) % 7 - 3) * 5))

        rp = risk_premium(hero_stack, avg_stack, stage)
        bf = bubble_factor(stacks, payouts, 0) if len(stacks) <= 6 else round(1.2 + idx * 0.05, 2)
        range_width = push_fold_range_width(hero_stack, stage)

        drills.append({
            **spot,
            "id": f"ICM-{idx + 1:03d}",
            "title": f"{spot_type}: {spot['position']} {hero_stack}bb {stage}",
            "stage": stage,
            "spot_type": spot_type,
            "players_left": players_left,
            "paid_places": max(1, players_left // 3),
            "risk_premium": rp,
            "bubble_factor": bf,
            "bounty_ev": round((idx % 4) * 0.35, 2) if stage == "PKO" else 0.0,
            "hero_stack_bb": hero_stack,
            "avg_stack_bb": avg_stack,
            "stacks": stacks,
            "payouts": payouts,
            "push_range_width": range_width,
            "options": ("fold", "call", "raise", "jam"),
            "best_action": ["fold", "jam", "call", "raise"][idx % 4],
        })
    return drills


class IcmTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = _generate_icm_drills(40)
        self.index = 0
        self.correct = 0
        self.total = 0
        self.icm_punts = 0

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
        title = QLabel("ICM / PKO Trainer")
        title.setObjectName("Title")
        header.addWidget(title)
        self.stage_filter = QComboBox()
        self.stage_filter.addItems(["All", "bubble", "final table", "PKO", "satellite", "chipEV"])
        self.stage_filter.currentTextChanged.connect(self._filter_changed)
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All"] + ICM_SPOT_TYPES[:6])
        self.type_filter.currentTextChanged.connect(self._filter_changed)
        header.addWidget(QLabel("Stage"))
        header.addWidget(self.stage_filter)
        header.addWidget(QLabel("Type"))
        header.addWidget(self.type_filter)
        layout.addLayout(header)

        # Stats cards
        stats = QGridLayout()
        self.card_accuracy = MetricCard("ICM Accuracy", "—", "decisions")
        self.card_punts = MetricCard("ICM Punts", "0", "avoid $EV mistakes", "Red")
        self.card_bf = MetricCard("Bubble Factor", "—", "current spot")
        self.card_rp = MetricCard("Risk Premium", "—", "current spot", "Amber")
        stats.addWidget(self.card_accuracy, 0, 0)
        stats.addWidget(self.card_punts, 0, 1)
        stats.addWidget(self.card_bf, 0, 2)
        stats.addWidget(self.card_rp, 0, 3)
        layout.addLayout(stats)

        # Main area: table + spot info
        main = QHBoxLayout()
        self.table = PokerTableView()
        main.addWidget(self.table, 2)

        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_info = QLabel()
        self.spot_info.setWordWrap(True)
        self.spot_info.setObjectName("Muted")
        self.icm_detail = QLabel()
        self.icm_detail.setWordWrap(True)
        self.icm_detail.setObjectName("Cyan")
        self.action_layout = QHBoxLayout()
        panel_layout.addWidget(self.spot_title)
        panel_layout.addWidget(self.spot_info)
        panel_layout.addWidget(self.icm_detail)
        panel_layout.addLayout(self.action_layout)
        main.addWidget(panel, 1)
        layout.addLayout(main)

        # ICM equity panel — real Malmuth-Harville math for current spot
        self.equity_card = QFrame()
        self.equity_card.setObjectName("Card")
        eq_layout = QVBoxLayout(self.equity_card)
        eq_layout.setContentsMargins(14, 12, 14, 12)
        eq_title = QLabel("📊 ICM Equity (Malmuth-Harville)")
        eq_title.setObjectName("SectionTitle")
        eq_layout.addWidget(eq_title)
        self.equity_grid = QGridLayout()
        eq_layout.addLayout(self.equity_grid)
        self.equity_summary = QLabel("")
        self.equity_summary.setWordWrap(True)
        self.equity_summary.setObjectName("Cyan")
        eq_layout.addWidget(self.equity_summary)
        layout.addWidget(self.equity_card)

        # Feedback
        self.feedback = QFrame()
        self.feedback.setObjectName("DataPanel")
        self.feedback_layout = QVBoxLayout(self.feedback)
        self.feedback_label = QLabel("ICM Trainer: Her spotta chipEV vs $EV farkını analiz et. Bubble pressure ve pay jump etkisini öğren.")
        self.feedback_label.setWordWrap(True)
        self.feedback_label.setObjectName("Green")
        self.feedback_layout.addWidget(self.feedback_label)
        layout.addWidget(self.feedback)

        self.load_spot()

    def _filter_changed(self) -> None:
        stage = self.stage_filter.currentText()
        stype = self.type_filter.currentText()
        filtered = _generate_icm_drills(40)
        if stage != "All":
            filtered = [d for d in filtered if d["stage"] == stage]
        if stype != "All":
            filtered = [d for d in filtered if d["spot_type"] == stype]
        if filtered:
            self.drills = filtered
            self.index = 0
            self.load_spot()

    def _render_icm_equity(self, spot: dict) -> None:
        """Compute and display real Malmuth-Harville $-equities for the current stack distribution."""
        # Clear existing rows
        while self.equity_grid.count():
            item = self.equity_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        stacks = list(spot.get("stacks") or [])
        payouts = list(spot.get("payouts") or [])
        if not stacks or not payouts:
            self.equity_summary.setText("Stack/payout data missing — equity unavailable.")
            return
        # Cap to first 8 players for performance
        if len(stacks) > 8:
            stacks = stacks[:8]
        equities = malmuth_harville(stacks, payouts)
        prize_pool = sum(payouts)
        hero_eq = equities[0] if equities else 0.0

        # Header row
        for col, txt in enumerate(["Seat", "Stack", "ICM $", "% of pool"]):
            lbl = QLabel(txt)
            lbl.setObjectName("Muted")
            self.equity_grid.addWidget(lbl, 0, col)
        for r, (stack, eq) in enumerate(zip(stacks, equities), start=1):
            seat_lbl = QLabel(f"Seat {r}" + (" (Hero)" if r == 1 else ""))
            seat_lbl.setObjectName("Cyan" if r == 1 else "Muted")
            stack_lbl = QLabel(f"{int(stack):,}")
            eq_lbl = QLabel(f"${eq:.2f}")
            eq_lbl.setObjectName("Green" if r == 1 else "Muted")
            pct_lbl = QLabel(f"{(eq / prize_pool * 100) if prize_pool else 0:.1f}%")
            pct_lbl.setObjectName("Amber")
            for col, w in enumerate([seat_lbl, stack_lbl, eq_lbl, pct_lbl]):
                self.equity_grid.addWidget(w, r, col)

        # Hero summary
        chip_share = stacks[0] / sum(stacks) if sum(stacks) else 0
        eq_share = hero_eq / prize_pool if prize_pool else 0
        compression = (eq_share - chip_share) * 100
        comp_label = (
            f"chipEV {chip_share*100:.1f}% / $EV {eq_share*100:.1f}% "
            f"({compression:+.1f}pp)"
        )
        if compression < -3:
            comp_label += " ← ICM compresses your chip lead — call-offs need extra equity."
        elif compression > 3:
            comp_label += " ← Short stack ICM premium working in your favour for jam decisions."
        self.equity_summary.setText(comp_label)

    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.table.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])
        self._render_icm_equity(spot)
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_info.setText(
            f"Players left: {spot['players_left']} | Paid: {spot['paid_places']} | "
            f"Hero: {spot['hero_stack_bb']}bb | Avg: {spot['avg_stack_bb']}bb | "
            f"Cards: {spot['hero_cards']} | Board: {spot['board'] or 'preflop'}"
        )
        self.icm_detail.setText(
            f"Risk Premium: {spot['risk_premium']:.1%} | Bubble Factor: {spot['bubble_factor']:.2f} | "
            f"Push Range: {spot['push_range_width']:.0%} | "
            f"Bounty EV: {spot['bounty_ev']:+.2f} | Stage: {spot['stage'].upper()}"
        )

        # Update stat cards
        self.card_bf = _update_card_text(self.card_bf, f"{spot['bubble_factor']:.2f}", f"{spot['stage']} pressure")
        self.card_rp = _update_card_text(self.card_rp, f"{spot['risk_premium']:.1%}", f"{spot['hero_stack_bb']}bb vs {spot['avg_stack_bb']}bb avg")

        _clear_layout(self.action_layout)
        for action in spot["options"]:
            button = QPushButton(action.upper())
            button.clicked.connect(lambda checked=False, a=action: self.decide(a))
            if action == "jam":
                button.setObjectName("DangerButton")
            elif action == "fold":
                button.setObjectName("")
            else:
                button.setObjectName("PrimaryButton")
            self.action_layout.addWidget(button)

    def decide(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        self.total += 1

        dollar_ev_loss = round(result["ev_loss"] * (1.0 + spot["risk_premium"] * 5), 2)
        review = analyze_training_spot_decision(
            spot,
            action,
            30000 + self.total,
            dollar_ev_loss=dollar_ev_loss,
            context="icm",
        )
        try:
            save_decision_review(review)
        except Exception:
            pass
        is_punt = dollar_ev_loss > 0.7

        if result["is_correct"]:
            self.correct += 1
        if is_punt:
            self.icm_punts += 1

        accuracy = f"{100 * self.correct / self.total:.0f}%" if self.total > 0 else "—"
        self.card_accuracy = _update_card_text(self.card_accuracy, accuracy, f"{self.total} decisions")
        self.card_punts = _update_card_text(self.card_punts, str(self.icm_punts), "avoid $EV mistakes")

        # Feedback
        self.feedback_label.setObjectName("Green" if not is_punt else "Red")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

        chip_ev_text = f"chipEV best: {result['best_action']}"
        icm_note = ""
        if spot["stage"] in ("bubble", "final table", "satellite"):
            icm_note = (
                f"\n⚠ ICM pressure active! Risk premium {spot['risk_premium']:.1%} means "
                f"chipEV calls need {spot['risk_premium']:.0%} extra equity. "
                f"Bubble factor {spot['bubble_factor']:.2f} — losing chips costs more than winning."
            )

        self.feedback_label.setText(
            f"Hero {action} | {chip_ev_text} | $EV loss: {dollar_ev_loss:.2f} | "
            f"{'✓ Good ICM decision' if not is_punt else '✗ ICM PUNT — review risk premium'} | "
            f"{review['verdict']} | Drill: {review['drill_target']}"
            f"{icm_note}"
        )

        self.coach_message.emit(
            explain_spot(spot, action)
            + "\n\nICM decision review:\n"
            + f"Hero {review['hero_action']} vs baseline {review['solver_action']} | "
            + f"$EV loss {review['ev_loss']:.2f} | Risk premium {spot['risk_premium']:.1%} | "
            + f"Drill: {review['drill_target']}"
        )
        self.index += 1
        self.load_spot()


def _update_card_text(card: MetricCard, value: str, detail: str) -> MetricCard:
    """Update MetricCard labels."""
    for child in card.findChildren(QLabel):
        if child.objectName() == "MetricValue":
            child.setText(value)
        elif child.objectName() in ("Cyan", "Green", "Amber", "Red"):
            child.setText(detail)
    return card


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
