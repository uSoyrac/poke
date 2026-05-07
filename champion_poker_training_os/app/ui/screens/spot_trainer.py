from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import compare_action, solve_spot
from app.training.trainer_scoring import score_decision, skill_label
from app.ui.components.action_chip import parse_action_string
from app.ui.components.oval_table import DEFAULT_POSITIONS_9, OvalTable
from app.ui.components.poker_table import PokerTableView
from app.ui.components.solver_bar import EVLossBadge, SolverFrequencyBar


SIZING_PRESETS = ["33%", "50%", "75%", "130%"]


def _spread_actions_for_spot(spot: dict[str, Any], rng: random.Random) -> dict[str, list[str]]:
    """Make a plausible action map per position from the spot's action_history string."""
    positions = ["LJ", "HJ", "CO", "BTN", "SB", "BB", "UTG", "UTG1"]
    history = spot.get("action_history", "") or ""
    tokens = parse_action_string(history)[:8]
    hero_pos = spot.get("position") or "BTN"
    if hero_pos not in positions:
        hero_pos = "BTN"

    layout: dict[str, list[str]] = {p: [] for p in positions}
    # Most positions fold preflop
    for p in positions:
        if p == hero_pos:
            continue
        layout[p] = ["F"] if rng.random() < 0.65 else []

    # Distribute the parsed history across hero + a few villains
    villain = rng.choice([p for p in positions if p != hero_pos and not layout[p]] or [hero_pos])
    if tokens:
        layout[hero_pos] = tokens
    else:
        layout[hero_pos] = ["R 2.3"]
    if villain != hero_pos:
        layout[villain] = ["C", "X", "B 25%", "C"][: max(1, len(tokens) - 1)]
    return {k: v for k, v in layout.items() if v}


class SpotTrainerScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.drills = generate_spot_drills(120)
        self.index = 0
        self.seed = random.randint(1, 99)
        self._rng = random.Random(self.seed)
        self.feedback_layout = QVBoxLayout()
        self.action_layout = QHBoxLayout()
        self.sizing_buttons: list[QPushButton] = []

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

        # --- Header ---
        header = QHBoxLayout()
        title = QLabel("Spot Practice Trainer")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch(1)
        for mode in ["Quick drill", "Timed mode", "Mistakes-only", "Boss battle"]:
            button = QPushButton(mode)
            button.clicked.connect(
                lambda checked=False, m=mode: self.coach_message.emit(
                    f"{m} aktif. Feedback demo solver ile üretilecek."
                )
            )
            header.addWidget(button)
        reroll = QPushButton("🎲 Reroll seed")
        reroll.clicked.connect(self._reroll)
        header.addWidget(reroll)
        layout.addLayout(header)

        # --- Top row: oval preview (left) + decision panel (right) ---
        top = QHBoxLayout()
        top.setSpacing(14)

        # Oval preview card
        preview_card = QFrame()
        preview_card.setObjectName("Card")
        pc_layout = QVBoxLayout(preview_card)
        pc_layout.setContentsMargins(14, 14, 14, 14)
        preview_label = QLabel("Preview")
        preview_label.setObjectName("Muted")
        pc_layout.addWidget(preview_label)
        self.oval = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=False)
        self.oval.set_dealer("BTN")
        self.oval.set_seed(self.seed)
        pc_layout.addWidget(self.oval, 1)
        # Sizing strip
        sz_row = QHBoxLayout()
        sz_row.addStretch(1)
        self.custom_sizing = QLineEdit()
        self.custom_sizing.setPlaceholderText("150")
        self.custom_sizing.setFixedWidth(70)
        sz_row.addWidget(QLabel("Custom %"))
        sz_row.addWidget(self.custom_sizing)
        sz_row.addSpacing(12)
        for s in SIZING_PRESETS:
            b = QPushButton(s)
            b.setStyleSheet(
                "QPushButton { background: #131A24; border: 1px solid #1E2733; "
                "border-radius: 7px; padding: 6px 12px; color: #E5E7EB; font-weight: 700; }"
                "QPushButton:hover { border-color: #22D3EE; color: #22D3EE; }"
            )
            b.clicked.connect(lambda _checked=False, val=s: self._sizing_clicked(val))
            sz_row.addWidget(b)
            self.sizing_buttons.append(b)
        pc_layout.addLayout(sz_row)
        top.addWidget(preview_card, 3)

        # Decision panel
        info = QFrame()
        info.setObjectName("DataPanel")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(14, 14, 14, 14)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_title.setWordWrap(True)
        self.spot_meta = QLabel()
        self.spot_meta.setWordWrap(True)
        self.spot_meta.setObjectName("Muted")
        self.action_history = QLabel()
        self.action_history.setWordWrap(True)
        self.action_history.setObjectName("Cyan")

        # Hero cards mini display via existing PokerTableView (kept for cards)
        self.cards_view = PokerTableView()
        self.cards_view.setMinimumHeight(160)

        info_layout.addWidget(self.spot_title)
        info_layout.addWidget(self.spot_meta)
        info_layout.addWidget(self.action_history)
        info_layout.addWidget(self.cards_view)
        info_layout.addLayout(self.action_layout)
        top.addWidget(info, 2)
        layout.addLayout(top)

        # --- Solver feedback area ---
        feedback = QFrame()
        feedback.setObjectName("DataPanel")
        feedback.setLayout(self.feedback_layout)
        layout.addWidget(feedback)

        self._apply_drill_filters()
        self.load_spot()

    # --- helpers ---------------------------------------------------------
    def _apply_drill_filters(self) -> None:
        filt = getattr(self.state, "drill_filters", None)
        if not filt:
            return
        positions = set(filt.get("positions") or [])
        starting = filt.get("starting_spot")
        preflop = filt.get("preflop_action")
        if positions:
            self.drills = [d for d in self.drills if d.get("position") in positions] or self.drills
        if starting and starting != "Custom":
            target = starting.lower()
            filtered = [d for d in self.drills if d.get("street", "").lower() == target]
            if filtered:
                self.drills = filtered
        if preflop and preflop != "Any":
            mapped = {
                "SRP": "single raised pot",
                "3-bet": "3bet pot",
                "4-bet": "4bet pot",
                "5-bet": "4bet pot",
                "Squeeze": "squeezed pot",
                "Limp": "limped pot",
                "Iso": "iso pot",
            }
            tag = mapped.get(preflop, "").lower()
            if tag:
                filtered = [d for d in self.drills if tag in (d.get("pot_type", "") or "").lower()]
                if filtered:
                    self.drills = filtered

    def _reroll(self) -> None:
        self.seed = random.randint(1, 99)
        self._rng = random.Random(self.seed)
        self.oval.set_seed(self.seed)
        # Jump to a random spot
        self.index = self._rng.randint(0, len(self.drills) - 1)
        self.load_spot()
        self.coach_message.emit(f"Seed {self.seed}: yeni rastgele spot yüklendi. RNG ile sapmaları test ediyoruz.")

    def _sizing_clicked(self, value: str) -> None:
        self.coach_message.emit(
            f"Sizing tercih: {value} — solver bu sizing'in EV/Frequency dağılımını yan panelde gösteriyor."
        )

    # --- core flow -------------------------------------------------------
    def load_spot(self) -> None:
        spot = self.drills[self.index % len(self.drills)]
        self.state.selected_spot = spot
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_meta.setText(
            f"{spot['format']} · {spot['table']} · {spot['pot_type']} · "
            f"{spot['stack_bb']}bb · {spot['board_texture']} · ICM {spot['icm']}"
        )
        self.action_history.setText(spot["action_history"])
        self.cards_view.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])

        # Update oval preview
        self.oval.set_actions(_spread_actions_for_spot(spot, self._rng))
        self.oval.set_hero(spot.get("position", "BTN"))
        # Show face-down community on flop/turn/river
        comm: list[str] = []
        if spot.get("street") == "flop":
            comm = ["W", "W", "W"]
        elif spot.get("street") == "turn":
            comm = ["W", "W", "W", "W"]
        elif spot.get("street") == "river":
            comm = ["W", "W", "W", "W", "W"]
        self.oval.set_community_cards(comm)
        # SPR / pot odds approximation
        spr = round(spot.get("stack_bb", 100) / max(spot.get("pot_bb", 1), 1), 1)
        po = round(100 * 0.33 / (1 + 2 * 0.33), 1)  # rough placeholder for default 33% bet pot odds
        self.oval.set_spr_po(spr=spr, po=po)

        _clear_layout(self.action_layout)
        for action in spot["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self.answer(a))
            self.action_layout.addWidget(button)
        self._show_solver_preview(spot)

    def answer(self, action: str) -> None:
        spot = self.drills[self.index % len(self.drills)]
        result = compare_action(spot, action)
        score = score_decision(result["ev_loss"], result["solver_frequency"])
        self.state.record_decision(
            result["is_correct"], result["ev_loss"],
            f"{spot['id']} {action}: -{result['ev_loss']:.2f}bb",
        )
        self._show_feedback(spot, result, score)
        self.coach_message.emit(explain_spot(spot, action))
        self.index += 1

    def _show_solver_preview(self, spot: dict) -> None:
        _clear_layout(self.feedback_layout)
        title = QLabel("Solver Baseline Preview")
        title.setObjectName("SectionTitle")
        self.feedback_layout.addWidget(title)
        result = solve_spot(spot)
        grid = QGridLayout()
        for idx, action in enumerate(result.actions):
            grid.addWidget(
                SolverFrequencyBar(action.action, action.frequency, action.ev, action.sizing),
                idx // 4, idx % 4,
            )
        self.feedback_layout.addLayout(grid)
        confidence = QLabel(f"Source confidence: {result.source_confidence}")
        confidence.setObjectName("Amber" if "Mock" in result.source_confidence else "Green")
        self.feedback_layout.addWidget(confidence)

    def _show_feedback(self, spot: dict, result: dict, score: int) -> None:
        _clear_layout(self.feedback_layout)
        row = QHBoxLayout()
        row.addWidget(EVLossBadge(result["ev_loss"]))
        verdict = QLabel(
            f"Hero {result['hero_action']} | Best {result['best_action']} | "
            f"Hero EV {result['hero_ev']:+.2f} | Score {score} ({skill_label(score)})"
        )
        verdict.setObjectName("Green" if result["is_correct"] else "Red")
        row.addWidget(verdict, 1)
        next_button = QPushButton("Next Spot")
        next_button.setObjectName("PrimaryButton")
        next_button.clicked.connect(self.load_spot)
        retry_button = QPushButton("Retry Similar 5")
        retry_button.clicked.connect(
            lambda: self.coach_message.emit(
                "Benzer 5 spot drill pack'e eklendi: aynı street, benzer pot type, farklı blocker."
            )
        )
        row.addWidget(retry_button)
        row.addWidget(next_button)
        self.feedback_layout.addLayout(row)
        self.feedback_layout.addWidget(QLabel(result["sizing_feedback"]))
        grid = QGridLayout()
        for idx, action in enumerate(result["solver"]["actions"]):
            grid.addWidget(
                SolverFrequencyBar(
                    action["action"], action["frequency"], action["ev"], action.get("sizing", "")
                ),
                idx // 4, idx % 4,
            )
        self.feedback_layout.addLayout(grid)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget:
            widget.deleteLater()
        if child_layout:
            _clear_layout(child_layout)
