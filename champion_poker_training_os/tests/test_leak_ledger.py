"""Leak-ledger — kalıcı drill öz-bilgisi + spaced repetition.

Kritik ilke: bir leak ancak GECİKMELİ re-test'i geçince (≥1 gün) 'çözüldü'
sayılır — tek oturumda mükemmel oynamak yetmez.
"""
from __future__ import annotations

from app.poker.leak_ledger import compute_status, next_review_hours

_DAY = 86400.0


def test_next_review_grows_with_streak():
    assert next_review_hours(0) == 0
    assert next_review_hours(1) < next_review_hours(3) < next_review_hours(5)
    assert next_review_hours(9) == next_review_hours(5)   # tavan


def test_new_when_few_attempts():
    s = compute_status(3, 3, 3, 0.0, 0.0, 0.0)
    assert "yeni" in s["status"] and not s["resolved"]


def test_active_leak_low_accuracy():
    s = compute_status(20, 8, 0, 0.0, 100.0, 200.0)   # %40
    assert "aktif leak" in s["status"] and not s["resolved"]


def test_not_resolved_same_session_even_if_perfect():
    """Aynı oturumda (span<1 gün) yüksek doğruluk + streak → çözülmez."""
    s = compute_status(20, 19, 8, 0.0, 3600.0, 3600.0)  # ~1 saat span
    assert not s["resolved"]
    assert "re-test bekliyor" in s["status"]


def test_resolved_after_delayed_retest():
    """≥1 gün span + yüksek doğruluk + streak ≥5 → çözüldü."""
    first = 0.0
    last = 3 * _DAY                                    # 3 gün sonra
    s = compute_status(25, 22, 6, first, last, last)
    assert s["resolved"]
    assert "çözüldü" in s["status"]


def test_db_record_and_get(tmp_path, monkeypatch):
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "ledger.db")
    R.initialize_database()
    cat = "River Bluff-Catch (combo)"
    t0 = 1_000_000.0
    # 10 tekrar, 8 doğru, aynı gün
    for i in range(10):
        R.record_drill_result(cat, correct=(i % 5 != 0), now=t0 + i * 60)
    led = [r for r in R.get_leak_ledger(now=t0 + 700) if r["category"] == cat]
    assert led and led[0]["attempts"] == 10
    assert led[0]["correct"] == 8
    assert 70 <= led[0]["accuracy"] <= 90
    # aynı gün → çözülmemiş
    assert not led[0]["resolved"]


def test_db_streak_resets_on_wrong():
    import tempfile, os
    from app.db import repository as R
    import importlib
    db = tempfile.mkdtemp() + "/l2.db"
    R.DB_PATH = __import__("pathlib").Path(db)
    R.initialize_database()
    cat = "X"
    R.record_drill_result(cat, True, now=1.0)
    R.record_drill_result(cat, True, now=2.0)
    R.record_drill_result(cat, False, now=3.0)   # streak sıfırlanır
    row = [r for r in R.get_leak_ledger(now=4.0) if r["category"] == cat][0]
    assert row["streak"] == 0
    assert row["attempts"] == 3 and row["correct"] == 2
