"""Bot postflop POZİSYON farkındalığı — IP agressor OOP'tan daha sık c-bet'ler.

GTO temel ilkesi: pozisyonda olan (son konuşan) agressor range bet ile daha sık
c-bet atar; OOP agressor checking range'ini korur, daha az c-bet'ler. Eskiden
_in_position hesaplanıyor ama KULLANILMIYORDU. Bu test farkı kanıtlar; ayrıca
toplam frekansın (ortalama) makul kaldığını (AF stabil) doğrular.
"""
from __future__ import annotations

import random

from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES
from app.engine.hand_state import (
    Action, ActionType, Card, HandState, PlayerSeat, Street,
)


def _cbet_freq(in_position: bool, n: int = 4000, seed: int = 1) -> float:
    random.seed(seed)
    brain = BotBrain(BOT_ARCHETYPES["TAG"])
    # IP/OOP'u sabitle
    brain._in_position = lambda state, idx: in_position

    bets = 0
    for _ in range(n):
        p0 = PlayerSeat(name="hero", stack=100.0, position="BTN")
        p1 = PlayerSeat(name="villain", stack=100.0, position="BB")
        # Orta-güç el: K9 (kuru olmayan ama net olmayan) — c-bet kararı serbest
        p0.hole_cards = [Card("K", "s"), Card("9", "d")]
        p1.hole_cards = [Card("7", "c"), Card("2", "h")]
        for p in (p0, p1):
            p.is_folded = False
        hand = HandState(hand_id=1, players=[p0, p1], dealer_idx=0,
                         small_blind=0.5, big_blind=1.0)
        hand.street = Street.FLOP
        hand.community = [Card("Q", "s"), Card("8", "d"), Card("3", "c")]
        hand.pot = 6.0
        # Hero (idx 0) preflop agressor olsun
        hand.actions = [Action(player_idx=0, action_type=ActionType.RAISE,
                               amount=3.0, street=Street.PREFLOP)]
        # Flop: kimse bet yapmadı → c-bet kararı
        valid = [(ActionType.CHECK, 0.0, 0.0), (ActionType.BET, 2.0, 100.0)]
        act, _ = brain._postflop(hand, 0, p0, valid)
        if act == ActionType.BET:
            bets += 1
    return bets / n


def test_ip_cbets_more_than_oop():
    ip = _cbet_freq(True)
    oop = _cbet_freq(False)
    assert ip > oop, f"IP c-bet (%{ip*100:.0f}) > OOP (%{oop*100:.0f}) olmalı"
    # Fark anlamlı ama abartısız (mean-preserving ~%24 fark)
    assert ip - oop >= 0.03, f"fark çok küçük: IP {ip:.2f} OOP {oop:.2f}"


def test_average_cbet_freq_stays_reasonable():
    """Ortalama c-bet frekansı makul bantta (AF şişmesin) — mean-preserving."""
    ip = _cbet_freq(True)
    oop = _cbet_freq(False)
    avg = (ip + oop) / 2
    assert 0.20 <= avg <= 0.75, f"ortalama c-bet %{avg*100:.0f} bant dışı"
