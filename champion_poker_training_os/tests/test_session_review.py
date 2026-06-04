"""Oturum-sonu review CTA (geliştirme #5): GTO karne + en zayıf alanlar +
Leak Finder'da drill yönlendirmesi. SessionScore.summary()'den üretilir."""
from __future__ import annotations

from app.ai.coach_engine import session_review


def test_empty_when_no_decisions():
    assert session_review({}) == ""
    assert session_review({"n_decisions": 0}) == ""
    assert session_review(None) == ""


def test_review_has_accuracy_weakest_and_drill_cta():
    r = session_review({"n_decisions": 12, "accuracy": 58, "ev_lost": 4.3,
                        "weakest": "river",
                        "by_cat": {"river": 40, "flop": 70, "preflop": 85}})
    assert "OTURUM REVIEW" in r
    assert "%58" in r and "4.3bb" in r
    assert "river" in r                 # öncelik (weakest)
    assert "Leak Finder" in r           # drill CTA


def test_worst_three_categories_listed_not_best():
    r = session_review({"n_decisions": 20, "accuracy": 70, "ev_lost": 2.0,
                        "weakest": "a",
                        "by_cat": {"a": 30, "b": 40, "c": 50, "d": 90}})
    assert "a (%30)" in r and "b (%40)" in r and "c (%50)" in r
    assert "d (%90)" not in r            # en iyi alan listelenmez
