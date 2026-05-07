from __future__ import annotations

import random

from app.poker.cards import RANKS, SUITS


def new_deck() -> list[str]:
    return [rank + suit for rank in RANKS for suit in SUITS]


def shuffled_deck(seed: int | None = None) -> list[str]:
    deck = new_deck()
    rng = random.Random(seed)
    rng.shuffle(deck)
    return deck

