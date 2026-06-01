"""Bot profil havuzu GERÇEKÇİLİK değişmezleri — havuzun iç tutarlılığı.

test_bot_archetype_fidelity her arketipin MUTLAK hedefini gerçek simülasyonla
doğrular; test_bot_realism karar-düzeyi anti-spew'i. Bu paket havuzun
GÖRELİ/mantıksal tutarlılığını (WSOP-gerçekçiliği) doğrular: tight oyuncu
loose'dan az el oynar, pasif agresiften az saldırır, nit station'dan çok
fold eder vs. Profiller bozulursa (örn. PFR>VPIP) bu testler yakalar.
"""
from __future__ import annotations

from app.engine.bot_brain import BOT_ARCHETYPES as A


def _p(name):
    return A[name]


# ── HARD poker değişmezleri (her profil) ─────────────────────────────
def test_pfr_never_exceeds_vpip():
    """PFR ≤ VPIP — oynadığından fazla el RAISE edilemez (imkansız)."""
    bad = [n for n, p in A.items() if p.pfr > p.vpip + 0.01]
    assert not bad, f"PFR > VPIP olan profiller: {bad}"


def test_stats_in_sane_ranges():
    bad = []
    for n, p in A.items():
        if not (8 <= p.vpip <= 60): bad.append(f"{n} VPIP {p.vpip}")
        if not (0 <= p.pfr <= 40): bad.append(f"{n} PFR {p.pfr}")
        if not (0 <= p.three_bet <= 28): bad.append(f"{n} 3bet {p.three_bet}")
        if not (5 <= p.fold_to_cbet <= 90): bad.append(f"{n} FCB {p.fold_to_cbet}")
        if not (0.5 <= p.aggression <= 4.5): bad.append(f"{n} AF {p.aggression}")
        if not (0.0 <= p.river_bluff <= 1.0): bad.append(f"{n} rb {p.river_bluff}")
        if not (0.0 <= p.call_down <= 1.0): bad.append(f"{n} cd {p.call_down}")
    assert not bad, "Aralık dışı: " + "; ".join(bad)


# ── GÖRELİ gerçekçilik (tipoloji doğru olmalı) ───────────────────────
def test_tight_play_fewer_hands_than_loose():
    tight = max(_p("Nit").vpip, _p("Rock").vpip)
    loose = min(_p("Fish").vpip, _p("Maniac").vpip, _p("Calling Station").vpip)
    assert tight < loose, f"tight {tight} < loose {loose} olmalı"


def test_nit_folds_to_cbet_more_than_station():
    assert _p("Nit").fold_to_cbet > _p("Calling Station").fold_to_cbet
    assert _p("Rock").fold_to_cbet > _p("Fish").fold_to_cbet


def test_station_calls_down_more_than_nit():
    assert _p("Calling Station").call_down > _p("Nit").call_down
    assert _p("Fish").call_down > _p("Rock").call_down


def test_maniac_lag_3bet_more_than_nit_rock():
    assert _p("Maniac").three_bet > _p("Nit").three_bet
    assert _p("LAG").three_bet > _p("Rock").three_bet


def test_aggressive_types_bluff_more_rivers():
    aggr = min(_p("Maniac").river_bluff, _p("LAG").river_bluff)
    pasv = max(_p("Calling Station").river_bluff, _p("Nit").river_bluff)
    assert aggr > pasv, f"agresif rb {aggr} > pasif rb {pasv}"


def test_elite_regs_balanced_not_extreme():
    """Elit reg'ler dengeli — ne nit ne maniac (orta VPIP, sağlam AF)."""
    for n in ("Shark", "GTO Expert", "Solver Bot"):
        p = _p(n)
        assert 18 <= p.vpip <= 30, f"{n} VPIP {p.vpip} dengeli değil"
        assert p.aggression >= 2.5, f"{n} AF {p.aggression} elit reg için düşük"


def test_legends_present_and_distinct():
    legends = ["Doyle Brunson", "Phil Ivey", "Phil Hellmuth", "Daniel Negreanu"]
    for n in legends:
        assert n in A, f"{n} havuzda yok"
    vpips = {n: _p(n).vpip for n in legends}
    assert len(set(vpips.values())) >= 3, f"efsaneler çok benzer: {vpips}"
    # Hellmuth disiplinli (tight), Doyle eski-okul loose-aggressive
    assert _p("Phil Hellmuth").vpip < _p("Doyle Brunson").vpip


def test_pool_size_and_coverage():
    """Havuz yeterince çeşitli (≥20 arketip + tüm stil aileleri)."""
    assert len(A) >= 20, f"sadece {len(A)} arketip"
    names = " ".join(A.keys()).lower()
    for fam in ("tag", "lag", "nit", "fish", "station", "shark", "maniac"):
        assert fam in names, f"'{fam}' stili havuzda yok"
