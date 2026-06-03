"""Combo-sayım antrenörü üretici + grader."""
from __future__ import annotations

import random

from app.poker.combo_drill import generate_spot, grade


def test_spot_is_valid_river_bluff_catch():
    s = generate_spot(rng=random.Random(1))
    assert s["street"] == "river"
    assert len(s["board"].split()) == 5
    assert len(s["hero_cards"].split()) == 2
    a = s["analysis"]
    # Anlamlı: hem value hem bluff combo var
    assert a["value_combos"] >= 2 and a["bluff_combos"] >= 2
    assert s["correct_action"] in ("CALL", "FOLD")
    assert "villain_style" in s


def test_no_card_overlap():
    """Hero + board kartları çakışmaz (geçerli deste)."""
    for seed in range(20):
        s = generate_spot(rng=random.Random(seed))
        cards = s["hero_cards"].split() + s["board"].split()
        assert len(cards) == len(set(cards)), f"çakışan kart: {cards}"


def test_grade_correct_and_wrong():
    s = generate_spot(rng=random.Random(3))
    correct = s["correct_action"]
    wrong = "FOLD" if correct == "CALL" else "CALL"
    assert grade(s, correct)["correct"] is True
    assert grade(s, wrong)["correct"] is False


def test_produces_both_call_and_fold_spots():
    """Çeşitlilik: 40 spotta hem CALL hem FOLD çıkmalı (tek yönlü değil)."""
    rng = random.Random(7)
    acts = [generate_spot(rng=rng)["correct_action"] for _ in range(40)]
    assert "CALL" in acts and "FOLD" in acts


def test_correct_action_matches_analysis():
    s = generate_spot(rng=random.Random(11))
    a = s["analysis"]
    expected = "CALL" if a["call_ok"] else "FOLD"
    assert s["correct_action"] == expected
    # call_ok: kazanma% >= gereken equity
    assert a["call_ok"] == (a["win_pct"] >= a["needed_equity"])
