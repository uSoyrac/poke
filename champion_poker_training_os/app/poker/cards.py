from __future__ import annotations

RANKS = "23456789TJQKA"
SUITS = "shdc"


def pretty_card(card: str) -> str:
    rank = card[0].upper()
    suit = card[1].lower()
    symbols = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
    return f"{rank}{symbols.get(suit, suit)}"


def normalize_hand(card_a: str, card_b: str) -> str:
    rank_a, rank_b = card_a[0].upper(), card_b[0].upper()
    suited = card_a[1].lower() == card_b[1].lower()
    if rank_a == rank_b:
        return rank_a + rank_b
    order = {rank: idx for idx, rank in enumerate(RANKS)}
    high, low = sorted((rank_a, rank_b), key=lambda r: order[r], reverse=True)
    return high + low + ("s" if suited else "o")

