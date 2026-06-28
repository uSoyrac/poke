"""D337 (oturum-sonu entegrasyon): canlı koç (soyrac_explain) bu oturumda eklenen 6+ advice-katmanını
(SAYIM read_count, value-up, ICM-proximity, station-classify, multiway-3bet, deep-stackoff-guard)
BİRLİKTE tutarlı üretiyor mu — çelişki/garbled-çıktı yok, action↔why tutarlı."""
import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Action, ActionType, Card, Street
from app.poker.soyrac_advisor import soyrac_explain

_VALID_POSTFLOP = ("FOLD", "CHECK", "CALL", "RAISE", "BET", "ALL_IN", "JAM")


def _postflop_hand(hole, board, stack=60.0, multistreet=True):
    random.seed(4)
    gl = PokerGame(num_players=2, starting_stack=100, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Reg"], player_names=["v"])
    gl.start_hand()
    h = gl.current_hand; hi = h.hero_idx; vi = 1 - hi
    h.players[hi].hole_cards = hole
    h.community = board
    h.street = Street.TURN if len(board) == 4 else Street.RIVER
    acts = [Action(player_idx=vi, action_type=ActionType.RAISE, amount=3, street=Street.PREFLOP),
            Action(player_idx=hi, action_type=ActionType.CALL, amount=3, street=Street.PREFLOP)]
    if multistreet:
        acts += [Action(player_idx=vi, action_type=ActionType.BET, amount=4, street=Street.FLOP),
                 Action(player_idx=hi, action_type=ActionType.CALL, amount=4, street=Street.FLOP)]
    acts.append(Action(player_idx=vi, action_type=ActionType.BET, amount=14, street=h.street))
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


_STATION = {"vpip": 24, "pfr": 7, "aggression": 1.5, "river_bluff": 48,
            "fold_to_cbet": 0, "call_down": 56, "obs_hands": 80}


def test_postflop_coach_coherent_with_station():
    """Cash postflop + station villain: çıktı yapısal-tam, action geçerli, why dolu, çelişki yok."""
    h, hi = _postflop_hand([Card("A", "d"), Card("J", "d")],
                           [Card("Q", "c"), Card("A", "c"), Card("T", "d"), Card("2", "s")],
                           stack=60.0)
    out = soyrac_explain("AJs", "BB", scenario="Postflop", hand=h, hero_idx=hi,
                         villain_stats=_STATION, tourney=False)
    assert out["action"] in _VALID_POSTFLOP
    assert out.get("why")                      # gerekçe boş değil
    assert out["tone"] in ("go", "caution", "stop", "hidden")
    # deep-stackoff-guard bu spotta tetiklenir (derin+ıslak+çok-sokak+top-pair) → FOLD + guard
    assert out["action"] == "FOLD" and out.get("deep_stackoff_guard") is True
    # read_count katmanı çelişki üretmez (varsa context cash)
    if out.get("read_count"):
        assert out["read_count"]["context"] == "cash"


def test_layers_no_crash_across_spots():
    """Birkaç temsili spot — hiçbir katman kombinasyonu crash/None-patlama üretmez."""
    spots = [
        ([Card("K", "h"), Card("K", "c")], [Card("7", "d"), Card("2", "c"), Card("9", "s")], 80.0),  # set kuru
        ([Card("A", "s"), Card("5", "s")], [Card("A", "h"), Card("K", "d"), Card("Q", "c"), Card("J", "s")], 40.0),
        ([Card("9", "h"), Card("8", "h")], [Card("7", "h"), Card("6", "h"), Card("2", "c")], 100.0),  # draw
    ]
    for hole, board, stk in spots:
        out = soyrac_explain("KK", "BB", scenario="Postflop", hand=_postflop_hand(hole, board, stk)[0],
                             hero_idx=0, villain_stats=_STATION, tourney=False)
        assert out["action"] in _VALID_POSTFLOP and isinstance(out.get("why", ""), str)


def test_bubble_pushfold_coherent():
    """Bubble push/fold (ICM + proximity): saçma '< eşik' eşitsizliği YOK (D324) + action geçerli."""
    import re
    e = soyrac_explain("AJo", "SB", scenario="Push/Fold", stack_bb=9, n_active=8,
                       tourney=True, stage="bubble", avg_stack_bb=40, players_to_money=1)
    assert e["action"] in ("JAM", "FOLD")
    blob = " ".join([e.get("why", ""), e.get("line", "") or "", " ".join(e.get("chain_steps", []))])
    for a, b in re.findall(r"Puan (-?\d+) < .*?(\d+)", blob):
        assert int(a) < int(b), f"saçma eşitsizlik: {a} < {b}"
