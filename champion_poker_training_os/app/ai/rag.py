from __future__ import annotations

from app.db.seed_data import knowledge_cards


def search_concepts(query: str) -> list[dict]:
    text = query.lower()
    cards = knowledge_cards()
    return [
        card
        for card in cards
        if text in card["concept"].lower() or text in card["summary"].lower() or text in card["source"].lower()
    ][:5] or cards[:3]

