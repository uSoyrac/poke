from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    street: str
    actor: str
    action: str
    amount_bb: float = 0.0

