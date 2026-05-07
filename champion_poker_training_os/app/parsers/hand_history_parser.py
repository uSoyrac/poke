from __future__ import annotations

from app.parsers.coinpoker_parser import parse_coinpoker
from app.parsers.pokerstars_parser import parse_pokerstars


def parse_hand_history(raw_text: str, site_hint: str | None = None) -> list[dict]:
    """Auto-detect site from text and route to the appropriate parser.

    Returns a list of normalized hand dicts (see pokerstars_parser for fields).
    Supports PokerStars and CoinPoker out of the box; falls back to PS parser
    for generic / other formats since most sites mimic the PS layout.
    """
    if not raw_text:
        return []
    text = raw_text.strip()

    if site_hint == "CoinPoker" or text.startswith("CoinPoker"):
        return parse_coinpoker(text)
    if site_hint == "PokerStars" or text.startswith("PokerStars"):
        return parse_pokerstars(text)

    # Auto-detect: if either parser produces results, use the richer one
    coin = parse_coinpoker(text) if "CoinPoker" in text[:200] else []
    if coin:
        return coin
    return parse_pokerstars(text)

