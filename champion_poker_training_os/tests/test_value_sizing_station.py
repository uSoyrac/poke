"""D253 (+EV-max audit — en büyük cash kayıp): value-bet boyutu rakip-tipine kördü.
CALLING STATION'a karşı thin-value için BÜYÜK bas; no-read/reg/bot GTO-baz korunur."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice

_STATION = {"vpip": 62, "pfr": 8, "aggression": 0.9, "obs_hands": 120}
_REG = {"vpip": 24, "pfr": 20, "aggression": 2.5, "obs_hands": 120}
_TOPSET = (["Kh", "Kd"], ["Ks", "7c", "2d", "9h", "3s"])   # top set, dry, river (value bet)


def _adv(hole, board, vstats):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=80.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.RIVER,
                               pot=10.0, active_count=2, to_call=lambda i: 0.0)
    return soyrac_postflop_advice(hd, 0, villain_stats=vstats)


def test_station_value_bet_sized_up():
    """Station'a value bet → daha BÜYÜK boyut (thin-value extraction)."""
    base = _adv(*_TOPSET, None)["size_frac"]
    st = _adv(*_TOPSET, _STATION)["size_frac"]
    assert st > base + 0.2, f"station {st} ≤ base {base}"
    assert st <= 1.10


def test_no_read_baseline_gto_preserved():
    """Okuma YOK → GTO board-bazlı boyut (değişmez)."""
    r = _adv(*_TOPSET, None)
    assert r["action"] == "BET (value)"
    assert 0.30 <= r["size_frac"] <= 0.80


def test_reg_not_sized_up():
    """REG (station değil) → boyut DOKUNULMAZ."""
    assert _adv(*_TOPSET, _REG)["size_frac"] == _adv(*_TOPSET, None)["size_frac"]
