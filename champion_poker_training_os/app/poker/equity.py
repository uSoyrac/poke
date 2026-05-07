from __future__ import annotations

import random
from typing import List, Optional

# Comprehensive preflop equity lookup (2-player, approximate)
HAND_STRENGTH_HINTS = {
    # Premium pairs
    "AA": 0.852, "KK": 0.824, "QQ": 0.799, "JJ": 0.775, "TT": 0.750,
    "99": 0.720, "88": 0.693, "77": 0.665, "66": 0.636, "55": 0.605,
    "44": 0.572, "33": 0.540, "22": 0.502,
    # Broadway suited
    "AKs": 0.670, "AQs": 0.660, "AJs": 0.650, "ATs": 0.640,
    "KQs": 0.630, "KJs": 0.620, "KTs": 0.610,
    "QJs": 0.600, "QTs": 0.590, "JTs": 0.580,
    # Broadway offsuit
    "AKo": 0.650, "AQo": 0.640, "AJo": 0.630, "ATo": 0.610,
    "KQo": 0.610, "KJo": 0.600, "KTo": 0.585,
    "QJo": 0.575, "QTo": 0.565, "JTo": 0.560,
    # Suited aces
    "A9s": 0.620, "A8s": 0.610, "A7s": 0.600, "A6s": 0.590,
    "A5s": 0.600, "A4s": 0.590, "A3s": 0.580, "A2s": 0.570,
    # Suited connectors
    "T9s": 0.555, "98s": 0.540, "87s": 0.530, "76s": 0.520,
    "65s": 0.510, "54s": 0.500,
    # Offsuit aces
    "A9o": 0.590, "A8o": 0.580, "A7o": 0.570, "A6o": 0.560,
    "A5o": 0.570, "A4o": 0.560, "A3o": 0.550, "A2o": 0.540,
    # Weak hands
    "72o": 0.340, "93o": 0.370, "T2o": 0.390, "J3o": 0.400,
    "Q2o": 0.420, "K2o": 0.450,
}

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def estimate_preflop_equity(hand: str, players: int = 2) -> float:
    """Estimate preflop equity from lookup table with multiway adjustment."""
    base = HAND_STRENGTH_HINTS.get(hand, _interpolate_equity(hand))
    multiway_penalty = max(players - 2, 0) * 0.045
    return max(0.05, min(0.95, base - multiway_penalty))


def _interpolate_equity(hand: str) -> float:
    """Rough equity estimate for hands not in the lookup table."""
    if len(hand) < 2:
        return 0.45
    r1, r2 = hand[0], hand[1]
    if r1 == r2:  # pocket pair
        rank_val = RANKS.index(r1) if r1 in RANKS else 5
        return 0.50 + rank_val * 0.027
    suited = hand.endswith("s") if len(hand) >= 3 else False
    r1_val = RANKS.index(r1) if r1 in RANKS else 5
    r2_val = RANKS.index(r2) if r2 in RANKS else 4
    high = max(r1_val, r2_val)
    low = min(r1_val, r2_val)
    gap = high - low
    base = 0.35 + high * 0.018 + low * 0.008
    if suited:
        base += 0.035
    base -= gap * 0.012
    return max(0.30, min(0.70, base))


def monte_carlo_equity(
    hero_cards: List[str],
    board: Optional[List[str]] = None,
    villain_range_width: float = 1.0,
    simulations: int = 5000,
) -> float:
    """Simplified Monte Carlo equity estimation.

    Uses random runouts to estimate hero's equity against a random villain hand.
    This is a simplified version — production would use a proper evaluator.
    """
    if board is None:
        board = []

    wins = 0
    total = 0
    hero_rank_values = [_rank_value(c[0]) for c in hero_cards if c]

    for _ in range(simulations):
        # Generate random villain cards
        v1_rank = random.randint(0, 12)
        v2_rank = random.randint(0, 12)
        villain_rank_values = [v1_rank, v2_rank]

        # Simplified board evaluation
        all_hero = sorted(hero_rank_values, reverse=True)
        all_villain = sorted(villain_rank_values, reverse=True)

        # Check for pairs
        hero_paired = all_hero[0] == all_hero[1] if len(all_hero) >= 2 else False
        villain_paired = all_villain[0] == all_villain[1] if len(all_villain) >= 2 else False

        if hero_paired and not villain_paired:
            wins += 1
        elif not hero_paired and villain_paired:
            pass
        elif hero_paired and villain_paired:
            if all_hero[0] > all_villain[0]:
                wins += 1
            elif all_hero[0] == all_villain[0]:
                wins += 0.5
        else:
            if all_hero[0] > all_villain[0]:
                wins += 1
            elif all_hero[0] == all_villain[0]:
                if len(all_hero) > 1 and len(all_villain) > 1:
                    if all_hero[1] > all_villain[1]:
                        wins += 1
                    elif all_hero[1] == all_villain[1]:
                        wins += 0.5
                else:
                    wins += 0.5
        total += 1

    return round(wins / max(total, 1), 3)


def _rank_value(rank_char: str) -> int:
    """Convert rank character to numeric value."""
    idx = RANKS.find(rank_char.upper())
    return idx if idx >= 0 else 5


def equity_vs_range(hero_equity: float, villain_fold_frequency: float) -> float:
    """Calculate effective equity when villain folds some portion of their range."""
    fold_ev = villain_fold_frequency * 1.0  # Win pot when villain folds
    call_ev = (1 - villain_fold_frequency) * hero_equity
    return round(fold_ev + call_ev, 3)
