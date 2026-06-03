"""Range vs Range avantajı — equity + nut avantajı (elit koç 'kim bahis atmalı')."""
from __future__ import annotations

import random

from app.poker.range_advantage import (
    coach_range_adv_line, range_vs_range,
)


def test_overpairs_beat_underpairs_on_low_board():
    """Düşük board (8-5-2): üst-çift range'i alt-çift range'ini ezer (river exact)."""
    r = range_vs_range(["AA", "KK", "QQ"], ["33", "44"],
                       "8h 5d 2c 9s Jd", rng=random.Random(1))
    assert r["range_advantage"] == "hero"
    assert r["hero_equity"] > 60


def test_nut_advantage_set_vs_overpair():
    """Board'da set yapan range, overpair range'ine karşı NUT avantajı taşır."""
    # Board 9-9-2: 99 (quads/set) vs AA (overpair) → 99 nutted
    r = range_vs_range(["99"], ["AA", "KK"], "9h 9d 2c 5s 7d",
                       rng=random.Random(2))
    assert r["nut_advantage"] == "hero"      # 99 = quads, nutted
    assert r["nut_hero"] > r["nut_villain"]


def test_symmetric_ranges_roughly_even():
    r = range_vs_range(["AK"], ["AK"], "7h 2d 9s Jc 4d", rng=random.Random(3))
    assert r["range_advantage"] == "eşit"
    assert 45 <= r["hero_equity"] <= 55


def test_equities_sum_to_100():
    r = range_vs_range(["AA", "AK", "KQ"], ["QQ", "JJ", "T9s"],
                       "Qh 8d 3c", iterations=800, rng=random.Random(4))
    assert abs((r["hero_equity"] + r["villain_equity"]) - 100.0) < 0.1


def test_flop_runout_works():
    """Flop (3 kart) → MC runout; geçerli equity döner."""
    r = range_vs_range(["AA"], ["72o"], "Ah Kd 5c", iterations=600,
                       rng=random.Random(5))
    assert r["hero_equity"] > 80              # AA seti vs 72 air, board A-high
    assert 0 <= r["villain_equity"] <= 20


def test_coach_line_renders():
    r = range_vs_range(["AA", "KK"], ["QQ", "JJ"], "2h 7d Tc Ks 4d",
                       rng=random.Random(6))
    line = coach_range_adv_line(r)
    assert "Range avantajı" in line and "Nut avantajı" in line
