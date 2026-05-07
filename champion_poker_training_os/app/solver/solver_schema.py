from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SolverAction:
    action: str
    frequency: float
    ev: float
    sizing: str = ""


@dataclass(frozen=True)
class SolverResult:
    spot_id: str
    best_action: str
    actions: tuple[SolverAction, ...]
    source_confidence: str
    range_advantage: str
    nut_advantage: str
    explanation: str

    def action_by_name(self, action: str) -> SolverAction | None:
        normalized = action.lower()
        for item in self.actions:
            if item.action.lower() == normalized:
                return item
        return None

