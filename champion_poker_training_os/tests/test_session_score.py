"""Oturum skor kartı (Phase D2) testleri."""
from __future__ import annotations

from app.poker.session_score import SessionScore


def _d(street, hero, **freq):
    base = {"available": True, "street": street, "scenario": street,
            "fold": 0, "call": 0, "raise": 0, "allin": 0,
            "equity": 0, "pot_bb": 0, "to_call_bb": 0,
            "hero_action": hero, "hero_amount": 1.0}
    if "raise_" in freq:
        freq["raise"] = freq.pop("raise_")
    base.update(freq)
    return base


def test_empty_summary():
    s = SessionScore()
    assert s.summary()["n_hands"] == 0
    assert s.accuracy == 0.0


def test_accumulates_hands_and_accuracy():
    s = SessionScore()
    # Hand 1: one A decision (raise 100, hero RAISE)
    s.add_hand([_d("Preflop", "RAISE", raise_=100)])
    # Hand 2: one D decision (fold 5, hero FOLD)
    s.add_hand([_d("Flop", "FOLD", fold=5, call=70, raise_=25)])
    summ = s.summary()
    assert summ["n_hands"] == 2
    assert summ["n_decisions"] == 2
    # 1 of 2 is A/B → accuracy 50%
    assert summ["accuracy"] == 50.0


def test_skips_unavailable_decisions():
    s = SessionScore()
    s.add_hand([{"available": False, "hero_action": "FOLD"}])
    # No gradeable decision → hand not counted
    assert s.summary()["n_hands"] == 0


def test_weakest_category():
    s = SessionScore()
    # Preflop strong (two A), Turn weak (two D)
    s.add_hand([_d("Preflop", "RAISE", raise_=100),
                _d("Turn", "FOLD", fold=5, call=80, raise_=15)])
    s.add_hand([_d("Preflop", "RAISE", raise_=100),
                _d("Turn", "FOLD", fold=5, call=80, raise_=15)])
    assert s.weakest_category() == "Turn"


def test_ev_lost_accumulates():
    s = SessionScore()
    # -EV call: equity 20, pot 10, call 8 → ev_loss 4.4
    s.add_hand([_d("Flop", "CALL", fold=10, call=70, raise_=20,
                   equity=20, pot_bb=10, to_call_bb=8)])
    assert s.summary()["ev_lost"] > 4


def test_reset():
    s = SessionScore()
    s.add_hand([_d("Preflop", "RAISE", raise_=100)])
    s.reset()
    assert s.summary()["n_hands"] == 0 and s.n_decisions == 0
