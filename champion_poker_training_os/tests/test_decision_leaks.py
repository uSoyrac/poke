"""hero_decisions persistence + data-driven leak detection (#52)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Her test izole bir SQLite DB kullanır (gerçek DB'ye dokunmaz)."""
    from app.db import repository as R
    db = tmp_path / "test.db"
    monkeypatch.setattr(R, "DB_PATH", db)
    R.initialize_database()
    return R


def _over_fold_vs_3bet(n: int) -> list:
    """GTO call/raise derken hero FOLD eden n karar (over-fold leak)."""
    return [{
        "available": True, "street": "Preflop", "scenario": "vs 3-bet",
        "fold": 10, "call": 70, "raise": 20, "allin": 0,
        "equity": 55, "pot_bb": 22, "to_call_bb": 9,
        "hero_action": "FOLD", "hero_amount": 0,
    } for _ in range(n)]


def test_record_skips_unavailable_and_no_action(isolated_db):
    R = isolated_db
    log = [
        {"available": False, "hero_action": "FOLD"},          # no GTO data
        {"available": True, "hero_action": None,               # not acted
         "fold": 50, "call": 50, "raise": 0, "allin": 0},
        {"available": True, "hero_action": "CALL", "street": "Flop",
         "scenario": "Postflop", "fold": 20, "call": 70, "raise": 10,
         "allin": 0, "equity": 60, "pot_bb": 10, "to_call_bb": 3},
    ]
    assert R.record_decision_log(log) == 1   # only the 3rd is persisted


def test_over_fold_vs_3bet_detected(isolated_db):
    R = isolated_db
    R.record_decision_log(_over_fold_vs_3bet(12))
    leaks = R.get_decision_leaks(min_sample=8)
    names = [l["name"] for l in leaks]
    assert any("Over-folding" in n and "vs 3-bet" in n for n in names), names
    top = leaks[0]
    assert top["ev_lost"] > 0          # +EV spotu fold etmek EV kaybettirir
    assert top["sample_size"] == 12


def test_min_sample_gate(isolated_db):
    R = isolated_db
    R.record_decision_log(_over_fold_vs_3bet(3))   # below threshold
    assert R.get_decision_leaks(min_sample=8) == []


def test_freq_error_zero_when_on_gto_line(isolated_db):
    """Hero GTO'nun yüksek frekanslı aksiyonunu seçerse sapma az olmalı."""
    R = isolated_db
    # GTO call %70 → hero CALL → frequency_error = 100-70 = 30 (kabul edilebilir)
    log = [{
        "available": True, "street": "Flop", "scenario": "Postflop",
        "fold": 20, "call": 70, "raise": 10, "allin": 0,
        "equity": 60, "pot_bb": 10, "to_call_bb": 3,
        "hero_action": "CALL", "hero_amount": 3,
    } for _ in range(10)]
    R.record_decision_log(log)
    leaks = R.get_decision_leaks(min_sample=8)
    # On-line oynanan, +EV call → over-fold/spew leak'i OLMAMALI
    assert not any("Over-folding" in l["name"] or "spew" in l["name"]
                   for l in leaks), leaks


def test_leak_analysis_combines_sources(isolated_db):
    R = isolated_db
    R.record_decision_log(_over_fold_vs_3bet(12))
    combined = R.get_leak_analysis()
    assert any("Over-folding" in l["name"] for l in combined)
