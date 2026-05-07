from __future__ import annotations

from app.db.seed_data import generate_spot_drills


def fast_play_hands(count: int = 60) -> list[dict]:
    spots = generate_spot_drills(count)
    return [
        {
            **spot,
            "id": f"FAST-{idx + 1:03d}",
            "title": f"Fast Play #{idx + 1}: {spot['position']} vs pool",
        }
        for idx, spot in enumerate(spots)
    ]

