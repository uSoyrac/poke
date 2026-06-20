"""D262 (+EV-max audit #16): call-vs-jam jammer-pozisyonunu yok sayıyordu. SB/BB geniş
jam'ler (Nash %42-72) → call genişlet; UTG dar jam'ler (%5-10) → daralt. Jammer range
genişliği call-off genişliğini belirler."""
from app.poker.soyrac_advisor import soyrac_advice


def _thr(hk, jammer, stack=12):
    return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=jammer,
                         stack_bb=stack, tourney=True)["threshold"]


def test_wide_jammer_wider_calloff():
    """SB (geniş jam) → call-off range UTG'den (dar jam) GENİŞ. D288: 'threshold' artık
    Nash call-off% (yüksek=geniş, eski SHCP-eşiği değil) → SB pct > UTG pct."""
    assert _thr("KTo", "SB") > _thr("KTo", "UTG")


def test_marginal_calls_vs_sb_folds_vs_utg():
    """Marjinal (KTo/A9o) 12bb: geniş SB-jam'e CALL, dar UTG-jam'e FOLD (dominated)."""
    def act(hk, j):
        return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=j,
                             stack_bb=12, tourney=True)["action"]
    for hk in ("KTo", "A9o"):
        assert act(hk, "SB") == "CALL", f"{hk} vs SB"
        assert act(hk, "UTG") == "FOLD", f"{hk} vs UTG"


def test_calloff_connector_not_overweighted():
    """D288 (all-in=Nash membership): küçük suited-connector (54s/64s) call-off'ta
    over-weight EDİLMEZ — geniş SB-jam'e bile FOLD (postflop yok, showdown zayıf)."""
    def act(hk, j):
        return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=j,
                             stack_bb=12, tourney=True)["action"]
    for hk in ("54s", "64s"):
        assert act(hk, "SB") == "FOLD", f"{hk} vs SB call-off connector over-weight"


def test_premium_calls_both():
    """Premium (99) her jammer'a CALL (dar UTG jam'e bile)."""
    def act(hk, j):
        return soyrac_advice(hk, "BB", scenario="vs 3-bet", vs_position=j,
                             stack_bb=12, tourney=True)["action"]
    assert act("99", "SB") == "CALL" and act("99", "UTG") == "CALL"
