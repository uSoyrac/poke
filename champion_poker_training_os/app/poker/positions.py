POSITIONS_6MAX = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
POSITIONS_9MAX = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]


def position_order(table_size: int) -> list[str]:
    return POSITIONS_9MAX if table_size >= 8 else POSITIONS_6MAX

