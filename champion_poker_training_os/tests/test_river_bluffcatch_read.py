"""D251: river over-fold leak — bilinen blöfçüye karşı made bluff-catcher gevşemiyordu.
eq_facing=eq−threat korkutucu board'da aşırı iskonto ediyordu → _bc_margin(-0.10) bile
yetmiyordu. Fix: bilinen blöfçü + made-hand (str≥0.30) → tehdidin ~yarısını geri ver.
No-read/pasif baseline (soft-field lean) DOKUNULMAZ → fidelity/advice 0-sapma."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice

_JACK = {"vpip": 30, "pfr": 10, "aggression": 3.5, "river_bluff": 40, "obs_hands": 150}
_NIT = {"vpip": 16, "pfr": 13, "aggression": 1.6, "river_bluff": 4, "obs_hands": 150}
_K8 = (["Kh", "8c"], ["Ts", "Tc", "6s", "3h", "8d"])   # pair of 8s on paired TT board


def _act(hole, board, vstats, tc=5.0, pot=10.0):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=80.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.RIVER,
                               pot=pot, active_count=2, to_call=lambda i: tc)
    return soyrac_postflop_advice(hd, 0, villain_stats=vstats)["action"]


def test_made_bluffcatch_calls_vs_known_bluffer():
    """Made bluff-catcher (K8 pair) BİLİNEN BLÖFÇÜYE karşı → CALL (blöfleri geçer)."""
    assert _act(*_K8, _JACK).startswith("CALL")


def test_no_read_baseline_preserved():
    """Okuma YOKsa → FOLD (soft-field over-fold lean korunur, değişmez)."""
    assert _act(*_K8, None).startswith("FOLD")


def test_passive_read_still_folds():
    """Pasif/nit rakip (az blöf) → FOLD (gevşetme YALNIZ blöfçüye)."""
    assert _act(*_K8, _NIT).startswith("FOLD")


def test_air_not_loosened_vs_bluffer():
    """Hava (ace-high, str<0.30) blöfçüye karşı bile FOLD (made-hand gate)."""
    assert _act(["Ah", "Jc"], ["9s", "9d", "5c", "2h", "7s"], _JACK).startswith("FOLD")
