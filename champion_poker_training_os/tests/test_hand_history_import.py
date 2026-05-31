"""Gerçek el geçmişi import — PokerStars parser (Phase D7) testleri."""
from __future__ import annotations

from app.poker.hand_history_import import parse_pokerstars

# Hero kazanır (rakip fold), flop'a kadar gider, uncalled bet döner.
HAND_WIN = """\
PokerStars Hand #100000001: Hold'em No Limit ($0.50/$1.00 USD) - 2024/01/01 12:00:00 ET
Table 'Test' 6-max Seat #1 is the button
Seat 1: Hero ($100 in chips)
Seat 2: Villain ($100 in chips)
Hero: posts small blind $0.50
Villain: posts big blind $1
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
Hero: raises $2 to $3
Villain: calls $2
*** FLOP *** [7c 2d 9s]
Villain: checks
Hero: bets $4
Villain: folds
Uncalled bet ($4) returned to Hero
Hero collected $5.50 from pot
*** SUMMARY ***
Total pot $6 | Rake $0.50
Board [7c 2d 9s]
Seat 1: Hero collected ($5.50)
"""

# Hero kaybeder (river'a gider, fold eder).
HAND_LOSE = """\
PokerStars Hand #100000002: Hold'em No Limit ($0.50/$1.00 USD) - 2024/01/01 12:05:00 ET
Table 'Test' 6-max Seat #2 is the button
Seat 1: Hero ($100 in chips)
Seat 2: Villain ($100 in chips)
Villain: posts small blind $0.50
Hero: posts big blind $1
*** HOLE CARDS ***
Dealt to Hero [Qd Jc]
Villain: raises $2 to $3
Hero: calls $2
*** FLOP *** [Ah 7c 2d]
Hero: checks
Villain: bets $4
Hero: calls $4
*** TURN *** [Ah 7c 2d] [8s]
Hero: checks
Villain: bets $10
Hero: folds
Uncalled bet ($10) returned to Villain
Villain collected $14 from pot
*** SUMMARY ***
Total pot $14 | Rake $0
Board [Ah 7c 2d 8s]
"""


def test_parses_two_hands():
    hands = parse_pokerstars(HAND_WIN + "\n\n" + HAND_LOSE)
    assert len(hands) == 2


def test_winning_hand_fields():
    h = parse_pokerstars(HAND_WIN)[0]
    assert h["hand_id"] == "HH-100000001"
    assert h["hero_cards"] == "Ah Kh"
    assert h["community"] == "7c 2d 9s"
    assert h["streets_seen"] == 2          # flop'a gitti
    assert h["hero_won"] is True
    # invested = 0.5(sb)+2.5(raise to 3)+4(flop bet)=7 ; returned 4 ; collected 5.5
    # net = 5.5 + 4 - 7 = 2.5 (bb=1 → 2.5bb)
    assert abs(h["hero_profit"] - 2.5) < 0.01


def test_losing_hand_fields():
    h = parse_pokerstars(HAND_LOSE)[0]
    assert h["hero_won"] is False
    assert h["streets_seen"] == 3          # turn'e gitti
    # invested = 1(bb)+2(call)+4(flop call) = 7 ; collected 0 → net -7
    assert abs(h["hero_profit"] + 7.0) < 0.01


def test_ignores_non_pokerstars_text():
    assert parse_pokerstars("random text\n\nno hands here") == []


def test_empty():
    assert parse_pokerstars("") == []


