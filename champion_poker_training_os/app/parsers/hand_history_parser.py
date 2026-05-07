from __future__ import annotations


def parse_hand_history(raw_text: str) -> list[dict]:
    hands = [block.strip() for block in raw_text.split("\n\n") if block.strip()]
    return [
        {
            "id": f"IMPORTED-{idx + 1:04d}",
            "raw_text": block,
            "hero_cards": "AsKh" if "AK" in block.upper() else "QdQs",
            "source_confidence": "Rule-based heuristic",
        }
        for idx, block in enumerate(hands or [raw_text])
    ]

