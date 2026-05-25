from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    active_mode: str = "Dashboard"
    strict_rta_guard: bool = True
    strategy_locked: bool = False
    last_import: str = "Demo seed: 100 hands"
    ai_provider: str = "Offline mock coach"
    completed_drills: int = 0
    correct_drills: int = 0
    ev_loss_total: float = 0.0
    session_notes: list[str] = field(default_factory=list)
    selected_spot: dict[str, Any] | None = None
    last_hand: dict[str, Any] | None = None
    # Live tournament context — populated by TournamentSimulatorScreen each
    # refresh, consumed by the AI coach to give tournament-aware advice
    # (ICM, bubble, blind level, etc.). None when no tournament is active.
    tournament_context: dict[str, Any] | None = None

    @property
    def accuracy(self) -> float:
        if self.completed_drills == 0:
            return 0.0
        return 100.0 * self.correct_drills / self.completed_drills

    def record_decision(self, correct: bool, ev_loss: float, note: str) -> None:
        self.completed_drills += 1
        if correct:
            self.correct_drills += 1
        self.ev_loss_total += max(ev_loss, 0.0)
        self.session_notes.insert(0, note)
        self.session_notes = self.session_notes[:12]

