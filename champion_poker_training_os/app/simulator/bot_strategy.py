from __future__ import annotations


def bot_action(bot: dict, hand_strength: float, pressure: float = 0.0) -> str:
    aggression = bot.get("aggression", 1.0)
    call_down = bot.get("call_down", 40) / 100
    bluff = bot.get("river_bluff", 20) / 100
    score = hand_strength + aggression * 0.08 + bluff * 0.12 - pressure * (1 - call_down)
    if score > 0.82:
        return "jam"
    if score > 0.62:
        return "raise"
    if score > 0.38:
        return "call"
    return "fold"

