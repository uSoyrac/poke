"""D278 (kullanıcı içgörüsü, son turnuva değerlendirmesi sonrası): "3-4 kişi pota
girince QQ/JJ-altı çiftle set olmadan kazanmak çok zor → çok büyük call ve 3-4bet
olmamalı; illaki büyük karta sahipler var, ortak kartlarda yakalarlar."

Çok-yollu (açan + ≥1 call = n_committed≥2) vs-RFI: orta/küçük çift (≤TT) → 3-BET YOK,
ucuz set-mine FLAT (çok-yollu implied-odds iyi). Blöf-3bet (blocker) → iptal (fold-equity
yok). JJ+/QQ+ + broadway DOKUNULMAZ. Heads-up (n_committed≤1) eski davranış (regresyon yok)."""
import types
from app.poker.soyrac_advisor import soyrac_advice, _committed_opponents


def _a(hk, nc, vs="MP", pos="CO"):
    return soyrac_advice(hk, pos, "vs RFI", vs, stack_bb=60, tourney=True, n_committed=nc)["action"]


def test_midpairs_flat_not_3bet_multiway():
    """Çok-yollu: 55-TT → CALL (set-mine), 3-BET DEĞİL."""
    for hk in ("55", "66", "77", "88", "99", "TT"):
        assert _a(hk, 2) == "CALL", f"{hk} çok-yollu set-mine FLAT olmalı: {_a(hk, 2)}"


def test_midpairs_still_3bet_heads_up():
    """Heads-up (açan tek): 55-TT 3-BET korunur (regresyon yok)."""
    for hk in ("55", "77", "99", "TT"):
        assert _a(hk, 1) == "3-BET", f"{hk} heads-up 3-BET kalmalı: {_a(hk, 1)}"


def test_strong_pairs_and_broadway_untouched():
    """JJ+/QQ+ ve broadway → çok-yollu da olsa 3-BET (QQ/JJ ÜSTÜ + value)."""
    for hk in ("JJ", "QQ", "KK", "AA", "KQs", "AKo"):
        assert _a(hk, 2) == "3-BET", f"{hk} çok-yollu 3-BET kalmalı: {_a(hk, 2)}"


def test_blocker_bluff_3bet_cancelled_multiway():
    """Wheel-ace blöf-3bet (A5s vs geç açış) → çok-yollu İPTAL (fold-equity yok)."""
    assert _a("A5s", 1, vs="CO", pos="BTN") == "3-BET"   # heads-up: blöf-3bet
    assert _a("A5s", 2, vs="CO", pos="BTN") != "3-BET"   # çok-yollu: iptal


def _mk(bets, bb=2.0):
    pls = [types.SimpleNamespace(current_bet=b, is_folded=False, is_eliminated=False) for b in bets]
    return types.SimpleNamespace(players=pls, big_blind=bb)


def test_committed_opponents_signal():
    """Helper: açan+call=2 (çok-yollu); tek açan=1; limp-pot=0 (forced kör sayılmaz)."""
    assert _committed_opponents(_mk([6, 6, 0, 2, 2]), 2) == 2     # açan+call (hero idx2)
    assert _committed_opponents(_mk([6, 0, 2, 2]), 1) == 1        # tek açan (hero idx1)
    assert _committed_opponents(_mk([2, 2, 2, 2]), 3) == 0        # limp pot, raise yok
