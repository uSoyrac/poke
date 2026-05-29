"""Karar notlandırma motoru (Phase D1) — saf fonksiyon birim testleri."""
from __future__ import annotations

from app.poker.decision_grade import grade_decision, grade_hand


def _snap(**kw) -> dict:
    base = {
        "available": True, "street": "Preflop", "scenario": "RFI",
        "fold": 0, "call": 0, "raise": 0, "allin": 0,
        "equity": 0, "pot_bb": 0, "to_call_bb": 0,
        "hero_action": "RAISE", "hero_amount": 2.5,
    }
    if "raise_" in kw:                 # 'raise' is a Python keyword
        kw["raise"] = kw.pop("raise_")
    base.update(kw)
    return base


def test_a_when_hero_picks_top_frequency_action():
    # GTO raise %100, hero RAISE → A
    g = grade_decision(_snap(raise_=100, hero_action="RAISE"))
    assert g.letter == "A" and g.score == 100


def test_a_when_hero_freq_high_even_if_not_max():
    # GTO call 65 / raise 35; hero CALL (65 >= 60) → A
    g = grade_decision(_snap(call=65, raise_=35, hero_action="CALL"))
    assert g.letter == "A"


def test_b_grade_band():
    # hero action freq 40 (35..59) → B
    g = grade_decision(_snap(call=40, raise_=45, fold=15, hero_action="CALL"))
    # raise is max(45) so CALL(40) isn't top → 40 in [35,60) → B
    assert g.letter == "B"


def test_c_grade_band():
    g = grade_decision(_snap(call=20, raise_=60, fold=20, hero_action="CALL"))
    assert g.letter == "C"


def test_d_when_off_gto():
    # GTO almost never folds here (fold 5), hero FOLD → D
    g = grade_decision(_snap(fold=5, call=70, raise_=25, hero_action="FOLD"))
    assert g.letter == "D"


def test_check_maps_to_call_slot():
    g = grade_decision(_snap(call=80, raise_=20, hero_action="CHECK"))
    assert g.letter == "A"


def test_ev_overlay_caps_at_c():
    # hero would be A by freq, but big EV loss caps to C
    g = grade_decision(_snap(
        fold=10, call=70, raise_=20, hero_action="CALL",
        equity=20, pot_bb=10, to_call_bb=8,   # -EV call
    ))
    # call EV = .20*18 - 8 = -4.4 → ev_loss 4.4 > 4 → F
    assert g.letter == "F"
    assert g.ev_loss > 4


def test_ev_overlay_moderate_caps_c():
    # moderate -EV (between 1.5 and 4) caps an A/B down to C
    g = grade_decision(_snap(
        fold=10, call=70, raise_=20, hero_action="CALL",
        equity=35, pot_bb=10, to_call_bb=6,
    ))
    # EV = .35*16 - 6 = -0.4 ... too small; tune: equity 30 → .30*16-6=-1.2 still <1.5
    # Use equity 25: .25*16-6 = -2.0 → between 1.5 and 4 → cap C
    g2 = grade_decision(_snap(
        fold=10, call=70, raise_=20, hero_action="CALL",
        equity=25, pot_bb=10, to_call_bb=6,
    ))
    assert g2.letter == "C"


def test_unavailable_returns_none_grade():
    g = grade_decision(_snap(available=False))
    assert g.letter == "N/A" and g.score is None


def test_grade_hand_averages():
    decisions = [
        _snap(raise_=100, hero_action="RAISE"),          # A=100
        _snap(call=20, raise_=60, fold=20, hero_action="CALL"),  # C=60
    ]
    hg = grade_hand(decisions)
    assert hg.n_decisions == 2
    assert 78 <= hg.score <= 82          # (100+60)/2 = 80
    assert hg.letter == "B"


def test_grade_hand_skips_unavailable():
    decisions = [
        _snap(raise_=100, hero_action="RAISE"),   # graded
        _snap(available=False),                  # skipped
    ]
    hg = grade_hand(decisions)
    assert hg.n_decisions == 1 and hg.score == 100


def test_grade_hand_empty():
    hg = grade_hand([])
    assert hg.n_decisions == 0 and hg.letter == "N/A"
