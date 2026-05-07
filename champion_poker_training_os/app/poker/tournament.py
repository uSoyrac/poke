from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TournamentState:
    stage: str
    players_left: int
    paid_places: int
    hero_stack_bb: float
    avg_stack_bb: float
    bounty: float = 0.0

    @property
    def bubble_pressure(self) -> str:
        if self.players_left <= self.paid_places + 2:
            return "Extreme"
        if self.stage.lower() in {"bubble", "final table"}:
            return "High"
        return "Medium"

