"""D262 (+EV-max audit #16): call-vs-jam jammer-pozisyonunu yok sayıyordu. SB/BB geniş
jam'ler (Nash %42-72) → call genişlet; UTG dar jam'ler (%5-10) → daralt. Jammer range
genişliği call-off genişliğini belirler."""
from app.poker.soyrac_advisor import soyrac_advice


def _thr(hk, jammer, stack=12):
    return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=jammer,
                         stack_bb=stack, tourney=True)["threshold"]


def test_wide_jammer_lower_calloff_threshold():
    """SB (geniş jam) → call eşiği UTG'den (dar jam) DÜŞÜK (daha çok call)."""
    assert _thr("KTo", "SB") < _thr("KTo", "UTG")


def test_marginal_calls_vs_sb_folds_vs_utg():
    """KTo/QJo 12bb: SB-jam'e CALL, UTG-jam'e FOLD."""
    def act(hk, j):
        return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=j,
                             stack_bb=12, tourney=True)["action"]
    for hk in ("KTo", "QJo"):
        assert act(hk, "SB") == "CALL", f"{hk} vs SB"
        assert act(hk, "UTG") == "FOLD", f"{hk} vs UTG"


def test_premium_calls_both():
    """Premium (99) her jammer'a CALL (dar UTG jam'e bile)."""
    def act(hk, j):
        return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=j,
                             stack_bb=12, tourney=True)["action"]
    assert act("99", "SB") == "CALL" and act("99", "UTG") == "CALL"
