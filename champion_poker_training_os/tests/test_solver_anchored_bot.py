"""Solver-anchored elit bot — Faz 1: GTO Expert postflop'u postflop_gto
(cbet/defend_strategy) ile solver-prensipli oynar. Gated: yalnız GTO arketipleri.

Hedef: edge etiketten değil DAHA İYİ KARARdan gelsin (emergent + hak edilmiş).
real-time CFR değil — precomputed solver-prensipli (feasible).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain


def test_gto_archetype_uses_solver_postflop_gated():
    gto = BotBrain(BOT_ARCHETYPES["GTO Expert"])
    reg = BotBrain(BOT_ARCHETYPES["Reg"])
    fish = BotBrain(BOT_ARCHETYPES["Fish"])
    assert gto.gto_postflop is True
    assert reg.gto_postflop is False        # diğerleri heuristik → fidelity korunur
    assert fish.gto_postflop is False


def _flop_state(to_call=0.0, hero_bet=0.0, villain_bet=0.0):
    from app.engine.hand_state import Card, HandState, PlayerSeat, Street
    h = HandState()
    h.big_blind = 1.0
    h.street = Street.FLOP
    h.community = [Card("K", "s"), Card("9", "d"), Card("4", "h")]
    h.current_bet = villain_bet
    h.pot = 6.0 + villain_bet + hero_bet
    h.players = [
        PlayerSeat(name="hero", stack=94.0, position="BTN", is_hero=True,
                   current_bet=hero_bet,
                   hole_cards=[Card("A", "s"), Card("K", "h")]),  # top pair
        PlayerSeat(name="v", stack=94.0, position="BB", current_bet=villain_bet),
    ]
    return h


def test_solver_postflop_returns_valid_action_both_branches():
    from app.engine.hand_state import ActionType
    brain = BotBrain(BOT_ARCHETYPES["GTO Expert"])
    valid_actions = [ActionType.FOLD, ActionType.CHECK, ActionType.CALL,
                     ActionType.BET, ActionType.RAISE]
    # Bahis YOK (bet/check): top-pair ile bet veya check dönmeli
    s = _flop_state(to_call=0.0)
    valid = [(a, 0.0, 100.0) for a in (ActionType.CHECK, ActionType.BET)]
    act = brain._gto_postflop_action(s, 0, s.players[0], valid,
                                     strength=0.7, draws=0.0, to_call=0.0,
                                     pot=6.0, in_position=True)
    assert act is None or act[0] in (ActionType.BET, ActionType.CHECK)

    # Bahis KARŞISINDA: defend_strategy → fold/call/raise'den biri
    s2 = _flop_state(to_call=4.0, villain_bet=4.0)
    valid2 = [(a, 0.0, 100.0) for a in (ActionType.FOLD, ActionType.CALL,
                                        ActionType.RAISE)]
    act2 = brain._gto_postflop_action(s2, 0, s2.players[0], valid2,
                                      strength=0.7, draws=0.0, to_call=4.0,
                                      pot=10.0, in_position=True)
    assert act2 is None or act2[0] in (ActionType.FOLD, ActionType.CALL,
                                       ActionType.RAISE, ActionType.CHECK)