def test_voluntary_only_filters_preflop_folds(tmp_path, monkeypatch):
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "vol.db")
    R.initialize_database()
    # Insta-fold (streets 1, sadece blind) — gösterilmemeli
    R.save_played_hand({"hand_id": 1, "hero_cards": "7d2c", "community": "",
                        "pot": 1.5, "hero_invested": 0.5, "hero_profit": -0.5,
                        "hero_won": 0, "streets_seen": 1})
    # Oynanan: flop gördü
    R.save_played_hand({"hand_id": 2, "hero_cards": "AhKh", "community": "Ah7c2d",
                        "pot": 8, "hero_invested": 4, "hero_profit": 4,
                        "hero_won": 1, "streets_seen": 2})
    # Oynanan: preflop raise edip 3bet'e fold (VPIP, streets 1 ama invested>1)
    R.save_played_hand({"hand_id": 3, "hero_cards": "QsJs", "community": "",
                        "pot": 12, "hero_invested": 3, "hero_profit": -3,
                        "hero_won": 0, "streets_seen": 1})
    assert R.count_played_hands() == 3
    assert R.count_played_hands(voluntary_only=True) == 2     # insta-fold elenir
    ids = {h["hand_id"] for h in R.get_session_history(10, voluntary_only=True)}
    assert ids == {2, 3}


def test_import_roundtrip_to_db(tmp_path, monkeypatch):
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "imp.db")
    R.initialize_database()
    before = R.get_player_stats()["total_hands"]
    n = R.import_hands_from_text(HAND_WIN + "\n\n" + HAND_LOSE)
    assert n == 2
    after = R.get_player_stats()["total_hands"]
    assert after == before + 2
    # İçeri alınan eller arşivde görünür
    hist = R.get_session_history(limit=10)
    ids = {h["hand_id"] for h in hist}
    assert "HH-100000001" in ids and "HH-100000002" in ids


# ── Çok-site: GGPoker + CoinPoker (PokerStars-türevi format) ──────────
HAND_GG = """\
GGPoker Hand #HD2500000001: Hold'em No Limit ($0.50/$1.00) - 2024/01/01 12:00:00
Table 'NLHGold01' 6-max Seat #1 is the button
Seat 1: Hero ($100 in chips)
Seat 2: Villain ($100 in chips)
Hero: posts small blind $0.50
Villain: posts big blind $1
*** HOLE CARDS ***
Dealt to Hero [Qd Qc]
Hero: raises $2 to $3
Villain: folds
Uncalled bet ($2) returned to Hero
Hero collected $2 from pot
*** SUMMARY ***
Total pot $2 | Rake $0
"""

# CoinPoker: para sembolsüz düz sayı (USDT/chip)
HAND_COIN = """\
CoinPoker Hand #987654321: Hold'em No Limit (0.50/1) - 2024/01/01 12:00:00
Table 'Aurora' 6-max Seat #1 is the button
Seat 1: Hero (100 in chips)
Seat 2: Villain (100 in chips)
Hero: posts small blind 0.50
Villain: posts big blind 1
*** HOLE CARDS ***
Dealt to Hero [Jh Ts]
Hero: raises 2 to 3
Villain: calls 2
*** FLOP *** [7c 2d 9s]
Villain: checks
Hero: bets 4
Villain: folds
Uncalled bet (4) returned to Hero
Hero collected 5.50 from pot
*** SUMMARY ***
Total pot 6
Board [7c 2d 9s]
"""


def test_ggpoker_parses():
    hands = parse_pokerstars(HAND_GG)
    assert len(hands) == 1
    h = hands[0]
    assert h["hero_cards"] == "Qd Qc"
    assert h["site"] == "GGPoker"
    assert h["hero_won"] is True


def test_coinpoker_parses_no_currency_symbol():
    hands = parse_pokerstars(HAND_COIN)
    assert len(hands) == 1
    h = hands[0]
    assert h["hero_cards"] == "Jh Ts"
    assert h["site"] == "CoinPoker"
    assert h["streets_seen"] == 2          # flop görüldü
    assert h["hero_won"] is True


def test_mixed_file_all_sites():
    hands = parse_pokerstars(HAND_WIN + "\n\n" + HAND_GG + "\n\n" + HAND_COIN)
    sites = {h["site"] for h in hands}
    assert len(hands) == 3
    assert {"PokerStars", "GGPoker", "CoinPoker"} <= sites
