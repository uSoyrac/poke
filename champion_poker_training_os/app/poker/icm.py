from __future__ import annotations

import math
from typing import List


def malmuth_harville(stacks: List[float], payouts: List[float]) -> List[float]:
    """Malmuth-Harville ICM equity calculation.

    Computes each player's dollar equity given current chip stacks and payout
    structure using the Harville probability model.
    """
    n = len(stacks)
    total = sum(stacks)
    if total <= 0 or n == 0:
        return [0.0] * n
    equities = [0.0] * n
    _harville_recurse(stacks, payouts, equities, total, 0, 1.0, list(range(n)))
    return [round(eq, 4) for eq in equities]


def _harville_recurse(
    stacks: List[float],
    payouts: List[float],
    equities: List[float],
    remaining_chips: float,
    place: int,
    probability: float,
    alive: List[int],
) -> None:
    if place >= len(payouts) or not alive or probability < 1e-9:
        return
    for i in alive:
        p_finish = probability * (stacks[i] / max(remaining_chips, 1e-9))
        equities[i] += p_finish * payouts[place]
        next_alive = [j for j in alive if j != i]
        next_remaining = remaining_chips - stacks[i]
        _harville_recurse(
            stacks, payouts, equities, next_remaining, place + 1, p_finish, next_alive
        )


def icm_equity_single(stacks: List[float], payouts: List[float], player_idx: int) -> float:
    """Return ICM equity for a single player."""
    equities = malmuth_harville(stacks, payouts)
    if player_idx < len(equities):
        return equities[player_idx]
    return 0.0


def chip_ev_vs_dollar_ev(
    hero_stack: float,
    villain_stack: float,
    other_stacks: List[float],
    payouts: List[float],
    win_equity: float,
    call_amount: float,
) -> dict:
    """Compare chipEV vs $EV for a call decision.

    Returns chipEV, $EV of calling, $EV of folding, and the divergence.
    """
    all_stacks = [hero_stack] + [villain_stack] + other_stacks
    hero_idx = 0

    # Fold scenario
    fold_stacks = list(all_stacks)
    fold_stacks[hero_idx] -= call_amount
    fold_stacks[1] += call_amount
    fold_equities = malmuth_harville(fold_stacks, payouts)
    dollar_ev_fold = fold_equities[hero_idx]

    # Call-win scenario
    win_stacks = list(all_stacks)
    win_stacks[hero_idx] += villain_stack
    win_stacks[1] = 0
    win_equities = malmuth_harville(win_stacks, payouts)
    dollar_ev_win = win_equities[hero_idx]

    # Call-lose scenario
    lose_stacks = list(all_stacks)
    lose_stacks[hero_idx] = max(0, hero_stack - call_amount)
    lose_stacks[1] += call_amount
    lose_equities = malmuth_harville(lose_stacks, payouts)
    dollar_ev_lose = lose_equities[hero_idx]

    dollar_ev_call = win_equity * dollar_ev_win + (1 - win_equity) * dollar_ev_lose
    chip_ev_call = win_equity * villain_stack - (1 - win_equity) * call_amount

    return {
        "chip_ev": round(chip_ev_call, 2),
        "dollar_ev_call": round(dollar_ev_call, 4),
        "dollar_ev_fold": round(dollar_ev_fold, 4),
        "dollar_ev_diff": round(dollar_ev_call - dollar_ev_fold, 4),
        "icm_tax": round(max(0, chip_ev_call - (dollar_ev_call - dollar_ev_fold) * 100), 2),
        "decision": "call" if dollar_ev_call > dollar_ev_fold else "fold",
    }


def risk_premium(hero_stack_bb: float, avg_stack_bb: float, stage: str) -> float:
    """Calculate risk premium based on stack and tournament stage."""
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
    """Calculate bounty EV in PKO format."""
    return win_probability * bounty_chips - (1.0 - win_probability) * call_cost


def bubble_factor(stacks: List[float], payouts: List[float], hero_idx: int) -> float:
    """Calculate bubble factor — how much more each chip lost costs vs each chip won."""
    if hero_idx >= len(stacks) or not payouts:
        return 1.0
    base_equity = icm_equity_single(stacks, payouts, hero_idx)
    small_win = list(stacks)
    small_win[hero_idx] += stacks[hero_idx] * 0.1
    win_equity = icm_equity_single(small_win, payouts, hero_idx)
    small_lose = list(stacks)
    small_lose[hero_idx] = max(1, stacks[hero_idx] * 0.9)
    lose_equity = icm_equity_single(small_lose, payouts, hero_idx)
    gain = win_equity - base_equity
    loss = base_equity - lose_equity
    if gain <= 0:
        return 2.0
    return round(loss / gain, 2)


def push_fold_range_width(stack_bb: float, stage: str = "chipEV") -> float:
    """Estimate appropriate push range width percentage for a given stack size."""
    base_widths = {
        3: 0.95, 5: 0.75, 7: 0.55, 10: 0.40, 12: 0.32, 15: 0.25,
        18: 0.20, 20: 0.16, 25: 0.12, 30: 0.08, 40: 0.05,
    }
    closest = min(base_widths.keys(), key=lambda k: abs(k - stack_bb))
    width = base_widths[closest]
    # Tighten under ICM pressure
    icm_multiplier = {
        "chipEV": 1.0, "bubble": 0.65, "final table": 0.72,
        "satellite": 0.50, "PKO": 1.10,
    }.get(stage, 0.80)
    return round(min(1.0, width * icm_multiplier), 3)


def icm_tighten(freqs: dict, risk_premium: float) -> dict:
    """ICM baskısı altında MARJİNAL call'ları fold'a kaydır (call-off / devam
    range'ini daralt) — ICM teorisinin en net etkisi: bubble/FT'de daha çok
    equity gerektiği için sınırdaki call'lar fold olur.

    AYRI KATMAN: base chip-EV frekanslarını DEĞİŞTİRMEZ; yalnız ``risk_premium``
    > 0 ise (turnuva bubble/FT/satellite veya kısa görece stack) uygulanır.
    risk_premium=0 (cash/chipEV/early) → kimliktir → gto_accuracy korunur.

    Ölçülü kalibrasyon: shift = min(0.5, rp*2.5). Örn. bubble rp≈0.09 → %22 call
    fold'a; FT rp≈0.13 → %32. Value-raise ve push/fold (allin) frekanslarına
    DOKUNMAZ — onlar zaten mtt_ranges'te ICM-ayarlı.
    """
    rp = max(0.0, float(risk_premium or 0.0))
    out = {
        "raise": float(freqs.get("raise", 0) or 0),
        "call": float(freqs.get("call", 0) or 0),
        "fold": float(freqs.get("fold", 0) or 0),
        "allin": float(freqs.get("allin", 0) or 0),
    }
    if rp <= 0.0 or out["call"] <= 0.0:
        return out
    shift = min(0.5, rp * 2.5)
    moved = out["call"] * shift
    out["call"] -= moved
    out["fold"] += moved
    return out
