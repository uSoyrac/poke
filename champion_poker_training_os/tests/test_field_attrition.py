"""MTT arka-plan alanı: skill-korelasyonlu hayatta kalma.

Gerçek MTT: zayıf oyuncular daha hızlı patlar (spew) → alan derinleştikçe
gerçekçi şekilde GÜÇLÜYE kayar. Toplam eleme sayısı (Poisson) değişmez;
sadece HANGİ skill kovasından elendiği kırılganlık-ağırlıklıdır.
"""
from __future__ import annotations

import random

from app.simulator.mtt_field import MTTField


def _drain(field: MTTField, target_remaining: int, max_ticks: int = 100000):
    ticks = 0
    while field.players_remaining > target_remaining and ticks < max_ticks:
        before = field.players_remaining
        field.tick()
        ticks += 1
        if field.players_remaining == before:
            field.tick()  # nudge


def test_initial_composition_is_realistic():
    f = MTTField(field_size=200, hero_table_size=9)
    comp = f.bg_composition
    assert 0.55 <= comp["weak"] <= 0.68, f"weak başlangıç %{comp['weak']*100:.0f}"
    assert 0.20 <= comp["mid"] <= 0.32
    assert 0.08 <= comp["strong"] <= 0.18
    # toplam = arka plan
    assert sum(f._bg.values()) == f.bg_players_remaining


def test_field_skews_stronger_as_it_drains():
    """Alan küçüldükçe güçlü oranı ARTAR (skill-korelasyonlu hayatta kalma)."""
    random.seed(11)
    f = MTTField(field_size=500, hero_table_size=9)
    start_strong = f.strong_fraction
    _drain(f, target_remaining=80)
    late_strong = f.strong_fraction
    assert late_strong > start_strong + 0.05, (
        f"güçlü oran artmalı: başlangıç %{start_strong*100:.0f} → "
        f"geç %{late_strong*100:.0f}")


def test_weak_depletes_faster_than_strong():
    random.seed(7)
    f = MTTField(field_size=400, hero_table_size=9)
    w0, s0 = f._bg["weak"], f._bg["strong"]
    _drain(f, target_remaining=120)
    # Zayıfların düşüş ORANI güçlülerden büyük olmalı
    weak_drop = (w0 - f._bg["weak"]) / max(1, w0)
    strong_drop = (s0 - f._bg["strong"]) / max(1, s0)
    assert weak_drop > strong_drop, (
        f"zayıf düşüş %{weak_drop*100:.0f} > güçlü %{strong_drop*100:.0f}")


def test_total_elimination_count_unchanged_invariant():
    """Kova modeli toplam eleme sayısını BOZMAZ — players_remaining tutarlı."""
    random.seed(3)
    f = MTTField(field_size=180, hero_table_size=9)
    total_elim = 0
    for _ in range(200):
        total_elim += f.tick()
    assert f.bg_players_remaining == (180 - 9) - total_elim
    assert f.players_remaining == 180 - total_elim


def test_move_into_hero_table_still_works():
    """Table balancing API korunur: arka plandan hero masasına taşır."""
    f = MTTField(field_size=200, hero_table_size=9)
    bg0 = f.bg_players_remaining
    moved = f.move_into_hero_table(3)
    assert moved == 3
    assert f.bg_players_remaining == bg0 - 3
    assert f._hero_table_remaining == 12
    # toplam saha değişmez
    assert f.players_remaining == 200


def test_field_strength_label():
    """Etiket: başlangıç 'soft', alan drenajından sonra daha sert; bg boşsa ''."""
    f = MTTField(field_size=300, hero_table_size=9)
    start = f.field_strength_label()
    assert start and "güçlü" in start
    random.seed(5)
    _drain(f, target_remaining=60)
    late = f.field_strength_label()
    # Geç aşamada güçlü oranı arttığı için etiket boş değil ve sayı yüksek
    assert late and "güçlü" in late
    # Arka plan tamamen bitince etiket boş
    f._bg = {"weak": 0, "mid": 0, "strong": 0}
    assert f.field_strength_label() == ""


def test_buckets_never_go_negative():
    random.seed(99)
    f = MTTField(field_size=120, hero_table_size=9)
    for _ in range(5000):
        f.tick()
        if f.bg_players_remaining <= 0:
            break
    assert all(v >= 0 for v in f._bg.values())
