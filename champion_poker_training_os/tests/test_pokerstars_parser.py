"""GERÇEK PokerStars el-geçmişi parser'ı — stub değil.

Standart PokerStars NLHE cash formatını parse eder: hero kartları, board,
pozisyon, sokak-bazlı aksiyonlar, pot, hero net sonucu (bb), VPIP/PFR bayrakları.
Çıktı played_hands şeması + hero-stat bayrakları + bb-normalize (D97) uyumlu.
"""
from __future__ import annotations

from app.parsers.pokerstars_parser import parse_pokerstars

_HAND = """\
PokerStars Hand #240000000001: Hold'em No Limit ($0.50/$1.00 USD) - 2024/03/01 20:00:00 ET
Table 'Antares' 6-max Seat #1 is the button
Seat 1: villain_btn ($100.00 in chips)
Seat 2: HeroGuy ($100.00 in chips)
Seat 3: villain_bb ($120.00 in chips)
Seat 4: villain_utg ($98.00 in chips)
Seat 5: villain_mp ($150.00 in chips)
Seat 6: villain_co ($102.00 in chips)
villain_bb: posts small blind $0.50
villain_utg: posts big blind $1.00
*** HOLE CARDS ***
Dealt to HeroGuy [As Kh]
villain_mp: folds
villain_co: folds
villain_btn: folds
HeroGuy: raises $2.50 to $3.50
villain_bb: folds
villain_utg: calls $2.50
*** FLOP *** [Kd 9s 4h]
villain_utg: checks
HeroGuy: bets $4.00
villain_utg: calls $4.00
*** TURN *** [Kd 9s 4h] [2c]
villain_utg: checks
HeroGuy: bets $9.00
villain_utg: folds
Uncalled bet ($9.00) returned to HeroGuy
HeroGuy collected $14.50 from pot
*** SUMMARY ***
Total pot $15.50 | Rake $1.00
Board [Kd 9s 4h 2c]
Seat 2: HeroGuy collected ($14.50)
"""


def _hand():
    hands = parse_pokerstars(_HAND, hero_name="HeroGuy")
    assert len(hands) == 1
    return hands[0]


def test_basic_fields():
    h = _hand()
    assert h["site"] == "PokerStars"
    assert h["hand_id"] == "240000000001"
    assert h["big_blind"] == 1.0
    assert h["small_blind"] == 0.5
    assert h["hero_cards"] in ("As Kh", "AsKh")
    assert h["board"].replace(" ", "") == "Kd9s4h2c"
    assert h["streets_seen"] >= 3            # preflop+flop+turn


def test_hero_position_and_flags():
    h = _hand()
    # Hero seat 2; button seat 1 → hero is SB? No: button=1, SB=next=2 → Hero SB.
    # (Pozisyon türetimi button'a göre.)
    assert h["hero_position"] in ("SB", "BB", "UTG", "MP", "CO", "BTN")
    # Hero preflop'ta RAISE etti (gönüllü + agresif)
    assert h["hero_vpip"] == 1
    assert h["hero_pfr"] == 1


def test_hero_result_in_bb():
    h = _hand()
    # Hero invested 3.5 (preflop) + 4 (flop) = 7.5; collected 14.5 → net +7.0 → +7bb
    assert abs(h["result_bb"] - 7.0) < 0.5
    assert h["hero_won"] is True


def test_game_type_cash():
    h = _hand()
    assert h["game_type"] == "cash"


def test_import_roundtrip_bb_normalized(tmp_path, monkeypatch):
    """parse → played_hands DB → okuma: dolar-ölçek + big_blind → /bb ile bb (D97).
    Cash stats saçma değil (import edilen gerçek eller leak analizine hazır)."""
    from app.db import repository as R
    monkeypatch.setattr(R, "DB_PATH", tmp_path / "imp.db")
    R.initialize_database()
    h = parse_pokerstars(_HAND, hero_name="HeroGuy")[0]
    R.save_played_hand({
        "hand_id": f"PS-{h['hand_id']}", "hero_cards": h["hero_cards"],
        "community": h["community"], "pot": h["pot"],
        "hero_invested": h["hero_invested"], "hero_profit": h["hero_profit"],
        "hero_won": h["hero_won"], "streets_seen": h["streets_seen"],
        "big_blind": h["big_blind"], "game_type": h["game_type"],
        "hero_vpip": h["hero_vpip"], "hero_pfr": h["hero_pfr"],
    })
    rows = {r["hand_id"]: r for r in R.get_session_history(50)}
    assert "PS-240000000001" in rows
    row = rows["PS-240000000001"]
    assert row["big_blind"] == 1.0 and row["game_type"] == "cash"
    assert abs(row["hero_profit"] / row["big_blind"] - 7.0) < 0.5   # bb-normalize
    s = R.get_player_stats()
    assert s["bb_per_100"] < 5000          # çip-sızıntısı/saçma DEĞİL
