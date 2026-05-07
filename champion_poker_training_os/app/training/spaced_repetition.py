from __future__ import annotations


def next_interval_days(mastered: bool, streak: int) -> int:
    if not mastered:
        return 1
    return min(30, 2 ** max(streak, 1))

