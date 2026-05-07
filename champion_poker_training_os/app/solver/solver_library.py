from __future__ import annotations

from app.db.seed_data import generate_spot_drills


def study_library_nodes() -> list[dict]:
    nodes = []
    for drill in generate_spot_drills(24):
        nodes.append(
            {
                "id": drill["id"],
                "title": drill["title"],
                "format": drill["format"],
                "table": drill["table"],
                "stack": f"{drill['stack_bb']}bb",
                "position": drill["position"],
                "pot_type": drill["pot_type"],
                "street": drill["street"],
                "icm": drill["icm"],
                "board_texture": drill["board_texture"],
                "action_line": drill["action_history"],
            }
        )
    return nodes

