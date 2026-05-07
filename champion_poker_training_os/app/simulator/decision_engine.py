from __future__ import annotations


def legal_actions(street: str, stack_bb: int) -> tuple[str, ...]:
    if stack_bb <= 15:
        return ("fold", "call", "jam")
    if street == "preflop":
        return ("fold", "call", "raise", "jam")
    return ("check", "call", "bet small", "bet medium", "bet large", "raise")

