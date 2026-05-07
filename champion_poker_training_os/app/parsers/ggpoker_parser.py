from __future__ import annotations

from app.parsers.hand_history_parser import parse_hand_history


def parse_ggpoker(raw_text: str) -> list[dict]:
    return [{**hand, "site": "GGPoker"} for hand in parse_hand_history(raw_text)]

