"""D339 (kullanıcı: Broadway düz EŞLİ-board'da 'ORTA→CHECK'di, 'ölçülü value' notuyla çelişiyordu):
eşli-board düz → GÜÇLÜ ince-VALUE bet (küçük boyut), CHECK değil; büyük-bet'e bluff-catch (raise değil)."""
import random
from app.engine.game_loop import PokerGame
from app.engine.hand_state import Card, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice


def _spot(board, facing=0.0):
    random.seed(1)
    gl = PokerGame(num_players=2, starting_stack=100, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=["Reg"], player_names=["v"])
    gl.start_hand(); h = gl.current_hand; hi = h.hero_idx
    h.players[hi].hole_cards = [Card("A", "d"), Card("T", "d")]   # Broadway düz
    h.community = board
    h.street = Street.RIVER
    for p in h.players:
        p.current_bet = 0.0
    h.current_bet = facing
    if facing:
        h.pot = 20.0
    return soyrac_postflop_advice(h, hi)


_PAIRED = [Card("J", "h"), Card("K", "h"), Card("8", "c"), Card("K", "d"), Card("Q", "d")]   # KK eşli
_DRY = [Card("J", "h"), Card("K", "h"), Card("8", "c"), Card("2", "d"), Card("Q", "d")]       # eşsiz


def test_paired_straight_thin_value_bet():
    r = _spot(_PAIRED)
    assert "BET" in r["action"] and r["tier"] == "GÜÇLÜ"      # CHECK DEĞİL
    assert r["size_frac"] <= 0.40                            # ince/küçük boyut


def test_unpaired_straight_still_nut():
    r = _spot(_DRY)
    assert r["tier"] == "NUT" and "BET" in r["action"]       # eşsiz board → nut, korunur


def test_paired_straight_facing_bet_bluffcatch_not_raise():
    r = _spot(_PAIRED, facing=14.0)
    assert "RAISE" not in r["action"]                        # boat-riski → raise YOK (call/fold)
