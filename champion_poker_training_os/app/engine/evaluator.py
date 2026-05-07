from __future__ import annotations

from typing import List, Tuple
from itertools import combinations

from app.engine.hand_state import Card, RANK_VALUES


# Hand ranking categories (lower is better)
HAND_RANKS = {
    "Royal Flush": 0,
    "Straight Flush": 1,
    "Four of a Kind": 2,
    "Full House": 3,
    "Flush": 4,
    "Straight": 5,
    "Three of a Kind": 6,
    "Two Pair": 7,
    "One Pair": 8,
    "High Card": 9,
}


def evaluate_5cards(cards: List[Card]) -> Tuple[int, List[int], str]:
    """Evaluate exactly 5 cards. Returns (rank_category, kickers, hand_name).

    Lower rank_category = stronger hand.
    Kickers are in descending significance order for tiebreaking.
    """
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    # Check straight
    is_straight, straight_high = _check_straight(values)

    # Count ranks
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)

    # Royal/Straight Flush
    if is_flush and is_straight:
        if straight_high == 12:  # Ace-high
            return (0, [12], "Royal Flush")
        return (1, [straight_high], "Straight Flush")

    # Four of a Kind
    if sorted_counts[0][1] == 4:
        quad_val = sorted_counts[0][0]
        kicker = sorted_counts[1][0]
        return (2, [quad_val, kicker], "Four of a Kind")

    # Full House
    if sorted_counts[0][1] == 3 and sorted_counts[1][1] == 2:
        trip_val = sorted_counts[0][0]
        pair_val = sorted_counts[1][0]
        return (3, [trip_val, pair_val], "Full House")

    # Flush
    if is_flush:
        return (4, values, "Flush")

    # Straight
    if is_straight:
        return (5, [straight_high], "Straight")

    # Three of a Kind
    if sorted_counts[0][1] == 3:
        trip_val = sorted_counts[0][0]
        kickers = sorted([v for v in values if v != trip_val], reverse=True)
        return (6, [trip_val] + kickers, "Three of a Kind")

    # Two Pair
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2:
        high_pair = max(sorted_counts[0][0], sorted_counts[1][0])
        low_pair = min(sorted_counts[0][0], sorted_counts[1][0])
        kicker = [v for v in values if v != high_pair and v != low_pair][0]
        return (7, [high_pair, low_pair, kicker], "Two Pair")

    # One Pair
    if sorted_counts[0][1] == 2:
        pair_val = sorted_counts[0][0]
        kickers = sorted([v for v in values if v != pair_val], reverse=True)
        return (8, [pair_val] + kickers, "One Pair")

    # High Card
    return (9, values, "High Card")


def _check_straight(values: List[int]) -> Tuple[bool, int]:
    """Check if sorted descending values form a straight."""
    unique = sorted(set(values), reverse=True)
    if len(unique) < 5:
        return False, 0

    # Normal straight check
    if unique[0] - unique[4] == 4:
        return True, unique[0]

    # Wheel (A-2-3-4-5)
    if set(unique) == {12, 3, 2, 1, 0}:
        return True, 3  # 5-high straight

    return False, 0


def evaluate_best_hand(hole_cards: List[Card], community: List[Card]) -> Tuple[int, List[int], str]:
    """Find the best 5-card hand from 7 cards (2 hole + 5 community)."""
    all_cards = hole_cards + community
    best = None

    for combo in combinations(all_cards, 5):
        result = evaluate_5cards(list(combo))
        if best is None or _compare_hands(result, best) < 0:
            best = result

    return best if best else (9, [0], "High Card")


def _compare_hands(a: Tuple[int, List[int], str], b: Tuple[int, List[int], str]) -> int:
    """Compare two evaluated hands. Returns <0 if a is better, >0 if b is better, 0 if tied."""
    if a[0] != b[0]:
        return a[0] - b[0]
    for ak, bk in zip(a[1], b[1]):
        if ak != bk:
            return bk - ak  # Higher kicker is better (negative means a wins)
    return 0


def determine_winners(
    players_hands: List[Tuple[int, List[Card]]],
    community: List[Card],
) -> Tuple[List[int], str]:
    """Determine winner(s) from list of (player_idx, hole_cards).

    Returns (list of winning player indices, winning hand name).
    Handles ties (split pots).
    """
    evaluations = []
    for player_idx, hole_cards in players_hands:
        rank, kickers, name = evaluate_best_hand(hole_cards, community)
        evaluations.append((player_idx, rank, kickers, name))

    # Find the best hand
    best = min(evaluations, key=lambda x: (x[1], [-k for k in x[2]]))
    best_rank, best_kickers = best[1], best[2]

    # Find all players with the same best hand (for split pots)
    winners = [
        e[0] for e in evaluations
        if e[1] == best_rank and e[2] == best_kickers
    ]

    return winners, best[3]
