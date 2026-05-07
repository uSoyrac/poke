from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout


class SolverFrequencyBar(QFrame):
    def __init__(self, action: str, frequency: float, ev: float, sizing: str = ""):
        super().__init__()
        self.setObjectName("Elevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        header = QHBoxLayout()
        label = QLabel(action)
        label.setObjectName("Cyan")
        ev_label = QLabel(f"EV {ev:+.2f}")
        ev_label.setObjectName("Green" if ev >= 0 else "Red")
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(ev_label)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(frequency * 100))
        bar.setFormat(f"{frequency:.0%}")
        sizing_label = QLabel(sizing or "no sizing")
        sizing_label.setObjectName("Muted")
        layout.addLayout(header)
        layout.addWidget(bar)
        layout.addWidget(sizing_label)


class EVLossBadge(QLabel):
    def __init__(self, ev_loss: float = 0.0):
        super().__init__()
        self.set_value(ev_loss)

    def set_value(self, ev_loss: float) -> None:
        self.setText(f"EV loss {ev_loss:.2f}bb")
        self.setObjectName("Red" if ev_loss >= 0.45 else "Green")
        self.style().unpolish(self)
        self.style().polish(self)

