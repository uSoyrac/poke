"""D321: value_up — 'saha öder → büyük value-bet' (VALIDATED ters-hipotez).
Cash +6.8…+42.3 bb/100 (her alan) + soft-MTT ROI +10.8; tough-MTT'de KAPALI (−9.6).
Yalnız made-value (NUT/GÜÇLÜ/ORTA) sizing büyür; blöf/çekme AYNI; default False = baz (fidelity)."""
import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Card, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice


def _spot(hole, board, vup):
    random.seed(2)
    gl = PokerGame(num_players=2, starting_stack=100, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Reg"], player_names=["v"])
    gl.start_hand()
    h = gl.current_hand; hi = h.hero_idx
    h.players[hi].hole_cards = hole
    h.community = board
    h.street = Street.FLOP
    for p in h.players:
        p.current_bet = 0.0
    h.current_bet = 0.0
    return soyrac_postflop_advice(h, hi, value_up=vup)


_B = [Card("9", "d"), Card("7", "d"), Card("4", "s")]   # semi-ıslak


def test_value_up_bigger_for_value():
    """Made-value (set) → value_up sizing 0.55→0.7 (daha çok çekme)."""
    base = _spot([Card("9", "h"), Card("9", "c")], _B, False)
    up = _spot([Card("9", "h"), Card("9", "c")], _B, True)
    assert "BET" in base["action"], base["action"]
    assert base["size_frac"] == 0.55
    assert up["size_frac"] == 0.7 and up["size_frac"] > base["size_frac"]


def test_value_up_default_off_identity():
    """Default value_up=False → baz sizing korunur (fidelity / bot-yolu değişmez)."""
    assert _spot([Card("9", "h"), Card("9", "c")], _B, False)["size_frac"] == 0.55


def test_value_up_skips_bluff():
    """Blöf/çekme (made-value DEĞİL) → value_up DOKUNMAZ (riskli büyük-blöf yok)."""
    base = _spot([Card("A", "h"), Card("K", "c")], _B, False)
    up = _spot([Card("A", "h"), Card("K", "c")], _B, True)
    assert base["size_frac"] == up["size_frac"]
