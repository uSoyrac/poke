from __future__ import annotations

from app.db.seed_data import generate_math_drills, generate_spot_drills, tournament_spots


def daily_drill_pack() -> dict[str, list[dict]]:
    return {
        "preflop": [d for d in generate_spot_drills(120) if d["street"] == "preflop"][:30],
        "flop": [d for d in generate_spot_drills(120) if d["street"] == "flop"][:30],
        "turn": [d for d in generate_spot_drills(120) if d["street"] == "turn"][:30],
        "river": [d for d in generate_spot_drills(120) if d["street"] == "river"][:30],
        "math": generate_math_drills(30),
        "icm": tournament_spots()[:20],
    }


def similar_spots(source_spot: dict, count: int = 5) -> list[dict]:
    drills = generate_spot_drills(120)
    return [
        drill
        for drill in drills
        if drill["street"] == source_spot.get("street") and drill["id"] != source_spot.get("id")
    ][:count]

