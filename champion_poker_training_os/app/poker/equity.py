from __future__ import annotations

HAND_STRENGTH_HINTS = {
    "AA": 0.85,
    "KK": 0.82,
    "QQ": 0.79,
    "AKs": 0.66,
    "AQs": 0.64,
    "AKo": 0.63,
    "KQs": 0.60,
    "72o": 0.34,
}


def estimate_preflop_equity(hand: str, players: int = 2) -> float:
    base = HAND_STRENGTH_HINTS.get(hand, 0.52)
    multiway_penalty = max(players - 2, 0) * 0.045
    return max(0.05, min(0.9, base - multiway_penalty))

