def spot_key(spot: dict) -> str:
    return "|".join(
        str(spot.get(key, ""))
        for key in ("format", "table", "stack_bb", "position", "pot_type", "street", "board_texture", "icm")
    )

