from __future__ import annotations


def simple_ev(win_probability: float, reward: float, risk: float) -> float:
    lose_probability = 1.0 - win_probability
    return win_probability * reward - lose_probability * risk


def bluff_ev(fold_frequency: float, pot: float, bet: float, equity_when_called: float = 0.0) -> float:
    call_frequency = 1.0 - fold_frequency
    called_ev = equity_when_called * (pot + bet) - (1.0 - equity_when_called) * bet
    return fold_frequency * pot + call_frequency * called_ev


def call_ev(equity: float, pot_before_call: float, call_amount: float) -> float:
    return equity * (pot_before_call + call_amount) - (1.0 - equity) * call_amount

