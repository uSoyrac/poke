"""Growth & Edge Lab matematik motoru — bilinen-değer + değişmez doğrulaması.

Üstel büyümenin iki şartı sayısallaştırılıyor: (1) edge var mı (Kelly>0),
(2) hayatta kalma (risk of ruin). Formüller standart kaynaklarla (Kelly 1956,
Chen/Ankenman risk-of-ruin) doğrulanır.
"""
from __future__ import annotations

import math

import pytest

from app.poker.growth_lab import (
    analyze_bankroll, analyze_edge, bankroll_for_ror, capital_multiple,
    expected_value, kelly_fraction, log_growth_rate, risk_of_ruin,
    trials_to_double,
)


# ── Kelly bilinen değerler ───────────────────────────────────────────
def test_kelly_even_money_60_40():
    # p=0.6, even money (g=l=1) → f* = 2p-1 = 0.2
    assert kelly_fraction(0.6, 1.0, 1.0) == pytest.approx(0.2, abs=1e-9)


def test_kelly_2to1_odds():
    # p=0.5, b=2 → f* = (p·b − q)/b = (1−0.5)/2 = 0.25
    assert kelly_fraction(0.5, 2.0, 1.0) == pytest.approx(0.25, abs=1e-9)


def test_kelly_zero_when_no_edge():
    assert kelly_fraction(0.5, 1.0, 1.0) == pytest.approx(0.0, abs=1e-9)


def test_kelly_clamped_zero_when_negative_edge():
    assert kelly_fraction(0.4, 1.0, 1.0) == 0.0   # negatif edge → bahis yok


# ── Kelly büyümeyi maksimize eder (tanımsal değişmez) ────────────────
def test_kelly_maximizes_log_growth():
    p, g, l = 0.57, 1.0, 1.0
    k = kelly_fraction(p, g, l)
    full = log_growth_rate(k, p, g, l)
    under = log_growth_rate(k / 2, p, g, l)
    over = log_growth_rate(min(0.999, k * 2), p, g, l)
    assert full >= under and full >= over, "f* log-büyümeyi maksimize etmeli"


def test_overbet_can_turn_growth_negative():
    """Edge olsa bile çok büyük basmak (overbet) büyümeyi negatife çevirir —
    kullanıcının botunun iflas sebebi tam bu."""
    p, g, l = 0.55, 1.0, 1.0
    k = kelly_fraction(p, g, l)            # ~0.10
    # 3× Kelly aşırı agresif
    g_over = log_growth_rate(min(0.999, k * 3.5), p, g, l)
    assert g_over < 0, "aşırı overbet üstel erime (negatif log-büyüme) vermeli"


def test_log_growth_zero_at_zero_fraction():
    assert log_growth_rate(0.0, 0.6, 1.0, 1.0) == pytest.approx(0.0)


def test_expected_value():
    assert expected_value(0.55, 1.0, 1.0) == pytest.approx(0.10, abs=1e-9)
    assert expected_value(0.45, 1.0, 1.0) == pytest.approx(-0.10, abs=1e-9)


def test_capital_multiple_and_doubling_consistent():
    p, g, l = 0.6, 1.0, 1.0
    k = kelly_fraction(p, g, l)
    n = int(round(trials_to_double(k, p, g, l)))
    mult = capital_multiple(k, p, g, n, l)   # (frac, p, payoff, n_trials, loss_frac)
    assert mult == pytest.approx(2.0, rel=0.05), f"~2× beklenir, {mult}"


def test_no_edge_never_doubles():
    assert trials_to_double(0.1, 0.5, 1.0, 1.0) == float("inf")


# ── Risk of ruin bilinen değerler ────────────────────────────────────
def test_ror_known_value():
    # winrate=5, std=100, B=2000bb → exp(-2·5·2000/100²)=exp(-2)≈0.1353
    assert risk_of_ruin(5.0, 100.0, 2000.0) == pytest.approx(math.exp(-2), abs=1e-6)


def test_ror_certain_when_losing():
    assert risk_of_ruin(-1.0, 100.0, 5000.0) == 1.0


def test_ror_decreases_with_bankroll():
    a = risk_of_ruin(5.0, 100.0, 1000.0)
    b = risk_of_ruin(5.0, 100.0, 3000.0)
    assert b < a, "daha büyük bankroll → daha düşük iflas riski"


def test_ror_increases_with_variance():
    lo = risk_of_ruin(5.0, 80.0, 2000.0)
    hi = risk_of_ruin(5.0, 160.0, 2000.0)
    assert hi > lo, "daha yüksek varyans → daha yüksek iflas riski"


def test_bankroll_for_ror_roundtrip():
    # Önerilen bankroll'la RoR ≈ hedef
    b = bankroll_for_ror(5.0, 100.0, 0.05)
    assert risk_of_ruin(5.0, 100.0, b) == pytest.approx(0.05, abs=1e-6)


def test_bankroll_infinite_when_no_edge():
    assert bankroll_for_ror(0.0, 100.0, 0.05) == float("inf")


# ── Yüksek seviye raporlar ───────────────────────────────────────────
def test_analyze_edge_detects_edge_and_defaults_half_kelly():
    r = analyze_edge(0.6, 1.0, 1.0, n_trials=100)
    assert r.has_edge
    assert r.kelly == pytest.approx(0.2, abs=1e-9)
    assert r.chosen_frac == pytest.approx(0.1, abs=1e-9)   # half-Kelly varsayılan
    assert not r.overbet
    assert r.multiple_chosen > 1.0


def test_analyze_edge_flags_overbet():
    r = analyze_edge(0.6, 1.0, 1.0, chosen_frac=0.5, n_trials=100)
    assert r.overbet, "0.5 > full Kelly 0.2 → overbet bayrağı"


def test_analyze_edge_no_edge():
    r = analyze_edge(0.48, 1.0, 1.0)
    assert not r.has_edge
    assert r.kelly == 0.0


def test_analyze_bankroll_health():
    # 30 buy-in @ 100bb = 3000bb, winrate 5, std 100
    rep = analyze_bankroll(5.0, 100.0, 3000.0, buyin_bb=100.0)
    assert rep.buyins == pytest.approx(30.0)
    assert 0.0 < rep.ror < 0.05
    assert rep.healthy
    assert rep.safe_buyins < 30.0   # 30 buy-in zaten güvenlinin üstünde


def test_analyze_bankroll_unhealthy_thin_roll():
    rep = analyze_bankroll(3.0, 150.0, 500.0, buyin_bb=100.0)  # 5 buy-in, MTT std
    assert not rep.healthy
    assert rep.ror > 0.05
