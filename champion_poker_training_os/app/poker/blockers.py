from __future__ import annotations


def blocker_note(hero_cards: str, board: str) -> str:
    if "A" in hero_cards:
        return "Ace blocker reduces opponent nut Ax combinations."
    if any(card in hero_cards for card in ("K", "Q")):
        return "Broadway blocker improves bluff-catch and barrel selection."
    if board.count("s") >= 2 and "s" in hero_cards:
        return "Suit blocker interacts with flush-completing runouts."
    return "No premium blocker; prefer range and pot-odds discipline."

