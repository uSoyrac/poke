from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandSpot:
    spot_id: str
    title: str
    hero_cards: str
    board: str
    position: str
    stack_bb: int
    pot_bb: float
    action_history: str
    options: tuple[str, ...]
    best_action: str

