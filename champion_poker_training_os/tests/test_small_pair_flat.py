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


def _act3b(hk, st=100):
    from app.poker.soyrac_advisor import soyrac_advice
    return soyrac_advice(hk, "CO", scenario="vs 3-bet", vs_position="MP", stack_bb=st)["action"]


def test_d236_small_pairs_fold_to_3bet():
    """D236: 33-66 vs 3-bet → FOLD (GTO pure-fold; 3-bet pot set-mine implied-odds yok)."""
    for hk in ("33", "44", "55", "66"):
        assert _act3b(hk) == "FOLD", f"{hk} vs-3bet FOLD olmalı: {_act3b(hk)}"


def test_d236_medium_pairs_still_call_3bet():
    """77+ vs 3-bet → CALL (set-mine, GTO call-lean) korunur."""
    for hk in ("77", "88", "99", "TT"):
        assert _act3b(hk) == "CALL", f"{hk} vs-3bet CALL kalmalı: {_act3b(hk)}"
