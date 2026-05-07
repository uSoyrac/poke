from __future__ import annotations

from app.poker.equity import estimate_preflop_equity


def evaluate_hand_strength(hero_cards: str, board: str = "", players: int = 2) -> float:
    """MVP evaluator proxy. Replace with treys/eval7 adapter for production-grade equity."""
    if len(hero_cards) >= 4:
        hand = _class_from_cards(hero_cards[:2], hero_cards[2:4])
        base = estimate_preflop_equity(hand, players)
    else:
        base = 0.5
    board_bonus = 0.04 if board and any(rank in board for rank in hero_cards[::2]) else 0.0
    return max(0.02, min(0.98, base + board_bonus))


def _class_from_cards(card_a: str, card_b: str) -> str:
    ranks = "23456789TJQKA"
    a, b = card_a[0].upper(), card_b[0].upper()
    if a == b:
        return a + b
    high, low = sorted((a, b), key=lambda r: ranks.index(r), reverse=True)
    return high + low + ("s" if card_a[1].lower() == card_b[1].lower() else "o")

