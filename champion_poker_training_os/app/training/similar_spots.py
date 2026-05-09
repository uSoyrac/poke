"""Similar-spot finder — given a parsed hand (or any spot dict with position +
pot_type + street), select N similar drill spots from the seed pool so the user
can drill the situation they just replayed.
"""
from __future__ import annotations

from typing import Iterable


# Map a parsed-hand pot_type (PokerStars / CoinPoker codes) to drill pot_type.
POT_TYPE_MAP: dict[str, str] = {
    "Limp": "limped pot",
    "SRP": "single raised pot",
    "3BP": "3bet pot",
    "4BP": "4bet pot",
    "5BP": "4bet pot",
    "Squeeze": "squeezed pot",
    "Walk": "single raised pot",
}


def _street_from_actions(hand: dict) -> str:
    """Infer the deepest street the hand reached."""
    if hand.get("river_actions"):
        return "river"
    if hand.get("turn_actions"):
        return "turn"
    if hand.get("flop_actions"):
        return "flop"
    return "preflop"


def _score_match(spot: dict, criteria: dict) -> int:
    """Higher = better match. Used to rank candidate drills against a hand."""
    score = 0
    if criteria.get("position") and spot.get("position") == criteria["position"]:
        score += 4
    if criteria.get("street") and spot.get("street") == criteria["street"]:
        score += 3
    if criteria.get("pot_type") and spot.get("pot_type") == criteria["pot_type"]:
        score += 3
    # Stack proximity (within 25bb)
    target_stack = criteria.get("stack_bb")
    spot_stack = spot.get("stack_bb")
    if target_stack and spot_stack:
        diff = abs(int(target_stack) - int(spot_stack))
        if diff <= 5:
            score += 2
        elif diff <= 25:
            score += 1
    # Format match (cash / MTT / SnG)
    if criteria.get("format") and spot.get("format") == criteria["format"]:
        score += 1
    return score


def find_similar_spots(
    hand: dict,
    candidate_spots: Iterable[dict],
    n: int = 5,
) -> list[dict]:
    """Pick the top-N spots from `candidate_spots` that resemble the given hand."""
    criteria = {
        "position": (hand.get("hero_position") or hand.get("position") or "").upper() or None,
        "street": _street_from_actions(hand) if "river_actions" in hand else hand.get("street"),
        "pot_type": POT_TYPE_MAP.get(hand.get("pot_type", ""), hand.get("pot_type", "")),
        "stack_bb": hand.get("stack_bb"),
        "format": hand.get("format"),
    }
    scored: list[tuple[int, dict]] = []
    for spot in candidate_spots:
        score = _score_match(spot, criteria)
        if score > 0:
            scored.append((score, spot))
    # Highest-score first; tie-break by descending base_ev so harder spots come first
    scored.sort(key=lambda x: (-x[0], -float(x[1].get("base_ev", 0))))
    return [s for _, s in scored[:n]]
