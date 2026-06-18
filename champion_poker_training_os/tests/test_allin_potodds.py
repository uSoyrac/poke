"""D269 (kullanıcı yakaladı: '0 param var ama fold'): hero to_call'dan AZ stack'le ancak
ALL-IN call edebilir → gerçek risk min(to_call, stack); pot-odds bununla hesaplanır.
Eski kod tam-bahsi fiyatlayıp short-stack'i dev odds'a rağmen FOLD'latıyordu."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice


def _act(hole, stack_bb, to_call_bb, board, pot_bb=76.8):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=stack_bb, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.TURN,
                               pot=pot_bb, active_count=2, to_call=lambda i: to_call_bb)
    return soyrac_postflop_advice(hd, 0)["action"]


_KQ = (["Kh", "Qh"], ["8d", "9c", "Th", "7d"])   # K-high + gutshot


def test_short_stack_priced_in_calls():
    """0.3-5bb stack shove'a karşı → CALL (priced-in, dev pot-odds)."""
    for st in (0.3, 1.0, 5.0):
        assert _act(_KQ[0], st, 30.5, _KQ[1]).startswith("CALL"), f"stack {st}"


def test_deep_stack_folds_weak_draw():
    """40bb derin (priced-in değil) → KQ gutshot %21 < gereken %28 → FOLD."""
    assert _act(_KQ[0], 40.0, 30.5, _KQ[1]).startswith("FOLD")


def test_deep_strong_made_calls():
    """Top set derin all-in → CALL (gerçek değer)."""
    assert _act(["Kh", "Kd"], 30.0, 30.0, ["Ks", "7c", "2d", "9h"]).startswith("CALL")


def test_deep_trash_folds():
    """Çöp (72o/A-K-Q) derin all-in → FOLD."""
    assert _act(["7c", "2d"], 40.0, 30.5, ["Ah", "Kd", "Qs", "3h"]).startswith("FOLD")


def test_d270_scary_board_priced_in_calls():
    """D270: paired/scary board'da short all-in — threat-haircut UYGULANMAZ (showdown).
    İki-çift (hero 9 + board QQ/9) 0.8bb shove'a karşı → CALL (be tiny, ham eq>>be).
    Eski (eq_facing) threat'i be altına itip FOLD'latıyordu."""
    h=[card_from_str('6h'),card_from_str('9s')]; b=[card_from_str(x) for x in ['2c','Qh','3d','9d','Qd']]
    hero=types.SimpleNamespace(hole_cards=h,stack=0.8,is_folded=False,is_eliminated=False)
    v=types.SimpleNamespace(hole_cards=[],stack=80.0,is_folded=False,is_eliminated=False)
    hd=types.SimpleNamespace(players=[hero,v],community=b,street=Street.RIVER,pot=30.0,active_count=2,to_call=lambda i:30.0)
    assert soyrac_postflop_advice(hd,0)['action'].startswith('CALL')


def test_d272_deep_facing_bet_human_book():
    """D272 (MC geri alındı, %100 insan-kitap): DERİN facing-bet normal pot-odds'ta (be~%33)
    KQ gutshot (3:1, %18<%33) → FOLD (kitabın tier+pot-odds yöntemi, insan-hesaplanabilir)."""
    h = [card_from_str("Kh"), card_from_str("Qh")]; b = [card_from_str(x) for x in ["8d", "9c", "Th", "7d"]]
    hero = types.SimpleNamespace(hole_cards=h, stack=40.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.TURN,
                               pot=10.0, active_count=2, to_call=lambda i: 5.0)   # be≈%33 normal
    assert soyrac_postflop_advice(hd, 0)["action"].startswith("FOLD")
