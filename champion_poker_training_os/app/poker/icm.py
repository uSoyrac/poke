from __future__ import annotations


def risk_premium(hero_stack_bb: float, avg_stack_bb: float, stage: str) -> float:
    stage_bonus = {
        "chipEV": 0.00,
        "bubble": 0.09,
        "final table": 0.13,
        "satellite": 0.18,
        "PKO": 0.05,
    }.get(stage, 0.06)
    stack_pressure = max(0.0, (avg_stack_bb - hero_stack_bb) / max(avg_stack_bb, 1.0)) * 0.05
    return round(stage_bonus + stack_pressure, 3)


def bounty_ev(bounty_chips: float, win_probability: float, call_cost: float) -> float:
    return win_probability * bounty_chips - (1.0 - win_probability) * call_cost

