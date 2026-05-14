"""Bot archetype pools by skill style + level.

Single source of truth shared by MttSetupDialog and FieldSimulator so both
sample from the same distribution.
"""
from __future__ import annotations


HUMAN_LIKE_POOL: dict[str, list[str]] = {
    "Easy":   ["Fish", "Calling Station", "Aggro Fish", "Maniac", "Tight Passive"],
    "Medium": ["TAG", "LAG", "Reg", "Fish", "Tight Passive", "Aggro Fish"],
    "Hard":   ["Reg", "TAG", "LAG", "Shark", "Balanced Reg", "Nit"],
}

GTO_POOL: dict[str, list[str]] = {
    "Easy":   ["Balanced Reg", "TAG", "Reg"],
    "Medium": ["Balanced Reg", "Shark", "TAG"],
    "Hard":   ["Shark", "Balanced Reg", "Shark"],
}


def pool_for(style: str, level: str) -> list[str]:
    pool = GTO_POOL if style == "GTO-Style" else HUMAN_LIKE_POOL
    return pool.get(level, pool["Medium"])
