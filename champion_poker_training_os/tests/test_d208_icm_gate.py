"""D257 (+EV-max audit #3): D208 statik call_t+=3 advice'ta early/no-ICM'de BB-vs-geç-açış
kapanış spotlarını (pure-CALL ~3.5:1) imha ediyordu (chip-EV=cash → over-fold −EV).
ICM-gated yapıldı: ICM→+2, blind-vs-erken→+1, geç-açışa early/no-ICM EK-sıkma yok.
BOT (+3) + bubble-ICM FOLD KORUNUR (fidelity + D208 leak ×835)."""
from app.poker.soyrac_advisor import soyrac_advice


def _a(hk, vs="CO", icm=False, bot=False):
    return soyrac_advice(hk, "BB", scenario="vs RFI", vs_position=vs, stack_bb=40,
                         tourney=True, icm=icm, bot_mode=bot, n_active=9)["action"]


def test_early_no_icm_defends_pure_call_spots():
    """early/no-ICM BB vs geç-açış: pure-CALL kapanış elleri → CALL (eski FOLD)."""
    for hk in ("Q8s", "K8s", "QTo", "JTo", "T8s", "98s"):
        assert _a(hk) == "CALL", f"{hk}: {_a(hk)}"


def test_icm_bubble_still_tightens():
    """ICM aktif (bubble/FT) → marjinal kapanış elleri FOLD (D208 leak fix korunur)."""
    for hk in ("Q8s", "K8s", "QTo", "T8s"):
        assert _a(hk, icm=True) == "FOLD", f"{hk} ICM: {_a(hk, icm=True)}"


def test_junk_still_folds():
    """Çöp early/no-ICM'de bile FOLD (genişleme yalnız oynanabilir kapanış elleri)."""
    assert _a("72o") == "FOLD"
    assert _a("J2o") == "FOLD"
