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
    drill_filters: dict[str, Any] = field(default_factory=dict)
    # When set, Spot Trainer will jump to this spot id on next load
    pending_spot_id: str | None = None
    # FIFO queue of upcoming spot ids — Spot Trainer pops from this on each load
    pending_spot_queue: list[str] = field(default_factory=list)
    # When set by My Mistakes screen, the Spot Trainer filters to similar spots
    active_leak_signature: str = ""
    active_leak_mistakes: list[str] = field(default_factory=list)
    # When set by Spot Trainer's '🤖 Coach Açıkla' button, AI Coach screen
    # picks this up on showEvent to render a personalised explanation.
    coach_deepdive_context: dict[str, Any] = field(default_factory=dict)
    # Singleton adaptive engine — lazily created so unit tests don't pay setup cost
    _adaptive_engine: Any = None

    def adaptive_engine(self):
        """Lazy accessor for the AdaptiveEngine singleton (avoids circular import).

        On first access we hydrate from SQLite so drill history persists across
        app restarts.
        """
        if self._adaptive_engine is None:
            from app.training.adaptive_engine import AdaptiveEngine
            engine = AdaptiveEngine()
            try:
                engine.load_from_db()
            except Exception:
                pass
            self._adaptive_engine = engine
        return self._adaptive_engine

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

