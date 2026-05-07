from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.ai.coach_engine import explain_spot
from app.core.app_state import AppState
from app.db.seed_data import generate_spot_drills
from app.solver.mock_solver import solve_spot
from app.ui.components.range_grid import RangeGrid
from app.ui.components.solver_bar import SolverFrequencyBar


class StudyLibraryScreen(QWidget):
    coach_message = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.spots = generate_spot_drills(80)
        self.current = self.spots[0]
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

        filters = QHBoxLayout()
        self.filter_boxes = {}
        for label, values in {
            "Format": ["all", "cash", "MTT", "SNG", "PKO", "heads-up"],
            "Table": ["all", "6-max", "9-max", "HU"],
            "Stack": ["all", "10bb", "15bb", "20bb", "25bb", "40bb", "60bb", "100bb", "200bb"],
            "Position": ["all", "UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"],
            "Pot": ["all", "SRP", "3BP", "4BP", "limped", "multiway"],
            "Street": ["all", "preflop", "flop", "turn", "river"],
            "ICM": ["all", "off", "bubble", "final table", "satellite", "PKO"],
        }.items():
            box = QComboBox()
            box.addItems(values)
            box.currentTextChanged.connect(self.select_first_match)
            self.filter_boxes[label] = box
            filters.addWidget(QLabel(label))
            filters.addWidget(box)
        layout.addLayout(filters)

        main = QHBoxLayout()
        left = QFrame()
        left.setObjectName("DataPanel")
        left_layout = QVBoxLayout(left)
        self.node_title = QLabel()
        self.node_title.setObjectName("SectionTitle")
        self.node_meta = QLabel()
        self.node_meta.setWordWrap(True)
        self.node_meta.setObjectName("Muted")
        self.solver_layout = QGridLayout()
        buttons = QHBoxLayout()
        for label, target in [
            ("Practice this spot", "Spot Practice Trainer"),
            ("Ask coach why", ""),
            ("Create drill pack", ""),
            ("Compare my hands", "Hand History Analyzer"),
        ]:
            button = QPushButton(label)
            if label == "Ask coach why":
                button.clicked.connect(lambda: self.coach_message.emit(explain_spot(self.current)))
            elif target:
                button.clicked.connect(lambda checked=False, t=target: self.navigate_requested.emit(t))
            else:
                button.clicked.connect(lambda checked=False, l=label: self.coach_message.emit(f"{l}: drill pack oluşturuldu."))
            buttons.addWidget(button)
        left_layout.addWidget(self.node_title)
        left_layout.addWidget(self.node_meta)
        left_layout.addLayout(self.solver_layout)
        left_layout.addLayout(buttons)
        main.addWidget(left, 1)
        main.addWidget(RangeGrid("BTN RFI"), 1)
        layout.addLayout(main)
        self.render_current()

    def select_first_match(self) -> None:
        matches = self.spots
        for label, box in self.filter_boxes.items():
            value = box.currentText()
            if value == "all":
                continue
            key = {"Format": "format", "Table": "table", "Position": "position", "Pot": "pot_type", "Street": "street", "ICM": "icm"}.get(label)
            if key:
                matches = [spot for spot in matches if spot[key] == value]
            if label == "Stack":
                matches = [spot for spot in matches if f"{spot['stack_bb']}bb" == value]
        if matches:
            self.current = matches[0]
            self.state.selected_spot = self.current
            self.render_current()

    def render_current(self) -> None:
        self.state.selected_spot = self.current
        self.node_title.setText(f"{self.current['id']} | {self.current['title']}")
        self.node_meta.setText(
            f"Node path: {self.current['format']} / {self.current['table']} / {self.current['stack_bb']}bb / "
            f"{self.current['position']} / {self.current['pot_type']} / {self.current['street']} / {self.current['board_texture']} / ICM {self.current['icm']}"
        )
        _clear_layout(self.solver_layout)
        solution = solve_spot(self.current)
        for idx, action in enumerate(solution.actions):
            self.solver_layout.addWidget(SolverFrequencyBar(action.action, action.frequency, action.ev, action.sizing), idx // 2, idx % 2)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()

