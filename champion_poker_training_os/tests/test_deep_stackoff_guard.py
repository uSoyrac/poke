"""D333 (kullanıcı: AJ-tipi DERİN top-pair'i çok-sokak yatırıp 68bb yedi): derin-stack çok-sokak
stack-off disiplini — ADVICE-ONLY koç-katmanı (bot/base DEĞİŞMEZ → fidelity 0). Derin + ıslak +
çok-sokak büyük-barrel + non-nut made-hand + base CALL → koç FOLD/pot-kontrol uyarısı."""
import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Action, ActionType, Card, Street
from app.poker.soyrac_advisor import soyrac_explain, soyrac_postflop_advice


def _build(stack=50.0, multistreet=True):
    random.seed(2)
    gl = PokerGame(num_players=2, starting_stack=100, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Reg"], player_names=["v"])
    gl.start_hand()
    h = gl.current_hand; hi = h.hero_idx; vi = 1 - hi
    h.players[hi].hole_cards = [Card("A", "d"), Card("J", "d")]
    h.community = [Card("Q", "c"), Card("A", "c"), Card("T", "d"), Card("2", "s")]  # ıslak turn
    h.street = Street.TURN
    acts = [Action(player_idx=vi, action_type=ActionType.RAISE, amount=3, street=Street.PREFLOP),
            Action(player_idx=hi, action_type=ActionType.CALL, amount=3, street=Street.PREFLOP)]
    if multistreet:
        acts += [Action(player_idx=vi, action_type=ActionType.BET, amount=4, street=Street.FLOP),
                 Action(player_idx=hi, action_type=ActionType.CALL, amount=4, street=Street.FLOP)]
    acts.append(Action(player_idx=vi, action_type=ActionType.BET, amount=14, street=Street.TURN))
    h.actions = acts
    h.current_bet = 14.0
    for p in h.players:
        p.current_bet = 0.0
    h.players[hi].stack = stack
    try:
        h.pot = 22.0
    except Exception:
        pass
    return h, hi


def test_guard_fires_deep_multistreet():
    h, hi = _build(stack=50.0, multistreet=True)
    exp = soyrac_explain("AJs", "BB", scenario="Postflop", hand=h, hero_idx=hi)
    assert exp["action"] == "FOLD" and exp.get("deep_stackoff_guard") is True


def test_base_unchanged_fidelity():
    """Bot/base (soyrac_postflop_advice) DEĞİŞMEZ → CALL (advice-only katman, fidelity 0)."""
    h, hi = _build(stack=50.0, multistreet=True)
    assert soyrac_postflop_advice(h, hi)["action"] == "CALL"


def test_guard_off_when_shallow():
    """Sığ (stack<35bb) → derin-disiplin tetiklenmez (kısa-stack zaten commit)."""
    h, hi = _build(stack=18.0, multistreet=True)
    exp = soyrac_explain("AJs", "BB", scenario="Postflop", hand=h, hero_idx=hi)
    assert not exp.get("deep_stackoff_guard")


def test_guard_off_when_single_street():
    """Tek-sokak (önceki barrel YOK) → guard tetiklenmez (çok-sokak value işareti gerekli)."""
    h, hi = _build(stack=50.0, multistreet=False)
    exp = soyrac_explain("AJs", "BB", scenario="Postflop", hand=h, hero_idx=hi)
    assert not exp.get("deep_stackoff_guard")
