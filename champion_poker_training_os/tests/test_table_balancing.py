"""Multi-table masa dengeleme — MTTField.move_into_hero_table +
Tournament.rebalance_hero_table (kırılan masalardan oyuncu taşıma)."""
from __future__ import annotations

from app.simulator.mtt_field import MTTField
from app.simulator.tournament_runner import Tournament, TournamentConfig


# ── MTTField: oyuncu taşıma toplam sahayı korur ──────────────────────
def test_move_into_hero_table_preserves_total():
    f = MTTField(field_size=200, hero_table_size=9)
    total_before = f.players_remaining
    bg_before = f.bg_players_remaining
    moved = f.move_into_hero_table(5)
    assert moved == 5
    assert f.players_remaining == total_before        # toplam DEĞİŞMEZ
    assert f.bg_players_remaining == bg_before - 5     # arka plandan düştü


def test_move_capped_by_background():
    f = MTTField(field_size=12, hero_table_size=9)   # bg = 3
    moved = f.move_into_hero_table(10)
    assert moved == 3                                  # bg ile sınırlı
    assert f.bg_players_remaining == 0


def test_is_final_table():
    f = MTTField(field_size=200, hero_table_size=9)
    assert not f.is_final_table
    f.update_hero_table(9)
    f._bg = {"weak": 0, "mid": 0, "strong": 0}         # sadece hero masası kaldı
    assert f.is_final_table


# ── Tournament: masa dengeleme taze profil/isimle koltuk doldurur ────
def test_rebalance_reseats_with_fresh_profiles():
    cfg = TournamentConfig(field_size=9, starting_chips=10000,
                           bot_mix=["Shark", "Nit", "LAG", "Fish"])
    t = Tournament(cfg)
    # 5 botu ele → masada 4 oyuncu (hero + 3)
    elim_seats = [i for i, p in enumerate(t.game.players) if not p.is_hero][:5]
    for i in elim_seats:
        t.game.players[i].is_eliminated = True
        t.state.eliminated_order.append(i)
    old_names = {i: t.game.players[i].name for i in elim_seats}

    seated = t.rebalance_hero_table(target_size=9, avg_stack=8000)
    assert seated == 5                                 # 5 koltuk dolduruldu
    active = [p for p in t.game.players if not p.is_eliminated]
    assert len(active) == 9                            # masa tam
    # Yeniden oturanlar TAZE: yeni isim + bot_mix'ten arketip
    for i in elim_seats:
        p = t.game.players[i]
        assert not p.is_eliminated
        assert p.stack == 8000
        assert p.name != old_names[i]                  # yeni oyuncu (yeni isim)
        assert i in t.game.bots                         # taze BotBrain


def test_rebalance_never_touches_hero():
    cfg = TournamentConfig(field_size=9, starting_chips=10000)
    t = Tournament(cfg)
    hero_i = next(i for i, p in enumerate(t.game.players) if p.is_hero)
    for i, p in enumerate(t.game.players):
        if not p.is_hero:
            p.is_eliminated = True
    t.rebalance_hero_table(target_size=9, avg_stack=5000)
    assert t.game.players[hero_i].is_hero
    assert hero_i not in t.game.bots                   # hero asla bot olmaz


def test_rebalance_noop_when_table_full():
    cfg = TournamentConfig(field_size=9, starting_chips=10000)
    t = Tournament(cfg)
    assert t.rebalance_hero_table(target_size=9, avg_stack=5000) == 0
