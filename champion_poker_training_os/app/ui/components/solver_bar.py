from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout


class SolverFrequencyBar(QFrame):
    def __init__(self, action: str, frequency: float, ev: float, sizing: str = "",
                 imported: bool = False):
        super().__init__()
        self.setObjectName("Elevated")
        # Subtle green tint when the data came from imported PIO/GTO solver vs mock
        if imported:
            self.setStyleSheet(
                "QFrame#Elevated { border: 1px solid #10B981; background: #0E1B17; }"
            )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        header = QHBoxLayout()
        label = QLabel(action)
        label.setObjectName("Cyan")
        if imported:
            tag = QLabel("✓")
            tag.setStyleSheet("color: #10B981; font-weight: 800;")
            tag.setToolTip("Imported solver data")
            header.addWidget(label)
            header.addWidget(tag)
        else:
            header.addWidget(label)
        ev_label = QLabel(f"EV {ev:+.2f}")
        ev_label.setObjectName("Green" if ev >= 0 else "Red")
        header.addStretch(1)
        header.addWidget(ev_label)

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(frequency * 100))
        bar.setFormat(f"{frequency:.0%}")
        if imported:
            # Solid green chunk for imported solver to distinguish from mock cyan
            bar.setStyleSheet(
                "QProgressBar { background: #0E141C; border: 1px solid #1E2733; "
                "border-radius: 5px; text-align: center; color: #E5E7EB; height: 12px; }"
                "QProgressBar::chunk { background: #10B981; border-radius: 4px; }"
            )

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
