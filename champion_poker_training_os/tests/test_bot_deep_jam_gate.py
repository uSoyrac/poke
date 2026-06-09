"""S3 guard: bot DERİN stack'te premium elle open-jam spew'i yapmasın (D125).

Bug (canlı test): turnuvada premium eller (AA/KK/AK) 90bb'yi bir 3-bet üstüne
jam'lıyordu ('pair yok ama hepsi all-in'). Bu bot'un sizing'inde 3-bet (~9-10bb)
zaten bb*8 eşiğini aşıp '4-bet' sanılıyor → premium open-jam. Fix: tournament_mode
+ derin (>25bb) → jam yerine 5-bet RAISE. Cash (tournament_mode=False) DEĞİŞMEZ
(fidelity korunur). Kısa stack jam (Nash) korunur.
"""
from __future__ import annotations

import random
from collections import Counter

from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES
from app.engine.hand_state import (Action, ActionType, Card, HandState,
                                    PlayerSeat, Street)


def _spot(tournament_mode: bool, stack: float, n=40) -> Counter:
    out = Counter()
    for s in range(n):
        h = HandState()
        h.big_blind = 1.0
        h.street = Street.PREFLOP
        h.players = [
            PlayerSeat(name="bot", stack=stack, position="CO", current_bet=3.0,
                       hole_cards=[Card("A", "s"), Card("A", "d")]),
            PlayerSeat(name="v", stack=stack, position="BTN", current_bet=10.0),
        ]
        h.actions = [
            Action(player_idx=0, action_type=ActionType.BET, amount=3.0, street=Street.PREFLOP),
            Action(player_idx=1, action_type=ActionType.RAISE, amount=10.0, street=Street.PREFLOP),
        ]
        h.current_bet = 10.0
        h.pot = 14.0
        h.min_raise = 17.0
        b = BotBrain(BOT_ARCHETYPES["Balanced Reg"])
        b.tournament_mode = tournament_mode
        random.seed(s)
        out[b.decide(h, 0)[0].name] += 1
    return out


def test_tournament_deep_premium_does_not_open_jam():
    """Turnuva + derin (90bb): premium vs 3-bet ASLA ALL_IN olmamalı → 5-bet RAISE."""
    c = _spot(tournament_mode=True, stack=90.0)
    assert c["ALL_IN"] == 0, f"Derin turnuvada open-jam spew: {dict(c)}"
    assert c["RAISE"] > 0, f"5-bet RAISE bekleniyordu: {dict(c)}"


def test_tournament_short_premium_still_jams():
    """Turnuva + kısa (20bb): premium vs 3-bet jam DOĞRU (Nash push/fold)."""
    c = _spot(tournament_mode=True, stack=20.0)
    assert c["ALL_IN"] > 0, f"Kısa stack jam korunmalı: {dict(c)}"


def test_cash_unchanged_preserves_fidelity():
    """Cash (tournament_mode=False): orijinal jam path KORUNUR → fidelity etkilenmez."""
    c = _spot(tournament_mode=False, stack=90.0)
    assert c["ALL_IN"] > 0, f"Cash'te orijinal jam davranışı korunmalı: {dict(c)}"
    assert c["RAISE"] == 0, f"Cash'te 5-bet dalı çalışmamalı (byte-identical): {dict(c)}"
