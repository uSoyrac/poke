from __future__ import annotations


def next_focus_from_leaks(leaks: list[dict]) -> str:
    if not leaks:
        return "Balanced maintenance"
    worst = sorted(leaks, key=lambda leak: leak.get("ev_lost", 0), reverse=True)[0]
    return f"Repair: {worst['name']}"

