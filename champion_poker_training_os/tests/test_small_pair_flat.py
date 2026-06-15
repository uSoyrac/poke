"""D234: küçük çift (22-44) açışa 3-BET DEĞİL set-mine FLAT (kullanıcı yakaladı + GTO-teyit:
33/44 pure-call). 55+ GTO-3bet kalır. SHCP pariteyi şişirip tüm çiftleri 3bet ettiriyordu."""
from app.poker.soyrac_advisor import soyrac_advice


def _act(hk, pos="MP", vs="UTG", st=100):
    return soyrac_advice(hk, pos, scenario="vs RFI", vs_position=vs, stack_bb=st, tourney=True)["action"]


def test_small_pairs_flat_not_3bet():
    """33/44 vs açış → CALL (set-mine), 3-BET DEĞİL."""
    for hk in ("33", "44"):
        for vs in ("UTG", "MP", "CO"):
            assert _act(hk, "MP", vs) == "CALL", f"{hk} vs {vs} set-mine FLAT olmalı: {_act(hk,'MP',vs)}"


def test_medium_pairs_still_3bet():
    """55+ GTO-3bet korunur (regresyon yok)."""
    for hk in ("55", "66", "77", "99", "JJ", "QQ"):
        assert _act(hk, "MP", "UTG") == "3-BET", f"{hk} 3-BET kalmalı: {_act(hk,'MP','UTG')}"


def test_small_pair_flat_all_depths():
    """Early-MTT sığ derinlikte de 33/44 flat (yarı-stack set-mine riski yok)."""
    for st in (100, 40, 25):
        assert _act("33", "MP", "UTG", st) == "CALL"
