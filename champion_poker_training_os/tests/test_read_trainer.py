"""Rakip-okuma trainer motoru (geliştirme #2).

Bir villain'in davranışından (stat + aksiyon log) tipini ve exploit'ini OKUMA
becerisini drill'ler. Ground-truth opponent_typology.classify_hellmuth'tan
(tek kaynak) → gerçek bot tiplemesiyle tutarlı.
"""
from __future__ import annotations

import random

from app.poker.read_trainer import generate_read_drill, score_read
from app.poker.opponent_typology import classify_hellmuth


def test_drill_is_valid():
    d = generate_read_drill(random.Random(1))
    assert d.correct_type in d.choices
    assert d.stats.get("vpip", 0) > 0
    assert d.action_log                      # davranış ipuçları var
    assert d.correct_exploit                 # exploit önerisi var
    assert len(d.choices) >= 4


def test_correct_type_matches_typology():
    d = generate_read_drill(random.Random(7))
    _, name, _ = classify_hellmuth(d.stats["vpip"], d.stats["pfr"],
                                   d.stats["af"], d.stats.get("river_bluff", 0))
    assert d.correct_type == name            # ground-truth tek kaynak


def test_score_correct_guess():
    d = generate_read_drill(random.Random(3))
    r = score_read(d.correct_type, d)
    assert r["correct"] is True
    assert r["exploit"] == d.correct_exploit


def test_score_wrong_guess_explains():
    d = generate_read_drill(random.Random(4))
    wrong = next(c for c in d.choices if c != d.correct_type)
    r = score_read(wrong, d)
    assert r["correct"] is False
    assert d.correct_type in r["explanation"]   # doğruyu açıklar


def test_variety_across_seeds():
    types = {generate_read_drill(random.Random(s)).correct_type
             for s in range(40)}
    assert len(types) >= 3                   # farklı tipler üretiliyor
