def classify_preflop_spot(position: str, action_line: str) -> str:
    if "3bet" in action_line.lower():
        return "vs 3bet defend"
    if position == "BB":
        return "BB defend"
    return "RFI"

