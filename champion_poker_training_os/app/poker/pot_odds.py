from __future__ import annotations


def pot_odds(call_amount: float, pot_before_call: float) -> float:
    final_pot = call_amount + pot_before_call + call_amount
    if final_pot <= 0:
        return 0.0
    return call_amount / final_pot


def required_equity(call_amount: float, pot_before_call: float) -> float:
    return pot_odds(call_amount, pot_before_call)

