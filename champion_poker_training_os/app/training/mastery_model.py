from __future__ import annotations


def mastery_percent(accuracy: float, volume: int, ev_loss_per_100: float) -> int:
    volume_factor = min(volume / 200, 1.0)
    ev_factor = max(0.0, 1.0 - ev_loss_per_100 / 60)
    return int(round((accuracy * 0.55 + volume_factor * 0.2 + ev_factor * 0.25) * 100))

