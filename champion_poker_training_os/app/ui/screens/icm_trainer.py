from __future__ import annotations

from PySide6.QtWidgets import QLabel

from app.ui.screens.tournament_simulator import TournamentSimulatorScreen


class IcmTrainerScreen(TournamentSimulatorScreen):
    def __init__(self, state):
        super().__init__(state)
        for label in self.findChildren(QLabel):
            if label.objectName() == "Title" and label.text() == "Tournament Simulator":
                label.setText("ICM / PKO Trainer")
                break
