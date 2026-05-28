"""Backwards-compat shim — yeni GTO datasını re-export eder.

Tüm gerçek implementation app/poker/gto_ranges.py içinde.
Eski importlar (range_matrix, demo_frequency) burada da çalışır.
"""
from __future__ import annotations

from app.poker.gto_ranges import (  # noqa: F401
    RANKS_DESC,
    all_hand_keys,
    demo_frequency,
    get_action,
    range_matrix,
    POSITIONS_6MAX,
    POSITIONS_8MAX,
    SCENARIOS,
    STACK_DEPTHS,
    MODES,
)
