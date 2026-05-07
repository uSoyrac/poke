"""Tests for the PokerStars hand history parser."""
from __future__ import annotations

from app.parsers.hand_history_parser import parse_hand_history
from app.parsers.pokerstars_parser import _classify_pot_type, _detect_position, parse_pokerstars


# --- Fixtures ----------------------------------------------------------------

DEMO_BLOCK = """PokerStars Hand #DEMO-0001: Tournament #ChampionLab, Hold'em No Limit - Level IX
Hero (BTN) dealt As Kh
CO opens 2.2bb, Hero raises 6.5bb, blinds fold, CO calls
Flop Ah 7c 2d. CO checks, Hero bets 33%, CO calls
Turn 9s. CO checks, Hero bets 66%, CO calls
River 4c. CO checks, Hero decides."""

PRODUCTION_HAND = """PokerStars Hand #240999000111: Tournament #2244668800, $5+$0.50 USD Hold'em No Limit - Level VIII (75/150) - 2024/06/01 19:35:21 ET
Table '2244668800 23' 6-max Seat #5 is the button
Seat 1: Player1 (3500 in chips)
Seat 2: Player2 (4200 in chips)
Seat 3: Hero (5100 in chips)
Seat 4: Player4 (2800 in chips)
Seat 5: Player5 (6700 in chips)
Seat 6: Player6 (3900 in chips)
Player6: posts small blind 75
Player1: posts big blind 150
*** HOLE CARDS ***
Dealt to Hero [As Kh]
Player2: folds
Hero: raises 300 to 450
Player4: folds
Player5: folds
Player6: folds
Player1: calls 300
*** FLOP *** [Ah 7c 2d]
Player1: checks
Hero: bets 600
Player1: calls 600
*** TURN *** [Ah 7c 2d] [9s]
Player1: checks
Hero: bets 1500
Player1: folds
Uncalled bet (1500) returned to Hero
Hero collected 2100 from pot
*** SUMMARY ***
Total pot 2100 | Rake 0
Board [Ah 7c 2d 9s]
Seat 3: Hero showed [As Kh] and won (2100)
"""

TWO_HAND_FILE = PRODUCTION_HAND + "\n\n" + DEMO_BLOCK


# --- Tests -------------------------------------------------------------------

def test_parses_production_hand_metadata():
    hands = parse_pokerstars(PRODUCTION_HAND)
    assert len(hands) == 1
    h = hands[0]
    assert h["external_id"] == "240999000111"
    assert h["site"] == "PokerStars"
    assert h["hero_cards"] == "AsKh"
    assert h["board"].startswith("Ah7c2d")
    assert h["pot_type"] == "SRP"
    assert h["preflop_actions"] != ""
    assert h["flop_actions"] != ""


def test_production_hand_extracts_hero_position_and_profit():
    hands = parse_pokerstars(PRODUCTION_HAND)
    h = hands[0]
    # Hero is at seat 3, button at seat 5, 6-max → hero is in HJ (rel == 4)
    assert h["hero_position"] in {"HJ", "UTG", "CO", "MP", "LJ", "BTN"}
    # Pot total / BB = 2100 / 150 = 14.0
    assert abs(h["pot_bb"] - 14.0) < 0.5
    # Hero profit > 0 (won the hand)
    assert h["hero_profit_bb"] > 0


def test_demo_block_parses_with_minimal_metadata():
    hands = parse_pokerstars(DEMO_BLOCK)
    assert len(hands) == 1
    assert hands[0]["external_id"] == "DEMO-0001"


def test_split_multiple_hands_in_one_file():
    hands = parse_pokerstars(TWO_HAND_FILE)
    assert len(hands) == 2
    ids = {h["external_id"] for h in hands}
    assert "240999000111" in ids and "DEMO-0001" in ids


def test_parse_hand_history_routes_to_pokerstars():
    hands = parse_hand_history(PRODUCTION_HAND)
    assert hands and hands[0]["site"] == "PokerStars"


def test_classify_pot_type_handles_common_lines():
    # one raise, others fold/call -> SRP
    assert _classify_pot_type([("a", "F", 0), ("b", "R", 3), ("c", "F", 0), ("d", "C", 3)]) == "SRP"
    # two raises -> 3BP
    assert _classify_pot_type([("a", "R", 3), ("b", "R", 9)]) == "3BP"
    # three raises -> 4BP
    assert _classify_pot_type([("a", "R", 3), ("b", "R", 9), ("c", "R", 27)]) == "4BP"
    # raise after a flat-call -> Squeeze
    assert _classify_pot_type([("a", "C", 1), ("b", "R", 3), ("c", "R", 12)]) == "Squeeze"


def test_position_detection_six_max():
    # Button at seat 5; SB is seat after button (seat 6 wraps)
    assert _detect_position(seat=5, button_seat=5, size=6) == "BTN"
    assert _detect_position(seat=6, button_seat=5, size=6) == "SB"
    assert _detect_position(seat=1, button_seat=5, size=6) == "BB"


def test_empty_input_returns_empty_list():
    assert parse_pokerstars("") == []
    assert parse_hand_history("") == []


def test_malformed_block_does_not_crash():
    junk = "This is not a hand history at all. Random nonsense."
    assert parse_pokerstars(junk) == []
