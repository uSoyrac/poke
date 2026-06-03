"""Sizing önerisi efektif stack'i ASLA aşmamalı (SS1 bug).

Senaryo: hero CO, efektif 103bb. Villain BTN 99.5bb'ye 3-bet etti. Eski model
'açışın 3x'i' = 298.5bb 'raise to' öneriyordu — imkansız (stack 103bb). Önerilen
raise stack'i aşıyorsa doğru aksiyon JAM'dir; öneri stack ile cap'lenmeli.
"""
from __future__ import annotations

from app.engine.hand_state import HandState, PlayerSeat, Street
from app.poker.sizing_advice import sizing_advice


def _hand_facing_3bet() -> HandState:
    h = HandState()
    h.big_blind = 1.0
    h.street = Street.PREFLOP
    h.current_bet = 99.5
    h.players = [
        PlayerSeat(name="hero", stack=80.0, position="CO", is_hero=True,
                   current_bet=23.0),
        PlayerSeat(name="villain", stack=0.5, position="BTN", current_bet=99.5),
    ]
    h.pot = 99.5 + 23.0
    return h


def test_recommended_raise_never_exceeds_effective_stack():
    h = _hand_facing_3bet()
    adv = sizing_advice(h, 0)
    eff = (h.players[0].stack + h.players[0].current_bet) / h.big_blind
    assert adv.available
    assert adv.recommended_bb <= eff + 0.01, (
        f"öneri {adv.recommended_bb}bb efektif stack {eff}bb'yi aşıyor")


def test_capped_recommendation_is_labelled_jam():
    h = _hand_facing_3bet()
    adv = sizing_advice(h, 0)
    assert "JAM" in adv.label.upper() or "ALL" in adv.label.upper()
