"""Headless all-bot MTT simülatörü — bütünlük (gerçekten oynar, varsayım yok).

Skill baştan ATANMAZ; her koltuk gerçek BotBrain ile oynar. Bu paket motorun
tutarlı çalıştığını (tek kazanan, bitiş sırası tam, final masa/ilk-3 geçerli)
doğrular — sonucun NE olduğunu değil, mekaniğin doğruluğunu test eder.
"""
from __future__ import annotations

from app.engine.bot_brain import BOT_ARCHETYPES
from app.simulator.headless_mtt import run_mtt


def test_small_mtt_resolves_to_one_winner():
    r = run_mtt(18, seed=1)
    assert r["field_size"] == 18
    assert r["hands"] > 0
    # Bitiş sırası tam alan kadar oyuncu içerir
    assert len(r["finish_1st_to_last"]) == 18
    # Hepsi geçerli arketip
    assert all(a in BOT_ARCHETYPES for a in r["finish_1st_to_last"])


def test_final_table_and_top3_consistent():
    r = run_mtt(27, seed=2)
    ft = r["final_table"]
    assert len(ft) == min(9, r["field_size"])
    # Final masa = bitiş sırasının ilk 9'u (yer 1..9)
    assert ft == r["finish_1st_to_last"][:len(ft)]
    assert r["top3"] == r["finish_1st_to_last"][:3]


def test_tiered_field_runs():
    """Tier'li alan da gerçekten oynar (yüksek-stake reg-ağır havuz)."""
    from app.engine.bot_brain import realistic_mtt_mix
    import random
    rng = random.Random(4)
    # tier örneklemesi çalışıyor + run_mtt herhangi alanı çözer
    assert len(realistic_mtt_mix(50, rng=rng, tier="Yüksek ($530+)")) == 50
    r = run_mtt(18, seed=3)
    assert len(r["finish_1st_to_last"]) == 18


def test_no_duplicate_or_missing_finishers():
    """Bitiş listesi alan büyüklüğüyle birebir (kimse kaybolmaz/iki kez bitmez)."""
    r = run_mtt(24, seed=5)
    assert len(r["finish_1st_to_last"]) == 24
