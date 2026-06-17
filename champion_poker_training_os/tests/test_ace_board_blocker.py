"""D258 (+EV-max audit #8): Ace-board haircut SADECE hero A tutmuyorsa. Hero A tutarsa
(top-pair-top-kicker + blocker) "açan-range Ax ile vurur" tehdidi TERS → ceza kalkar
(çifte-haircut + AKs A-board over-fold önlenir)."""
from app.engine.hand_state import card_from_str
from app.poker.soyrac_advisor import _board_threat


def _thr(hole, board, label):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    return _board_threat(b, label, h)[0]


def test_hero_with_ace_no_ace_board_haircut():
    """AK / A-9-4: hero A blokluyor + TPTK → Ace-board cezası YOK."""
    assert _thr(["Ah", "Kd"], ["As", "9c", "4d"], "top pair") == 0.0


def test_no_ace_keeps_haircut():
    """KQ / A-9-4: hero A yok → 'açan-range vurur' cezası KORUNUR."""
    assert _thr(["Kh", "Qd"], ["As", "9c", "4d"], "high card") >= 0.10


def test_weak_ace_kicker_still_no_threat():
    """A2 / A-9-4: zayıf kicker olsa da A bloklar → Ace-board cezası yine YOK."""
    assert _thr(["Ah", "2d"], ["As", "9c", "4d"], "top pair") == 0.0
