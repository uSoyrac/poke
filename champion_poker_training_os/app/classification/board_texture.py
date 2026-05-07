from __future__ import annotations


def classify_board(board: str) -> str:
    if not board or board == "preflop":
        return "preflop"
    ranks = board[::2]
    suits = board[1::2]
    if len(set(suits)) == 1 and len(suits) >= 3:
        return "monotone"
    if len(set(ranks)) < len(ranks):
        return "paired"
    if any(rank in ranks for rank in "AK"):
        return "high-card"
    return "low connected"

