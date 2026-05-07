from __future__ import annotations


def alpha(risk: float, reward: float) -> float:
    denominator = risk + reward
    if denominator <= 0:
        return 0.0
    return risk / denominator


def mdf(risk: float, reward: float) -> float:
    return 1.0 - alpha(risk, reward)

