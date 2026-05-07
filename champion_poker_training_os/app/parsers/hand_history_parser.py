from __future__ import annotations

from app.parsers.pokerstars_parser import parse_pokerstars


def parse_hand_history(raw_text: str, site_hint: str | None = None) -> list[dict]:
    """Auto-detect site from text and route to the appropriate parser.

    Returns a list of normalized hand dicts (see pokerstars_parser for fields).
    """
    if not raw_text:
        return []
    text = raw_text.strip()
    if site_hint == "PokerStars" or text.startswith("PokerStars"):
        return parse_pokerstars(text)
    if site_hint == "GGPoker" or "Poker Hand #" in text or text.startswith("GGPoker"):
        # GGPoker format is similar enough that PS parser handles a useful subset
        return [{**h, "site": "GGPoker"} for h in parse_pokerstars(text)]
    # Fallback: try PS parser anyway
    return parse_pokerstars(text)

