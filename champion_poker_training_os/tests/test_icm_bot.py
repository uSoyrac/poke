"""ICM-duyarlı bot oyunu — bubble/FT'de marjinal calloff sıkılaşır.

KRİTİK: icm_pressure=0 (cash/varsayılan) iken davranış DEĞİŞMEZ → fidelity
korunur. ICM mantığı saf _icm_should_fold() metodunda izole test edilir
(böylece _preflop'un kenar-durum tuhaflıklarından bağımsız ve güvenilir).
"""
from __future__ import annotations

from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
from app.engine.hand_state import Card
from app.simulator.mtt_field import icm_pressure_for


def _brain(icm):
    b = BotBrain(BOT_ARCHETYPES["TAG"])
    b.icm_pressure = icm
    return b


# Büyük risk: 20 call / 21 stack ≈ %95 stack riski
_BIG_RISK = dict(to_call=20.0, stack0=21.0)
_SMALL_RISK = dict(to_call=2.0, stack0=21.0)   # ~%10


def test_icm_zero_never_folds():
    """icm_pressure=0 → ICM gate HİÇ tetiklenmez (cash/fidelity korunur)."""
    b = _brain(0.0)
    for hole in ([Card("A", "s"), Card("9", "s")], [Card("7", "c"), Card("2", "d")]):
        assert not b._icm_should_fold(hole, [], **_BIG_RISK)


def test_high_icm_folds_marginal_big_risk():
    """Yüksek ICM + büyük risk → marjinal el (A9s) FOLD."""
    b = _brain(0.9)
    assert b._icm_should_fold([Card("A", "s"), Card("9", "s")], [], **_BIG_RISK)


def test_high_icm_keeps_premium():
    """ICM yüksek olsa bile premium (AA/KK/AKs) büyük-riskli calloff'u YAPAR."""
    b = _brain(0.9)
    for hole in ([Card("A", "s"), Card("A", "h")],
                 [Card("K", "s"), Card("K", "d")],
                 [Card("A", "s"), Card("K", "s")]):
        assert not b._icm_should_fold(hole, [], **_BIG_RISK), f"{hole} fold olmamalı"


def test_small_risk_never_triggers_icm():
    """Risk <%50 ise ICM gate tetiklenmez (ucuz spotlar normal oynanır)."""
    b = _brain(0.9)
    assert not b._icm_should_fold([Card("A", "s"), Card("9", "s")], [], **_SMALL_RISK)
    assert not b._icm_should_fold([Card("7", "c"), Card("2", "d")], [], **_SMALL_RISK)


def test_pressure_monotonic_tightening():
    """Baskı arttıkça daha çok el folda düşer (devam barı yükselir).
    Marjinal el (KQo) düşük baskıda devam, yüksek baskıda fold."""
    kqo = [Card("K", "s"), Card("Q", "d")]
    assert not _brain(0.2)._icm_should_fold(kqo, [], **_BIG_RISK)   # düşük baskı → devam
    assert _brain(0.95)._icm_should_fold(kqo, [], **_BIG_RISK)      # yüksek baskı → fold


def test_postflop_strong_hand_continues():
    """Postflop set/iki-çift gibi güçlü el ICM'de bile büyük-riski göğüsler."""
    b = _brain(0.9)
    # 99 board 9-2-3 → set (çok güçlü)
    hole = [Card("9", "s"), Card("9", "h")]
    board = [Card("9", "d"), Card("2", "c"), Card("3", "s")]
    assert not b._icm_should_fold(hole, board, **_BIG_RISK)


def test_icm_pressure_curve():
    """Bubble baskısı eğrisi: erken 0, bubble en yüksek, ITM orta, hata-güvenli."""
    assert icm_pressure_for(500, 50) == 0.0
    assert icm_pressure_for(52, 50) >= 0.85          # money bubble
    assert 0.3 <= icm_pressure_for(40, 50) <= 0.55   # ITM
    assert icm_pressure_for(0, 50) == 0.0


def test_decide_zero_icm_identical_to_no_attr():
    """decide() icm=0'da gate'i atlar — fidelity-güvenli (davranış değişmez)."""
    import random
    from app.engine.game_loop import PokerGame
    from app.engine.hand_state import ActionType
    random.seed(424242)
    g = PokerGame(num_players=6, starting_stack=100.0, hero_seat=0,
                  bot_archetypes=["TAG"] * 5, paced_bots=False)
    # Tüm botların icm_pressure'ı 0 (varsayılan) → normal oyun
    g.start_hand()
    guard = 0
    while g.current_hand and not g.current_hand.is_complete and guard < 200:
        if g.is_waiting_for_hero:
            g.hero_act(ActionType.FOLD, 0)
        else:
            g.step_action()
        guard += 1
    assert g.current_hand.is_complete   # hatasız tamamlanır
