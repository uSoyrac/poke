from __future__ import annotations

from app.parsers.hand_history_parser import parse_hand_history


def parse_pokerstars(raw_text: str) -> list[dict]:
    return [{**hand, "site": "PokerStars"} for hand in parse_hand_history(raw_text)]

