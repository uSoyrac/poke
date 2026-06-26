"""D327 (kullanıcı: 'sistem aşamaya göre düşünmüyor — 25/24 tam-bubble ≠ 40-kala').
ICM baskısını PARA'YA YAKINLIĞA göre ölçekle (insan-sayılabilir: 'X kala'). Tam-bubble (ptm=1)
MAKS baskı, uzaklaştıkça söner. default None → eski davranış (fidelity 0-sapma)."""
from app.poker.icm import proximity_mult, risk_premium
from app.poker.soyrac_advisor import soyrac_advice


def test_proximity_mult_gradient():
    assert proximity_mult(None) == 1.0
    assert proximity_mult(1) == 1.4 and proximity_mult(5) == 1.0
    assert proximity_mult(1) > proximity_mult(3) > proximity_mult(8) > proximity_mult(20)
    assert proximity_mult(20) >= 0.6           # taban


def test_proximity_risk_premium_and_fidelity():
    # tam-bubble (ptm=1) > uzak (ptm=15) baskı
    assert risk_premium(11, 40, "bubble", 1) > risk_premium(11, 40, "bubble", 15)
    # FIDELITY: default None == eski (proximity'siz) davranış
    assert risk_premium(11, 40, "bubble", None) == risk_premium(11, 40, "bubble")
    # cash/chipEV → proximity ETKİSİZ
    assert risk_premium(100, 100, "chipEV", 1) == risk_premium(100, 100, "chipEV", None)


def _jam(hk, ptm):
    return soyrac_advice(hk, "SB", "push", stack_bb=11, n_active=8, tourney=True,
                         icm=True, stage="bubble", avg_stack_bb=40,
                         players_to_money=ptm)["action"]


def test_proximity_tightens_marginal_only():
    """Tam-bubble MARJİNAL jam'i sıkar (T8o flip); premium + clear-fold DEĞİŞMEZ."""
    assert _jam("T8o", 15) == "JAM" and _jam("T8o", 1) == "FOLD", "marjinal el tam-bubble'da sıkılmalı"
    assert _jam("AKo", 1) == "JAM" and _jam("AKo", 15) == "JAM", "premium proximity'den etkilenmez"
    assert _jam("72o", 1) == "FOLD", "clear-fold her durumda fold"


def test_proximity_default_none_identity():
    """players_to_money geçilmezse (None) → bubble davranışı değişmez (advice-only, fidelity)."""
    a = soyrac_advice("T8o", "SB", "push", stack_bb=11, n_active=8, tourney=True,
                      icm=True, stage="bubble", avg_stack_bb=40)["action"]
    b = soyrac_advice("T8o", "SB", "push", stack_bb=11, n_active=8, tourney=True,
                      icm=True, stage="bubble", avg_stack_bb=40, players_to_money=None)["action"]
    assert a == b
