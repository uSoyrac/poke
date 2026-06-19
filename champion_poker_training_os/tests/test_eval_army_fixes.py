"""D285 (24-ajan full-eval-army doğrulanmış bug'ları): 3 advice-layer fix.
Hepsi insan-hesaplanabilir + fidelity-safe (bot_mode hariç / postflop) + GTO-teyitli.

#1 vs-RFI 3-bet ekseni opener-körlüğü: erken-açışa (UTG/UTG+1) dominated-flat eller PURE
   3-bet ediyordu; GTO flat'ler. Cerrahi value-3bet seti = 66+ ∪ suited(SHCP≥18) ∪ AKo.
#4 _draw_equity overpair hayalet overcard: cep-çiftine '2 overcard' kredisi → eq şişme.
#5 soyrac_explain stage/avg_stack_bb base karara geçmiyordu → FT/satellite bubble-seviyesi.
"""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_advice, soyrac_explain, _draw_equity


def _a(hk, vs, pos="MP"):
    return soyrac_advice(hk, pos, "vs RFI", vs_position=vs, stack_bb=100, tourney=False)["action"]


# ---- Bug #1: vs-RFI erken-açış dominated-3bet downgrade ----
def test_vsrfi_early_dominated_flats():
    """vs UTG: dominated-flat (offsuit-broadway/zayıf-suited/55) → CALL (GTO-teyit)."""
    for hk in ("AQo", "KQo", "55", "A9s", "KTs", "QTs", "JTs", "A5s"):
        assert _a(hk, "UTG") == "CALL", f"{hk} vs UTG dominated → CALL olmalı: {_a(hk,'UTG')}"


def test_vsrfi_early_value3bet_kept():
    """vs UTG: value-3bet seti (66+ ∪ suited-SHCP≥18 ∪ AKo) → 3-BET korunur."""
    for hk in ("66", "77", "99", "TT", "QQ", "AKo", "AKs", "AQs", "AJs", "KQs", "ATs", "KJs", "QJs"):
        assert _a(hk, "UTG") == "3-BET", f"{hk} vs UTG value-3bet kalmalı: {_a(hk,'UTG')}"


def test_vsrfi_late_open_untouched():
    """vs LATE (CO/BTN) açış: erken-fix DOKUNMAZ — geç-açana 3-bet/blöf geniş kalır."""
    # AQo vs CO açış: erken-downgrade YOK (yalnız UTG/UTG+1)
    assert _a("AQo", "CO") in ("3-BET", "CALL")   # geç-açış mantığı (fix değişmez)
    assert _a("66", "CO") == "3-BET"


# ---- Bug #4: overpair hayalet overcard yok ----
def _dq(hole, board):
    return _draw_equity([card_from_str(x) for x in hole], [card_from_str(x) for x in board])[0]


def test_overpair_no_phantom_overcard():
    """Overpair (AA/K72) → 0 çekme (hayalet '2 overcard' yok); HAVA 2-overcard korunur."""
    assert _dq(["Ad", "Ac"], ["Ks", "7c", "2d"]) == 0.0, "AA overpair hayalet overcard almamalı"
    assert _dq(["Kd", "Qc"], ["7s", "2c", "3d"]) > 0.0, "KQ HAVA 2-overcard kredisi korunmalı"


# ---- Bug #5: stage base karara akıyor ----
def _mk(hole, n=4):
    h = [card_from_str(x) for x in hole]
    hero = types.SimpleNamespace(hole_cards=h, stack=200.0, is_folded=False, is_eliminated=False, position="BTN")
    vs = [types.SimpleNamespace(hole_cards=[], stack=200.0, is_folded=False, is_eliminated=False, position="BB")
          for _ in range(n - 1)]
    return types.SimpleNamespace(players=[hero] + vs, community=[], street=Street.PREFLOP,
                                 pot=1.5, active_count=n, hero_idx=0, to_call=lambda i: 0, big_blind=1.0)


def test_stage_flows_to_decision():
    """soyrac_explain stage'i base karara geçirir → satellite eşik > bubble (cube_pressure)."""
    th = {}
    for stg in ("bubble", "satellite"):
        e = soyrac_explain("A7o", "BTN", "RFI", stack_bb=10, icm=True, n_active=4,
                           tourney=True, stage=stg, avg_stack_bb=12, hand=_mk(["Ah", "7c"]), hero_idx=0)
        th[stg] = e.get("threshold")
    assert th["satellite"] > th["bubble"], f"satellite eşik bubble'dan yüksek olmalı: {th}"
