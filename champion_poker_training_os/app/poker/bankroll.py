from __future__ import annotations


def risk_of_ruin_proxy(bankroll_buyins: float, edge_roi: float, field_variance: float = 1.0) -> float:
    if bankroll_buyins <= 0:
        return 1.0
    edge = max(edge_roi, 0.01)
    return max(0.01, min(0.95, field_variance / (bankroll_buyins * edge * 12.0)))

