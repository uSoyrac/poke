from __future__ import annotations


def score_decision(ev_loss: float, solver_frequency: float) -> int:
    raw = 100 - ev_loss * 45 + solver_frequency * 12
    return max(0, min(100, int(round(raw))))


def skill_label(score: int) -> str:
    if score >= 90:
        return "World-class"
    if score >= 78:
        return "Crusher"
    if score >= 65:
        return "Solid"
    if score >= 50:
        return "Developing"
    return "Repair mode"

