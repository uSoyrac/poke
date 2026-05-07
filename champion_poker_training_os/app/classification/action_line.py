def normalize_action_line(actions: list[str]) -> str:
    return " / ".join(action.strip().lower() for action in actions if action.strip())

