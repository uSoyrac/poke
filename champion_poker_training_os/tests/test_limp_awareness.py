"""D283 (kullanıcı yakaladı: 'LJ iken MP limp etmiş olmasına rağmen RFI/raise diyor QX ile'):
sistem limp'i hiç saymıyordu → pota giren olsa bile 'RFI (açış)' sanıyordu (steal değilken
steal gibi). FIX: _limpers_before_hero + soyrac_advice n_limpers. Önünde limper → iso-raise
(steal değil); ÇOK limper (2+) = çok-yollu → marjinal iso'yu bırak (D278 felsefesi). Tek limp
value-iso (QJs/KQ/QTs) korunur. ADVICE-only (n_limpers default 0 → bot + mevcut testler aynı)."""
import types
from app.engine.hand_state import HandState, Action, ActionType, Street, PlayerSeat
from app.poker.soyrac_advisor import soyrac_advice, _limpers_before_hero


_POS9 = ['UTG', 'UTG+1', 'MP', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']


def _hand_with_limps(n_limps, hero_idx=3):
    h = HandState()
    h.players = [PlayerSeat(name=f'p{i}', stack=100, position=_POS9[i]) for i in range(9)]
    h.community = []; h.street = Street.PREFLOP
    acts = []
    # hero (idx3) öncesi: idx0..2 → ilk (2-n_limps) fold, sonraki n_limps limp(call)
    for i in range(hero_idx):
        if i < hero_idx - n_limps:
            acts.append(Action(player_idx=i, action_type=ActionType.FOLD, amount=0, street=Street.PREFLOP))
        else:
            acts.append(Action(player_idx=i, action_type=ActionType.CALL, amount=1.0, street=Street.PREFLOP))
    h.actions = acts
    return h


def test_limper_detection():
    assert _limpers_before_hero(_hand_with_limps(0), 3) == 0
    assert _limpers_before_hero(_hand_with_limps(1), 3) == 1
    assert _limpers_before_hero(_hand_with_limps(2), 3) == 2


def test_raise_before_hero_not_limp():
    """Önünde RAISE varsa limp senaryosu DEĞİL → 0 (vs RFI ayrı dalda işlenir)."""
    h = _hand_with_limps(0)
    h.actions = [Action(player_idx=2, action_type=ActionType.RAISE, amount=3.0, street=Street.PREFLOP)]
    assert _limpers_before_hero(h, 3) == 0


def test_single_limp_value_iso_kept():
    """Tek limp: güçlü QX/broadway iso-raise korunur + 'izole et' notu (steal değil)."""
    for hk in ("QJs", "QTs", "KQo", "AQo"):
        r = soyrac_advice(hk, "LJ", "RFI", stack_bb=100, tourney=True, n_limpers=1)
        assert r["action"] == "RAISE (AÇ)", f"{hk}: {r['action']}"
        assert "limper" in r["limp_note"]   # ASCII-güvenli (Türkçe-İ .lower() tuzağı yok)
    assert "limp" in soyrac_advice("QJs", "LJ", "RFI", stack_bb=100, tourney=True, n_limpers=1)["scenario"]


def test_multi_limp_tightens_marginal():
    """2+ limper (çok-yollu): marjinal iso (QTs) FOLD; güçlü (QJs/KQ/AQ) raise kalır."""
    assert soyrac_advice("QTs", "LJ", "RFI", stack_bb=100, tourney=True, n_limpers=2)["action"] == "FOLD"
    for hk in ("QJs", "KQo", "AQo", "AA", "AKs"):
        assert soyrac_advice(hk, "LJ", "RFI", stack_bb=100, tourney=True, n_limpers=2)["action"] == "RAISE (AÇ)"


def test_no_limpers_identity():
    """n_limpers=0 (default): davranış + scenario birebir eski (fidelity/regresyon yok)."""
    for hk in ("QJs", "QTs", "QJo", "AA"):
        a = soyrac_advice(hk, "LJ", "RFI", stack_bb=100, tourney=True, n_limpers=0)
        assert a["scenario"] == "RFI" and a.get("limp_note", "") == ""
