"""Compatibility re-exports for older callers.

The authoritative position labels live in app.engine.hand_state, which is
shared by both the engine and UI screens. This module just re-exports them
so legacy callers (`from app.poker.positions import ...`) keep working.
"""
from __future__ import annotations

from app.engine.hand_state import (
    POSITIONS_HU,
    POSITIONS_3MAX,
    POSITIONS_4MAX,
    POSITIONS_5MAX,
    POSITIONS_6MAX,
    POSITIONS_7MAX,
    POSITIONS_8MAX,
    POSITIONS_9MAX,
    POSITIONS_10MAX,
    POSITIONS_11MAX,
    positions_for,
)


MIN_PLAYERS = 2
MAX_PLAYERS = 11


def position_order(table_size: int) -> list[str]:
    return positions_for(table_size)
