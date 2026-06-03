"""Ante DOĞRULUĞU — gerçekten kesiliyor mu, pota giriyor mu, to_call'u şişiriyor mu.

Kullanıcı 'ante kesmiyor' demişti; bu paket ante'nin (1) her oyuncudan
kesildiğini, (2) tam olarak pota eklendiğini, (3) canlı bahis (to_call)
OLMADIĞINI (ölü para), (4) turnuvada level'le ölçeklendiğini kanıtlar.
"""
from __future__ import annotations

import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


def _fresh(ante: float, n: int = 6, stack: float = 100.0, seed: int = 3):
    random.seed(seed)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=0.5,
                   big_blind=1.0, ante=ante, hero_seat=0, paced_bots=True)
    gl.start_hand()
    return gl


def test_ante_added_to_pot_exactly():
    gl = _fresh(0.2, n=6)
    h = gl.current_hand
    alive = sum(1 for p in gl.players if not p.is_eliminated)
    assert abs(h.pot - (0.5 + 1.0 + alive * 0.2)) < 1e-9, "pot = sb+bb+n·ante olmalı"


def test_ante_deducted_from_every_stack():
    gl = _fresh(0.2, n=6)
    # Kör olmayan oyuncular tam ante kadar (0.2) eksilmeli
    non_blind = [p for p in gl.players if p.current_bet == 0]
    for p in non_blind:
        assert abs(p.stack - (100.0 - 0.2)) < 1e-9, f"ante kesilmedi: {p.stack}"


def test_ante_is_dead_money_not_a_live_bet():
    """Ante to_call'u ŞİŞİRMEMELİ — ölü paradır, bahis değil."""
    gl = _fresh(0.2, n=6)
    h = gl.current_hand
    non_blind_idx = next(i for i, p in enumerate(gl.players) if p.current_bet == 0)
    assert abs(h.to_call(non_blind_idx) - 1.0) < 1e-9, "to_call = bb olmalı (ante hariç)"


def test_zero_ante_adds_nothing():
    gl = _fresh(0.0, n=6)
    h = gl.current_hand
    assert abs(h.pot - 1.5) < 1e-9, "ante=0 iken pot sadece sb+bb"


def test_ante_capped_at_short_stack():
    """Ante kısa stack'ten fazlasını kesemez (all-in eder)."""
    random.seed(1)
    gl = PokerGame(num_players=4, starting_stack=100.0, small_blind=0.5,
                   big_blind=1.0, ante=0.2, hero_seat=0, paced_bots=True)
    # Bir oyuncuyu çok kısa yap
    gl.players[2].stack = 0.1
    gl.start_hand()
    # 0.1 stack'li oyuncu en fazla 0.1 ante koyabilir (negatife düşmez)
    assert gl.players[2].stack >= -1e-9


def test_tournament_levels_have_scaling_antes():
    """Turnuva blind şeması: Big Blind Ante — L1'den itibaren ante var, BB ile
    ölçeklenir (modern online MTT standardı; antesiz erken seviye yok)."""
    from app.simulator.tournament_runner import regular_structure
    levels = regular_structure()
    antes = [lvl.ante for lvl in levels]
    assert antes[0] > 0, "L1'den itibaren ante olmalı (BBA — antesiz poker yok)"
    assert all(a > 0 for a in antes), "her seviyede ante > 0 olmalı"
    # Monoton artan (azalmayan) ante
    assert antes == sorted(antes), "ante level'le artmalı (azalmamalı)"
    # BBA-eşdeğeri: ante ≈ %12.5 BB, her zaman bb'den küçük (ölü para, canlı bahis değil)
    for lvl in levels:
        assert 0 < lvl.ante < lvl.bb, f"ante ({lvl.ante}) 0<·<bb ({lvl.bb}) olmalı"
        assert abs(lvl.ante - lvl.bb * 0.125) <= 1, f"ante ≈ %12.5 bb olmalı (L{lvl.level})"


def test_tournament_syncs_ante_each_hand():
    """Tournament.start_hand her el level ante'sini motora senkronlar."""
    import random as _r
    _r.seed(5)
    from app.simulator.tournament_runner import Tournament, TournamentConfig
    t = Tournament(TournamentConfig(field_size=6, starting_chips=10000))
    t.start_hand()
    lvl = t.state.current_level
    assert t.game.ante == float(lvl.ante), "motor ante'si level ile senkron değil"
