"""LIVE-ADVICE INVARIANT SWEEP — canlı masadaki tavsiye katmanı (live_gto_advice
+ sizing_advice + decision_capture) için kalıcı kalkan.

Range motoru sweep'i (test_advice_sanity_sweep) STATİK range'leri denetler;
bu dosya ise GERÇEK HandState'ler kurup canlı karar anını denetler:

  - HDR!=REVEAL : header (live) ≠ reveal (snapshot) senaryosu (D111 sınıfı)
  - SIZE>STACK  : önerilen raise efektif stack'i aşıyor (298bb all-in bug, D90)
  - SCEN_WRONG  : raise sayısı yanlış senaryoya eşleniyor (0→RFI/1→vsRFI/2→vs3bet)
  - PREMIUM_FOLD: AA fold-dominant (ASLA), 72o EP RFI raise-dominant (ASLA)
"""
from __future__ import annotations

import pytest

from app.engine.hand_state import (Action, ActionType, Card, HandState,
                                    PlayerSeat, Street)
from app.poker.decision_capture import make_snapshot
from app.poker.gto_live_advice import live_gto_advice
from app.poker.sizing_advice import sizing_advice

POS_ORDER = ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB"]


def _build(hero_pos, n_raises, stack_bb, hole):
    """hero_pos'ta hero, önünde n_raises raise olan preflop HandState."""
    h = HandState()
    h.big_blind = 1.0
    h.street = Street.PREFLOP
    hi = POS_ORDER.index(hero_pos)
    h.players = [PlayerSeat(name="hero", stack=stack_bb, position=hero_pos,
                            is_hero=True, current_bet=0.0,
                            hole_cards=[Card(hole[0], hole[1]),
                                        Card(hole[2], hole[3])])]
    h.actions = []
    raisers = POS_ORDER[:hi][-n_raises:] if n_raises else []
    bet, last = 3.0, 1.0
    for rp in raisers:
        idx = len(h.players)
        h.players.append(PlayerSeat(name=rp, stack=stack_bb, position=rp,
                                    current_bet=bet))
        h.actions.append(Action(player_idx=idx, action_type=ActionType.RAISE,
                                amount=bet, street=Street.PREFLOP))
        last, bet = bet, bet * 3.0
    h.current_bet = last
    h.pot = sum(p.current_bet for p in h.players) + 1.5
    return h


def _sweep(hole, check_aa=False, check_trash=False):
    v = []
    for mode in ("cash", "MTT"):
        for stack in (20, 40, 95):
            for pos in POS_ORDER:
                hi = POS_ORDER.index(pos)
                for nr in (0, 1, 2):
                    if nr > hi:
                        continue
                    h = _build(pos, nr, float(stack), hole)
                    adv = live_gto_advice(h, 0, mode=mode)
                    snap = make_snapshot(h, 0, adv, bb=1.0)
                    sz = sizing_advice(h, 0, mode=mode)
                    eff = h.players[0].stack + h.players[0].current_bet
                    tag = f"{mode} {pos} nr{nr} {stack}bb"
                    if snap["scenario"] != adv.scenario:
                        v.append(f"HDR!=REVEAL {tag}: {adv.scenario!r} vs {snap['scenario']!r}")
                    if sz.recommended_bb > eff + 0.5:
                        v.append(f"SIZE>STACK {tag}: {sz.recommended_bb} > eff {eff}")
                    exp = "vs RFI" if nr == 1 else ("vs 3-bet" if nr == 2 else None)
                    if exp and adv.scenario_key != exp:
                        v.append(f"SCEN_WRONG {tag}: {adv.scenario_key!r} != {exp!r}")
                    if check_aa and adv.fold > max(adv.raise_, adv.call) + 1e-9:
                        v.append(f"PREMIUM_FOLD {tag}: AA fold-dominant "
                                 f"(r={adv.raise_} c={adv.call} f={adv.fold})")
                    if (check_trash and nr == 0 and pos in ("UTG", "UTG+1", "MP")
                            and adv.raise_ > max(adv.call, adv.fold) + 1e-9):
                        v.append(f"TRASH_RAISE {tag}: 72o EP açışta raise-dominant")
    return v


def test_premium_aa_live_sweep():
    """AA ile 144 spot: header==reveal, sizing<=stack, doğru senaryo, AA asla fold."""
    v = _sweep(("A", "s", "A", "h"), check_aa=True)
    assert not v, "AA live-advice ihlalleri:\n" + "\n".join(v)


def test_trash_72o_live_sweep():
    """72o ile: header==reveal, sizing<=stack, EP RFI'da raise-dominant olmamalı."""
    v = _sweep(("7", "h", "2", "s"), check_trash=True)
    assert not v, "72o live-advice ihlalleri:\n" + "\n".join(v)
