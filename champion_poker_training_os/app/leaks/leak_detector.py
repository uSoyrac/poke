from __future__ import annotations

from app.db.seed_data import leaks


def detect_demo_leaks(_hands: list[dict]) -> list[dict]:
    return leaks()

