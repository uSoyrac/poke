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


def test_gto_accuracy_trend(isolated_db):
    R = isolated_db
    # On-line decisions (raise 100, hero RAISE → freq_error 0 → on-GTO)
    good = [{
        "available": True, "street": "Preflop", "scenario": "RFI",
        "fold": 0, "call": 0, "raise": 100, "allin": 0,
        "equity": 0, "pot_bb": 2, "to_call_bb": 0,
        "hero_action": "RAISE", "hero_amount": 2.5,
    } for _ in range(6)]
    R.record_decision_log(good)
    trend = R.get_gto_accuracy_trend()
    assert len(trend) >= 1
    today = trend[-1]
    assert today["decisions"] == 6
    assert today["accuracy"] == 100.0    # hepsi GTO çizgisinde


def test_gto_accuracy_trend_empty(isolated_db):
    assert isolated_db.get_gto_accuracy_trend() == []


def test_gto_category_accuracy(isolated_db):
    R = isolated_db
    # vs 3-bet: hepsi GTO-dışı fold (freq_error yüksek → düşük accuracy)
    R.record_decision_log(_over_fold_vs_3bet(10))
    cats = R.get_gto_category_accuracy()
    assert "vs 3-bet" in cats
    assert cats["vs 3-bet"]["n"] == 10
    assert cats["vs 3-bet"]["accuracy"] == 0.0   # tümü sapma


def test_gto_category_accuracy_empty(isolated_db):
    assert isolated_db.get_gto_category_accuracy() == {}


def test_mistake_spots_persist_and_retrieve(isolated_db):
    R = isolated_db
    # GTO raise %80, hero FOLD (büyük sapma) — gerçek board/kart ile
    log = [{
        "available": True, "street": "Flop", "scenario": "Postflop (Flop · dry · IP)",
        "fold": 10, "call": 10, "raise": 80, "allin": 0,
        "equity": 68, "pot_bb": 12, "to_call_bb": 6,
        "hero_action": "FOLD", "hero_amount": 0,
        "board": "Ah 7c 2d", "hero_combo": "AsKs", "hero_cards_disp": "A♠ K♠",
        "hero_position": "BTN", "n_active": 2, "eff_stack_bb": 95, "pot_type": "SRP",
    }]
    R.record_decision_log(log)
    spots = R.get_mistake_spots()
    assert len(spots) == 1
    s = spots[0]
    assert s["board"] == "Ah 7c 2d"
    assert s["best_action"] == "raise" and s["your_action"] == "fold"
    assert s["ev_loss"] > 0
    assert s["table"] == "HU" and s["position"] == "BTN"


def test_mistake_spots_skips_good_decisions(isolated_db):
    R = isolated_db
    # GTO raise %80, hero RAISE (doğru) → hata-spotu KAYDEDİLMEZ
    log = [{
        "available": True, "street": "Flop", "scenario": "Postflop",
        "fold": 10, "call": 10, "raise": 80, "allin": 0,
        "equity": 68, "pot_bb": 12, "to_call_bb": 0,
        "hero_action": "RAISE", "hero_amount": 4,
        "board": "Ah 7c 2d", "hero_combo": "AsKs", "hero_position": "BTN",
        "n_active": 2, "eff_stack_bb": 95, "pot_type": "SRP",
    }]
    R.record_decision_log(log)
    assert R.get_mistake_spots() == []


def test_mistake_spots_empty(isolated_db):
    assert isolated_db.get_mistake_spots() == []


def test_position_leaks_and_self_insights(isolated_db):
    R = isolated_db
    # UTG'de tekrar tekrar büyük sapma → pozisyon leak + zayıf-yön
    log = [{
        "available": True, "street": "Flop", "scenario": "Postflop",
        "fold": 5, "call": 10, "raise": 85, "allin": 0,
        "equity": 70, "pot_bb": 12, "to_call_bb": 6,
        "hero_action": "FOLD", "hero_amount": 0,
        "board": "Ah 7c 2d", "hero_combo": "AsKs", "hero_position": "UTG",
        "n_active": 2, "eff_stack_bb": 95, "pot_type": "SRP",
    }]
    for _ in range(4):
        R.record_decision_log([dict(log[0])])
    pl = R.get_position_leaks()
    assert pl and pl[0]["position"] == "UTG" and pl[0]["ev_lost"] > 0
    ins = R.get_self_insights()
    assert isinstance(ins["strengths"], list) and isinstance(ins["weaknesses"], list)
    # UTG EV kaybı zayıf-yön olarak çıkmalı
    assert any("UTG" in w for w in ins["weaknesses"])


def test_self_insights_empty(isolated_db):
    ins = isolated_db.get_self_insights()
    assert ins["strengths"] == [] and ins["weaknesses"] == []


def test_segmented_insights_early_short_overraise(isolated_db):
    R = isolated_db
    # Erken pozisyon + sığ stack: GTO fold derken raise (gereksiz agresyon)
    for _ in range(4):
        R.record_decision_log([{
            "available": True, "street": "Preflop", "scenario": "RFI",
            "fold": 85, "call": 0, "raise": 15, "allin": 0,
            "equity": 0, "pot_bb": 3, "to_call_bb": 0,
            "hero_action": "RAISE", "hero_amount": 2.5, "board": "",
            "hero_combo": "Jd9c", "hero_position": "UTG", "n_active": 8,
            "eff_stack_bb": 16, "pot_type": "SRP"}])
    segs = R.get_segmented_insights()
    assert segs, "segment çıkmalı"
    top = segs[0]
    assert "erken pozisyon" in top["segment"] and "sığ stack" in top["segment"]
    assert top["n"] == 4 and "raise" in top["pattern"].lower()


def test_segmented_insights_empty(isolated_db):
    assert isolated_db.get_segmented_insights() == []


def test_segmented_insights_mtt_stage_label(isolated_db):
    """MTT · aşama · masa boyutu etiket dimensiyonları."""
    R = isolated_db
    for _ in range(4):
        R.record_decision_log([{
            "available": True, "street": "Preflop", "scenario": "RFI",
            "fold": 85, "call": 0, "raise": 15, "allin": 0,
            "equity": 0, "pot_bb": 3, "to_call_bb": 0,
            "hero_action": "RAISE", "hero_amount": 2.5, "board": "",
            "hero_combo": "Jd9c", "hero_position": "UTG", "n_active": 6,
            "eff_stack_bb": 16, "pot_type": "SRP",
            "format": "mtt", "stage": "orta aşama"}])
    segs = R.get_segmented_insights()
    assert segs
    seg = segs[0]["segment"]
    # format + aşama + short-handed (6) + erken poz + sığ stack hepsi etikette
    assert "MTT" in seg and "orta aşama" in seg
    assert "short-handed" in seg
    assert "erken pozisyon" in seg and "sığ stack" in seg


def test_segmented_insights_cash_hides_defaults(isolated_db):
    """cash + full-ring (7+) → format/masa token'ları etikette gizlenir."""
    R = isolated_db
    for _ in range(4):
        R.record_decision_log([{
            "available": True, "street": "Preflop", "scenario": "RFI",
            "fold": 85, "call": 0, "raise": 15, "allin": 0,
            "equity": 0, "pot_bb": 3, "to_call_bb": 0,
            "hero_action": "RAISE", "hero_amount": 2.5, "board": "",
            "hero_combo": "Jd9c", "hero_position": "UTG", "n_active": 9,
            "eff_stack_bb": 16, "pot_type": "SRP",
            "format": "cash", "stage": ""}])
    seg = R.get_segmented_insights()[0]["segment"]
    assert seg == "erken pozisyon · sığ stack (≤20bb)"
