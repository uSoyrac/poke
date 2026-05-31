"""Canlı GTO advice — senaryo tespiti DOĞRULUĞU (eğitim güvenliği).

KRİTİK: hero açıp sonra 3-bet'le karşılaşınca spot 'RFI (açış)' değil
'vs 3-bet' olarak tanınmalı; aksi halde JTs gibi ellere 'RAISE %100'
(4-bet) önerilir ki bu YANLIŞ — kullanıcı yanlış eğitilir.
"""
from __future__ import annotations

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Action, ActionType, Street
from app.poker.gto_live_advice import _count_preflop_raises_before_hero
from app.poker.gto_ranges import get_action


def _clean_hand(hero_seat=2):
    # start_hand botları otomatik oynatıp h.actions'ı doldurur; fonksiyonu
    # İZOLE test etmek için actions'ı temizleyip bilinen aksiyonları kuruyoruz.
    g = PokerGame(num_players=6, starting_stack=100, hero_seat=hero_seat)
    h = g.start_hand()
    h.actions.clear()
    return g, h


def _raise(idx):
    return Action(player_idx=idx, action_type=ActionType.RAISE,
                  amount=2.5, street=Street.PREFLOP)


def test_hero_open_then_3bet_is_vs_3bet_not_rfi():
    g, h = _clean_hand(hero_seat=2)
    h.actions.append(_raise(2))   # hero açış
    h.actions.append(_raise(4))   # villain 3-bet
    n, raiser = _count_preflop_raises_before_hero(h, hero_idx=2)
    assert n == 2, f"hero açıp 3-bet yiyince 2 raise olmalı, {n} döndü"
    assert raiser != h.players[2].position   # kendi raise'ine karşı oynamaz


def test_rfi_open_counts_zero_raises():
    g, h = _clean_hand(hero_seat=2)
    n, _ = _count_preflop_raises_before_hero(h, hero_idx=2)
    assert n == 0


def test_facing_single_open_is_vs_rfi():
    g, h = _clean_hand(hero_seat=5)
    h.actions.append(_raise(1))   # bir oyuncu açtı, hero henüz konuşmadı
    n, _ = _count_preflop_raises_before_hero(h, hero_idx=5)
    assert n == 1


def test_jts_advice_differs_by_scenario():
    """Eğitim güvenliği değişmezleri: JTs ile
    - RFI → açılır (raise yüksek)
    - vs 3-bet → 4-bet ETMEZ (raise ~0), call/fold."""
    rfi = get_action("HJ", "JTs", "RFI", 100, "cash")
    assert rfi.get("raise", 0) >= 80                # açılış eli

    vs3 = get_action("CO", "JTs", "vs 3-bet", 100, "cash", vs_position="BB")
    assert vs3.get("raise", 0) <= 10, f"JTs vs 3-bet 4-bet ETMEMELİ: {vs3}"
    assert vs3.get("call", 0) + vs3.get("fold", 0) >= 90
