from __future__ import annotations

from app.db.seed_data import combat_packs


def available_combat_packs() -> list[dict]:
    return combat_packs()

