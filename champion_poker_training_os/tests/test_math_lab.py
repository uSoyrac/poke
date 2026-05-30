"""Math Lab drill doğruluğu — formülleri bağımsız yeniden hesaplayıp doğrular.

'Optimal olsun, test edip geliştirelim' → her formül-tabanlı drill'in saklı
cevabı temiz bir reimplementasyonla eşleşmeli (gelecekteki sapmaları yakalar).
"""
from __future__ import annotations

import re

from app.db.seed_data import generate_math_drills

_DRILLS = generate_math_drills()


def _by_cat(cat):
    return [d for d in _DRILLS if d["category"] == cat]


def test_all_drills_well_formed():
    assert len(_DRILLS) >= 100
    for d in _DRILLS:
        assert isinstance(d["answer"], (int, float))
        assert float(d.get("tolerance", 0)) > 0
        assert d.get("formula") and d.get("explanation")
        assert d.get("prompt")


def test_pot_odds_formula():
    # equity = call / (pot + 2*call)
    for d in _by_cat("pot_odds"):
        m = re.search(r"Pot (\d+)bb\. Villain bets (\d+)bb", d["prompt"])
        assert m, d["prompt"]
        pot, bet = int(m.group(1)), int(m.group(2))
        assert abs(d["answer"] - bet / (pot + 2 * bet)) < 1e-3
        assert 0 < d["answer"] < 0.5      # tek bet pot-odds her zaman < 50%


def test_alpha_formula():
    # alpha = bet / (bet + pot)
    for d in _by_cat("alpha"):
        m = re.search(r"bluff (\d+)bb into a (\d+)bb pot", d["prompt"])
        assert m, d["prompt"]
        bet, pot = int(m.group(1)), int(m.group(2))
        assert abs(d["answer"] - bet / (bet + pot)) < 1e-3
        assert 0 < d["answer"] < 1


def test_mdf_formula_and_complement():
    # MDF = pot / (pot + bet) = 1 - alpha
    for d in _by_cat("mdf"):
        m = re.search(r"bets (\d+)bb into (\d+)bb", d["prompt"])
        assert m, d["prompt"]
        bet, pot = int(m.group(1)), int(m.group(2))
        assert abs(d["answer"] - pot / (pot + bet)) < 1e-3


def test_alpha_plus_mdf_equals_one():
    # Aynı (pot,bet) listesi → index eşleşmesinde alpha + MDF ≈ 1
    al, mdf = _by_cat("alpha"), _by_cat("mdf")
    assert len(al) == len(mdf)
    for a, m in zip(al, mdf):
        assert abs(a["answer"] + m["answer"] - 1.0) < 2e-3


def test_ev_formula():
    for d in _by_cat("ev"):
        m = re.search(r"Win (\d+)% · pot reward (\d+)bb · risk (\d+)bb", d["prompt"])
        assert m, d["prompt"]
        w = int(m.group(1)) / 100.0
        pot, risk = int(m.group(2)), int(m.group(3))
        expected = w * pot - (1 - w) * risk
        assert abs(d["answer"] - expected) < 0.05


def test_combos_known_values():
    combos = {d["prompt"]: d["answer"] for d in _by_cat("combos")}
    # Bilinen kombinatorik değerler
    aa = next(v for k, v in combos.items() if k.startswith("Pocket Aces"))
    assert aa == 6.0
    deck = next(v for k, v in combos.items() if "full deck" in k)
    assert deck == 1326.0
    pairs = next(v for k, v in combos.items() if "All pocket pairs" in k)
    assert pairs == 78.0


def test_pot_odds_less_than_alpha_same_spot():
    # pot_odds = bet/(pot+2bet) < alpha = bet/(pot+bet) — payda daha büyük
    po, al = _by_cat("pot_odds"), _by_cat("alpha")
    for p, a in zip(po, al):
        assert p["answer"] < a["answer"] + 1e-9


def test_answer_choices_valid():
    # Çoktan seçmeli: doğru cevap her zaman şıklarda, 4 benzersiz seçenek
    from app.ui.screens.math_lab import MathLabScreen
    seen = set()
    for d in _DRILLS:
        if d["category"] in seen:
            continue
        seen.add(d["category"])
        opts = MathLabScreen._answer_choices(d)
        assert len(opts) == 4, (d["category"], opts)
        assert len(set(opts)) == 4, ("dup", d["category"], opts)
        assert round(d["answer"], 3) in opts, ("eksik doğru", d["category"], opts)
    assert len(seen) == 9          # 9 kategori


def test_pushfold_real_equity_sane():
    # Gerçek MC equity: QQ vs tight UTG-call > %55; küçük çift vs tight < %50
    pf = {d["prompt"]: d["answer"] for d in _by_cat("push_fold")}
    assert len(pf) == 15
    for ans in pf.values():
        assert 0.0 < ans < 1.0          # geçerli equity
    qq = next(v for k, v in pf.items() if k.startswith("15bb QQ"))
    assert qq > 0.55                    # QQ tight range'e karşı favori
    p22 = next(v for k, v in pf.items() if "22 jam" in k)
    assert p22 < 0.50                   # 22 tight calling range'e karşı underdog


def test_spot_check_exact_values():
    # Pot 10, bet 4 → pot_odds 4/18=0.222, alpha 4/14=0.286, mdf 10/14=0.714
    po = _by_cat("pot_odds")[0]
    assert abs(po["answer"] - 0.222) < 0.002
    al = _by_cat("alpha")[0]
    assert abs(al["answer"] - 0.286) < 0.002
    md = _by_cat("mdf")[0]
    assert abs(md["answer"] - 0.714) < 0.002
