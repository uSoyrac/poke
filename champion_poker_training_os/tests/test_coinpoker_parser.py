"""Tests for the CoinPoker hand history parser."""
from __future__ import annotations

from app.parsers.coinpoker_parser import parse_coinpoker
from app.parsers.hand_history_parser import parse_hand_history


COINPOKER_TOURNEY = """CoinPoker Hand #5500001234: Tournament #2024061501, $5+$0.50 USDT Hold'em No Limit - Level VI (50/100) - 2024/06/15 19:00:00 UTC
Table 'Tournament 2024061501 7' 6-max Seat #4 is the button
Seat 1: GrindMaster (4825)
Seat 2: BluffMonkey (3950)
Seat 3: Hero (5200)
Seat 4: SolverBot (6100)
Seat 5: NitNitNit (2700)
Seat 6: ChipShark (4200)
ChipShark: posts small blind 50
GrindMaster: posts big blind 100
*** HOLE CARDS ***
Dealt to Hero [Ah Qd]
BluffMonkey: folds
Hero: raises 200 to 300
SolverBot: folds
NitNitNit: folds
ChipShark: calls 250
GrindMaster: folds
*** FLOP *** [Qh 7s 4d]
ChipShark: checks
Hero: bets 350
ChipShark: calls 350
*** TURN *** [Qh 7s 4d] [Ks]
ChipShark: checks
Hero: bets 800
ChipShark: folds
Uncalled bet (800) returned to Hero
Hero collected 1400 from pot
*** SUMMARY ***
Total pot 1400 | Rake 0
Board [Qh 7s 4d Ks]
Seat 3: Hero showed [Ah Qd] and won (1400)"""

COINPOKER_CASH_NO_INCHIPS = """CoinPoker Hand #5500001236: Hold'em No Limit (CHP $0.05/$0.10) - 2024/06/15 20:11:42 UTC
Table 'CHP Cash Lab 14' 6-max Seat #2 is the button
Seat 1: NewbieNeil (10.50)
Seat 2: Hero (12.30)
Seat 3: GrinderGus (9.85)
Seat 4: ScaredCarl (11.10)
Seat 5: BluffyBob (8.40)
Seat 6: SteadyStu (13.20)
GrinderGus: posts small blind 0.05
ScaredCarl: posts big blind 0.10
*** HOLE CARDS ***
Dealt to Hero [Kc Kh]
BluffyBob: raises 0.30 to 0.40
SteadyStu: folds
NewbieNeil: calls 0.40
Hero: raises 1.20 to 1.60
GrinderGus: folds
ScaredCarl: folds
BluffyBob: folds
NewbieNeil: calls 1.20
*** FLOP *** [9d 6c 2s]
NewbieNeil: checks
Hero: bets 2.40
NewbieNeil: calls 2.40
*** TURN *** [9d 6c 2s] [3h]
NewbieNeil: checks
Hero: bets 8.30 and is all-in
NewbieNeil: folds
Uncalled bet (8.30) returned to Hero
Hero collected 8.55 from pot
*** SUMMARY ***
Total pot 8.55 | Rake 0
Board [9d 6c 2s 3h]
Seat 2: Hero showed [Kc Kh] and won (8.55)"""


def test_coinpoker_parses_tournament_hand():
    hands = parse_coinpoker(COINPOKER_TOURNEY)
    assert len(hands) == 1
    h = hands[0]
    assert h["external_id"] == "5500001234"
    assert h["site"] == "CoinPoker"
    assert h["hero_cards"] == "AhQd"
    assert "Q" in h["board"][0]
    assert h["pot_type"] in {"SRP", "Limp"}
    # Hero wins with uncalled bet returned: profit > 0
    assert h["hero_profit_bb"] > 0


def test_coinpoker_parses_cash_without_in_chips_suffix():
    """CoinPoker cash exports often omit the 'in chips' suffix in seat lines."""
    hands = parse_coinpoker(COINPOKER_CASH_NO_INCHIPS)
    assert len(hands) == 1
    h = hands[0]
    assert h["external_id"] == "5500001236"
    assert h["hero_cards"] == "KcKh"
    # Hero is on the button (3-bet, won), profit should be positive
    assert h["hero_profit_bb"] > 0
    # Pot type is 3BP because there's a raise + 3bet preflop
    assert h["pot_type"] in {"3BP", "Squeeze"}


def test_hand_history_parser_routes_coinpoker():
    hands = parse_hand_history(COINPOKER_TOURNEY)
    assert hands and hands[0]["site"] == "CoinPoker"


def test_coinpoker_split_multiple_hands():
    combined = COINPOKER_TOURNEY + "\n\n" + COINPOKER_CASH_NO_INCHIPS
    hands = parse_coinpoker(combined)
    assert len(hands) == 2
    ids = {h["external_id"] for h in hands}
    assert {"5500001234", "5500001236"} <= ids


def test_coinpoker_empty_and_garbage():
    assert parse_coinpoker("") == []
    assert parse_coinpoker("This isn't a hand history at all.") == []
