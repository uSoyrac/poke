"""Kombinatorik — combo sayımı + value:bluff split + blocker (elit-koç kalbi).

Bilinen-değer doğrulaması: çift=6, suited=4, offsuit=12 combo; dead-card
çıkarımı; bluff-catch çerçevesinde value/bluff ayrımı + blocker etkisi.
"""
from __future__ import annotations

from app.poker.combinatorics import (
    bluff_catch_analysis, coach_combo_line, hand_class_combos,
    parse_cards, range_combos, split_vs_hero,
)


# ── Combo sayımı (bilinen değerler) ──────────────────────────────────
def test_combo_counts_no_dead():
    assert len(hand_class_combos("AA")) == 6
    assert len(hand_class_combos("AKs")) == 4
    assert len(hand_class_combos("AKo")) == 12


def test_dead_cards_remove_combos():
    # Bir As ölüyse AA combo'su C(3,2)=3'e düşer
    dead = parse_cards("Ah")
    assert len(hand_class_combos("AA", dead)) == 3
    # AKs'te Ah ölüyse 3 suited kalır
    assert len(hand_class_combos("AKs", dead)) == 3
    # Ah+Kh ölüyse yalnız kupa AKs combo'su gider → 3 kalır (♣♦♠)
    dead2 = parse_cards("Ah Kh")
    assert len(hand_class_combos("AKs", dead2)) == 3


def test_range_combos_aggregates():
    combos = range_combos(["AA", "KK", "AKs"], dead=None)
    assert len(combos) == 6 + 6 + 4


# ── Value/bluff split (hero'ya göre) ─────────────────────────────────
def test_split_value_vs_bluff_basic():
    # Hero set (777) çok güçlü; villain range AK/KQ (board'a vuramayan) → çoğu bluff
    board = parse_cards("7h 7d 2c")
    hero = parse_cards("7s 7c")          # quads aslında — kesin value lider
    combos = range_combos(["AK", "KQ", "QJ"], dead=board + hero)
    s = split_vs_hero(combos, board, hero)
    assert s["value"] == 0               # hiçbiri quad 7'yi geçemez
    assert s["bluff"] == s["total"]      # hepsi hero'ya kaybeder


def test_split_value_present_when_villain_can_beat_hero():
    # Hero zayıf (tek pair 2) ; villain range setler içeriyor → value var
    board = parse_cards("Ah Kd 2c")
    hero = parse_cards("2h 3h")          # bottom pair
    combos = range_combos(["AA", "KK", "AK"], dead=board + hero)
    s = split_vs_hero(combos, board, hero)
    assert s["value"] > 0                # AA/KK/AK hepsi 2'yi geçer


# ── Tam bluff-catch analizi ──────────────────────────────────────────
def test_bluff_catch_analysis_fields():
    board = "Qs 8d 4c 9h 2s"
    hero = "Ac Qc"                       # top pair top kicker (bluff-catcher)
    villain_range = ["AA", "KK", "QJ", "JT", "T9", "65s", "A5s"]  # value + missed draws
    a = bluff_catch_analysis(hero, board, villain_range, pot=20.0, to_call=10.0)
    assert a["total_combos"] > 0
    assert a["value_combos"] + a["bluff_combos"] + a["tie_combos"] == a["total_combos"]
    assert 0 <= a["win_pct"] <= 100
    assert abs(a["needed_equity"] - 33.3) < 1.0   # 10/(20+10)=%33.3
    assert isinstance(a["call_ok"], bool)


def test_blocker_effect_detected():
    # Hero As elinde → villain'ın As-içeren value combo'larını (AA, AK) bloklar
    board = "Kd 7c 2s 9h 3d"
    hero = "As Ad"                       # iki As → AA/AK value'larını ciddi bloklar
    villain_range = ["AA", "KK", "AK", "QJ"]
    a = bluff_catch_analysis(hero, board, villain_range, pot=10, to_call=5)
    # AA imkânsız (2 As hero'da) → value combo'ları azalır
    assert a["blocked_value"] >= 0
    assert "blocker_verdict" in a


def test_coach_line_renders():
    a = bluff_catch_analysis("Ac Qc", "Qs 8d 4c 9h 2s",
                             ["AA", "QJ", "JT"], pot=20, to_call=10)
    line = coach_combo_line(a)
    assert "Combo:" in line and "value" in line and "Blocker:" in line


def test_more_bluffs_favors_call():
    """Bluff-ağır range → kazanma% yüksek → call_ok True (pot odds aşılır)."""
    board = "Qh 8s 3d 9c 2h"
    hero = "Qd Jd"                       # top pair
    # Çoğu missed draw (bluff) + az value
    bluffy = ["AK", "AJ", "AT", "KJ", "JT", "T9", "65s", "54s", "A5s", "QQ"]
    a = bluff_catch_analysis(hero, board, bluffy, pot=20, to_call=6)  # %23 gereken
    assert a["bluff_combos"] > a["value_combos"]
    assert a["call_ok"]
