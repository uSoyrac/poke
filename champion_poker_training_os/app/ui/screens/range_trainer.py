from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.app_state import AppState
from app.ui.components.range_grid import RangeGrid


class RangeTrainerScreen(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18)
        title = QLabel("Preflop Range Trainer")
        title.setObjectName("Title")
        controls = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["RFI", "BB defend", "SB strategy", "BTN steal", "vs RFI", "vs 3bet", "15bb push/fold", "Final table ICM"])
        self.mode.currentTextChanged.connect(self.render)
        quiz = QPushButton("Random Quiz")
        quiz.clicked.connect(lambda: self.feedback.setText("Quiz: select all BTN RFI hands at 40bb. Heatmap will mark deviations."))
        controls.addWidget(QLabel("Module"))
        controls.addWidget(self.mode)
        controls.addWidget(quiz)
        controls.addStretch(1)
        self.feedback = QLabel("Frequency colors: green pure, cyan high frequency, purple mixed, dark low frequency.")
        self.feedback.setObjectName("Muted")
        self.layout.addWidget(title)
        self.layout.addLayout(controls)
        self.grid_holder = QVBoxLayout()
        self.layout.addLayout(self.grid_holder)
        self.layout.addWidget(self.feedback)
        self.render()

    def render(self) -> None:
        while self.grid_holder.count():
            item = self.grid_holder.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.grid_holder.addWidget(RangeGrid(self.mode.currentText()))

