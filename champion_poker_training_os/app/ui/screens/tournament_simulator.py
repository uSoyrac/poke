from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.simulator.mtt_engine import TournamentEngine
from app.ui.components.poker_table import PokerTableView


class TournamentSimulatorScreen(QWidget):
    coach_message = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.engine = TournamentEngine()
        self.action_layout = QHBoxLayout()

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

        title = QLabel("Tournament Simulator")
        title.setObjectName("Title")
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.field = QSpinBox()
        self.field.setRange(9, 8000)
        self.field.setValue(self.engine.field_size)
        self.field.valueChanged.connect(self._update_settings)
        self.speed = QComboBox()
        self.speed.addItems(["regular", "turbo", "hyper"])
        self.speed.currentTextChanged.connect(self._update_settings)
        self.pko = QCheckBox("PKO on")
        self.pko.setChecked(True)
        self.pko.stateChanged.connect(self._update_settings)
        for label, widget in [("Field", self.field), ("Speed", self.speed), ("", self.pko)]:
            if label:
                controls.addWidget(QLabel(label))
            controls.addWidget(widget)
        controls.addStretch(1)
        layout.addLayout(controls)

        top = QHBoxLayout()
        self.table = PokerTableView()
        top.addWidget(self.table, 2)
        panel = QFrame()
        panel.setObjectName("DataPanel")
        panel_layout = QVBoxLayout(panel)
        self.spot_title = QLabel()
        self.spot_title.setObjectName("SectionTitle")
        self.spot_info = QLabel()
        self.spot_info.setWordWrap(True)
        self.spot_info.setObjectName("Muted")
        self.report = QLabel()
        self.report.setWordWrap(True)
        self.report.setObjectName("Cyan")
        panel_layout.addWidget(self.spot_title)
        panel_layout.addWidget(self.spot_info)
        panel_layout.addWidget(self.report)
        panel_layout.addLayout(self.action_layout)
        top.addWidget(panel, 1)
        layout.addLayout(top)
        self.load_spot()

    def _update_settings(self) -> None:
        self.engine.field_size = self.field.value()
        self.engine.speed = self.speed.currentText()
        self.engine.pko = self.pko.isChecked()

    def load_spot(self) -> None:
        spot = self.engine.current_spot
        self.state.selected_spot = spot
        self.table.set_hand(spot["hero_cards"], spot["board"], spot["pot_bb"])
        self.spot_title.setText(f"{spot['id']} | {spot['title']}")
        self.spot_info.setText(
            f"Players left {spot['players_left']} / paid {spot['paid_places']} | "
            f"Risk premium {spot['risk_premium']:.1%} | Bubble factor {spot['bubble_factor']} | "
            f"Bounty EV {spot['bounty_ev']:+.2f}"
        )
        self.report.setText(
            f"ROI projection {self.engine.roi_projection:+.2f}% | ICM punts {self.engine.icm_punts} | "
            f"Finish projection {self.engine.finish_position or 'live'}"
        )
        _clear_layout(self.action_layout)
        for action in spot["options"]:
            button = QPushButton(action)
            button.clicked.connect(lambda checked=False, a=action: self.decide(a))
            self.action_layout.addWidget(button)

    def decide(self, action: str) -> None:
        spot = self.engine.current_spot
        result = self.engine.decide(action)
        self.report.setText(
            f"Hero {action}; chipEV best {result['best_action']}. "
            f"$EV loss {result['dollar_ev_loss']:.2f}, risk premium {result['risk_premium']:.1%}, "
            f"ROI projection {result['roi_projection']:+.2f}, ICM punts {result['icm_punts']}."
        )
        self.coach_message.emit(explain_spot(spot, action))
        self.load_spot()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

