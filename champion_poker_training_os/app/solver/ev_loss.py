from __future__ import annotations


def severity_from_ev_loss(ev_loss: float) -> str:
    if ev_loss >= 1.0:
        return "Critical"
    if ev_loss >= 0.45:
        return "High"
    if ev_loss >= 0.15:
        return "Medium"
    return "Low"

