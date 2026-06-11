"""Soyrac Akademi müfredat+drill motoru."""
import random
from app.poker.soyrac_curriculum import (
    MODULES, module_list, make_drill, grade_drill, compute_badge, belt, _norm_action)


def test_modules_structure():
    assert list(MODULES) == ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    for m in module_list():
        assert m["title"] and m["analogy"] and m["learn_bullets"]
        assert m["fig_key"] and len(m["learn_bullets"]) >= 3


def test_make_drill_preflop():
    rng = random.Random(1)
    for mk in ["M1", "M2", "M3", "M4", "M7"]:
        d = make_drill(mk, difficulty=1, rng=rng)
        assert d is not None, mk
        assert d.hand_key and d.explain.get("action")
        assert d.correct in ("RAISE (AÇ)", "CALL", "FOLD", "3-BET", "4-BET", "JAM")


def test_make_drill_postflop():
    rng = random.Random(2)
    d = make_drill("M5", difficulty=1, rng=rng)
    assert d is not None and d.board and len(d.board) >= 3
    assert d.explain.get("phase") == "postflop"
    assert d.explain.get("tier")


def test_grade_correct():
    rng = random.Random(3)
    d = make_drill("M2", difficulty=1, rng=rng)
    res = grade_drill(d, d.correct)        # doğru cevap
    assert res.is_correct and res.leak_category is None
    assert res.chain_steps


def test_grade_wrong_leak():
    # RFI fold elinde RAISE dersek → leak
    rng = random.Random(5)
    d = None
    for _ in range(40):
        c = make_drill("M2", difficulty=1, rng=rng)
        if _norm_action(c.correct) == "FOLD":
            d = c; break
    assert d is not None
    res = grade_drill(d, "RAISE")
    assert not res.is_correct and res.leak_category


def test_badge_belt():
    m = MODULES["M2"]
    assert compute_badge(0.9, 7, m) == "🥈"
    assert compute_badge(0.9, 7, m, leak_resolved=True) == "🥇"
    assert compute_badge(0.5, 2, m) == ""
    assert "Çırağı" in belt(["🥈", "", "", "", "", "", ""])
    assert "Ustası" in belt(["🥈"] * 7)
