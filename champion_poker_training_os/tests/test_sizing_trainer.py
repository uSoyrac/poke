"""Bet-sizing trainer motoru (geliştirme #4).

'Raise/bet dedin → kaç bb / pot'un %kaçı?' drill'i. GTO-önerilen size'a göre
quality% + EV-loss + verdict döner. Puanlama tek kaynak: sizing_advice.SizingAdvice.score.
"""
from __future__ import annotations

import random

from app.poker.sizing_trainer import generate_sizing_drill, score_sizing


def test_drill_is_valid():
    d = generate_sizing_drill(random.Random(1))
    assert d.recommended_bb > 0
    assert d.pot_bb > 0
    assert d.choices_bb and len(d.choices_bb) >= 3
    assert d.scenario
    assert d.recommended_bb in d.choices_bb   # doğru cevap seçenekler arasında


def test_correct_size_scores_high():
    d = generate_sizing_drill(random.Random(2))
    r = score_sizing(d.recommended_bb, d)
    assert r["quality_pct"] >= 80          # tam GTO size → mükemmel
    assert r["ev_loss_bb"] < 0.5


def test_way_off_size_scores_low():
    d = generate_sizing_drill(random.Random(3))
    way_off = d.recommended_bb * 3.0       # 3x fazla → kötü
    r = score_sizing(way_off, d)
    assert r["quality_pct"] < 60
    assert r["ev_loss_bb"] >= score_sizing(d.recommended_bb, d)["ev_loss_bb"]


def test_variety_across_seeds():
    scen = {generate_sizing_drill(random.Random(s)).scenario_key for s in range(30)}
    assert len(scen) >= 2                  # farklı senaryo tipleri


def test_choices_include_pot_fractions_or_bb():
    d = generate_sizing_drill(random.Random(5))
    # Tüm seçenekler pozitif bb değerleri
    assert all(c > 0 for c in d.choices_bb)
