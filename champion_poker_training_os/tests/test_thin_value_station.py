"""D255 (+EV-max audit #11): kuru/statik board + checked-to + ORTA-el → calling station
zayıf-eliyle öder → küçük THIN-VALUE bas (CHECK yerine). No-read/reg → CHECK korunur."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice

_STATION = {"vpip": 62, "pfr": 8, "aggression": 0.9, "obs_hands": 120}
# K3o top-pair zayıf-kicker, kuru board (ORTA-tier, checked-to)
_SPOT = (["Ks", "3d"], ["4d", "5d", "Jh", "8c", "Kh"])


def _adv(hole, board, vstats):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=80.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.RIVER,
                               pot=10.0, active_count=2, to_call=lambda i: 0.0)
    return soyrac_postflop_advice(hd, 0, villain_stats=vstats)


def test_station_thin_value_bets():
    """Station'a ORTA-el → küçük thin-value BET (CHECK değil)."""
    r = _adv(*_SPOT, _STATION)
    assert "thin-value" in r["action"], r["action"]
    assert r["size_frac"] <= 0.40
    assert r["tier"] == "ORTA"


def test_no_read_checks():
    """Okuma YOK → CHECK (baseline korunur, thin-value YOK)."""
    r = _adv(*_SPOT, None)
    assert r["action"].startswith("CHECK"), r["action"]
