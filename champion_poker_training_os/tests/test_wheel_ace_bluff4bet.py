"""D254 (+EV-max audit #5): wheel-ace (A2s-A5s) bluff-4bet value-locked 3-bet'çiye karşı
fold-equity'siz → ~%29 eq ile domine call'lanır (ICM felaketi). Value-locked (Mouse/nit
VEYA three_bet≤%4) okumasında 4-bet İPTAL→FOLD. No-read GTO + premium value-4bet korunur."""
from app.poker.soyrac_advisor import soyrac_explain

_NIT = {"vpip": 14, "pfr": 11, "aggression": 1.4, "three_bet": 2, "obs_hands": 120}
_JACKAL = {"vpip": 32, "pfr": 26, "aggression": 3.4, "three_bet": 12, "river_bluff": 30, "obs_hands": 120}


def _act(hk, vstats, pos="BTN", vs="CO"):
    return soyrac_explain(hk, pos, scenario="vs 3-bet", vs_position=vs,
                          stack_bb=50, villain_stats=vstats)["action"]


def test_no_read_keeps_gto_bluff4bet():
    assert _act("A5s", None) == "4-BET"


def test_value_locked_nit_cancels_bluff4bet():
    """Nit/value-locked → bluff-4bet İPTAL → FOLD (spew önlendi)."""
    assert _act("A5s", _NIT) == "FOLD"


def test_aggressive_keeps_bluff4bet():
    """Jackal (light-3bet, fold-equity var) → bluff-4bet KALIR."""
    assert _act("A5s", _JACKAL) == "4-BET"


def test_premium_value_4bet_untouched():
    """Premium (AKs/QQ+) value-4bet → nit'e karşı bile KALIR (iptal yalnız bluff'a)."""
    assert _act("AKs", _NIT) == "4-BET"
    assert _act("QQ", _NIT) == "4-BET"
