"""Pure-Python concept → trainer routing table. Used by Knowledge Base.

Maps a concept's `application` (the linked module name from seed_data.knowledge_cards)
to (nav_target, optional drill_filters) so 'Practice this concept' can prime the
trainer with relevant filters.
"""
from __future__ import annotations


APPLICATION_NAV: dict[str, tuple[str, dict | None]] = {
    "Math Lab": ("Math Lab", None),
    "AI Coach": ("AI Poker Coach", None),
    "Combat Trainer": ("Combat Trainer", None),
    "Tournament Simulator": ("Tournament Simulator", None),
    "ICM / PKO Trainer": ("ICM / PKO Trainer", None),
    "River Decision Trainer": (
        "Spot Practice Trainer",
        {"starting_spot": "River", "preflop_action": "Any"},
    ),
    "River Trainer": (
        "Spot Practice Trainer",
        {"starting_spot": "River", "preflop_action": "Any"},
    ),
    "Study Planner": ("Study Planner", None),
    "Knowledge Base": ("Knowledge Base", None),
}


def route_for(application: str) -> tuple[str, dict | None]:
    """Return (nav_target, drill_filters) for the given application; safe default."""
    return APPLICATION_NAV.get(application, ("Spot Practice Trainer", None))
