from __future__ import annotations


def combo_count(hand_class: str) -> int:
    normalized = hand_class.strip().lower()
    if len(normalized) == 2 and normalized[0] == normalized[1]:
        return 6
    if normalized.endswith("s"):
        return 4
    if normalized.endswith("o"):
        return 12
    return 16

