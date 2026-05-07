from __future__ import annotations

RANKS_DESC = list("AKQJT98765432")


def range_matrix() -> list[list[str]]:
    grid: list[list[str]] = []
    for row, high in enumerate(RANKS_DESC):
        line: list[str] = []
        for col, low in enumerate(RANKS_DESC):
            if row == col:
                line.append(high + low)
            elif row < col:
                line.append(high + low + "s")
            else:
                line.append(low + high + "o")
        grid.append(line)
    return grid


def demo_frequency(hand: str, mode: str = "BTN RFI") -> int:
    premium = {"AA", "KK", "QQ", "JJ", "AKs", "AKo", "AQs"}
    if hand in premium:
        return 100
    if hand.endswith("s") and hand[0] in "AKQJT":
        return 75
    if hand.endswith("o") and hand[0] in "AKQ":
        return 55
    if hand[0] == hand[1]:
        return 70 if hand[0] in "TT9988" else 40
    return 20 if mode != "UTG RFI" else 8

