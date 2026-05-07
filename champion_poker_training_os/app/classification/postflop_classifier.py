from app.classification.board_texture import classify_board


def classify_postflop_spot(board: str, action_line: str) -> str:
    texture = classify_board(board)
    if "raise" in action_line.lower():
        return f"{texture} raise node"
    if "turn" in action_line.lower():
        return f"{texture} turn barrel node"
    return f"{texture} cbet node"

