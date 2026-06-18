"""D274 (multiway derinleştirme): 4+ yollu pot'ta tek-çift TOP-PAIR'i fat-value-bet etme
→ pot-kontrol (kalabalıkta ince value buharlaşır). Overpair/iki-çift+/set ROBUST → value
kalır. HU/3-yollu top-pair hâlâ basılır."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice


def _act(hole, board, n):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=80.0, is_folded=False, is_eliminated=False)
    vs = [types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
          for _ in range(n - 1)]
    hd = types.SimpleNamespace(players=[hero] + vs, community=b, street=Street.FLOP,
                               pot=10.0, active_count=n, to_call=lambda i: 0.0)
    return soyrac_postflop_advice(hd, 0)["action"]


_TPTK = (["Ah", "Qd"], ["As", "7c", "2d"])


def test_top_pair_pot_control_4way():
    """TPTK 4+ yollu → pot-kontrol CHECK (fat value DEĞİL)."""
    assert _act(*_TPTK, 4).startswith("CHECK")
    assert _act(*_TPTK, 5).startswith("CHECK")


def test_top_pair_value_bets_heads_up_and_3way():
    """TPTK HU + 3-yollu → BET (value) (kalabalık değil)."""
    assert _act(*_TPTK, 2) == "BET (value)"
    assert _act(*_TPTK, 3) == "BET (value)"


def test_robust_hands_value_bet_multiway():
    """Overpair / top-two / set → 5-yollu'da bile value-bet (robust)."""
    assert _act(["Ah", "Ad"], ["7c", "2d", "5h"], 5) == "BET (value)"   # overpair
    assert _act(["Kh", "9d"], ["Ks", "9c", "2d"], 5) == "BET (value)"   # top-two
    assert _act(["7h", "7d"], ["7c", "Kd", "2s"], 5) == "BET (value)"   # set
