"""Combo-sayım antrenörü — random river bluff-catch spot üretici + grader.

Gerçek masa hissi: random hero eli + 5-kart board + villain'ın polarize bahis
range'i. Öğrenci value:bluff combo'yu kafadan sayıp CALL/FOLD der; sonra
combinatorics motoru kesin cevabı + blocker'ı verir. Saf (Qt/DB bağımsız).
"""
from __future__ import annotations

import random
from typing import List

from app.engine.hand_state import Card
from app.engine.evaluator import evaluate_best_hand
from app.poker.combinatorics import bluff_catch_analysis, parse_cards

_RANKS = "23456789TJQKA"
_SUITS = "cdhs"

# Villain'ın river'da bahis attığı POLARİZE range (niyet bazlı): değer + blöf.
# Hangisinin hero'yu geçtiği board+hero'ya göre combinatorics'te belirlenir.
_VALUE_INTENT = ["AA", "KK", "QQ", "JJ", "TT", "99",
                 "AK", "AQ", "AJ", "KQ", "ATs", "KJs"]
_BLUFF_INTENT = ["T9s", "98s", "87s", "76s", "65s", "54s",
                 "A5s", "A4s", "A3s", "A2s", "J9s", "QJs"]
# Villain stilleri → range polaritesi. Çeşitlilik için (bazı spot CALL, bazı
# FOLD): value-ağır sıkı bettor (fold), dengeli, blöf-ağır (call) — gerçek
# popülasyonun farklı bettor tipleri.
_STYLES = {
    "value-ağır (sıkı bettor)": {"value": _VALUE_INTENT,
                                 "bluff": _BLUFF_INTENT[:3]},
    "dengeli":                  {"value": _VALUE_INTENT,
                                 "bluff": _BLUFF_INTENT},
    "blöf-ağır (overbluffer)":  {"value": _VALUE_INTENT[:5],
                                 "bluff": _BLUFF_INTENT + ["KQs", "QJo", "JTo", "T9o"]},
}

_BET_FRACS = [0.4, 0.5, 0.66, 0.75, 1.0]


def _full_deck() -> List[Card]:
    return [Card(r, s) for r in _RANKS for s in _SUITS]


def generate_spot(rng=None, max_tries: int = 200) -> dict:
    """Random river bluff-catch spot üret. Hero'yu gerçek bir BLUFF-CATCHER'a
    biasla (tek/iki pair — ne hava ne nut). Döner: UI + grader için sözlük."""
    rng = rng or random
    for _ in range(max_tries):
        deck = _full_deck()
        rng.shuffle(deck)
        hero = deck[:2]
        board = deck[2:7]
        # Hero gerçek bir bluff-catcher mi? (One Pair / Two Pair → rank 7-8)
        hrank = evaluate_best_hand(hero, board)[0]
        if hrank not in (7, 8):          # 8=one pair, 7=two pair
            continue
        hero_s = " ".join(c.code for c in hero)
        board_s = " ".join(c.code for c in board)
        style_name = rng.choice(list(_STYLES))
        style = _STYLES[style_name]
        villain_range = list(style["value"]) + list(style["bluff"])
        villain_desc = (
            f"Villain stili: {style_name}. River bahis range'i — değer: "
            f"{', '.join(style['value'][:6])}…  +  blöf: {', '.join(style['bluff'][:6])}…")
        pot = 20.0
        to_call = round(pot * rng.choice(_BET_FRACS), 1)
        analysis = bluff_catch_analysis(hero_s, board_s, villain_range, pot, to_call)
        # Anlamlı spot: villain'ın hem value hem bluff combo'su olsun
        if analysis["value_combos"] < 2 or analysis["bluff_combos"] < 2:
            continue
        return {
            "hero_cards": hero_s,
            "board": board_s,
            "villain_range": villain_range,
            "villain_desc": villain_desc,
            "villain_style": style_name,
            "pot_bb": pot,
            "to_call_bb": to_call,
            "position": "BB",
            "table": "6-max",
            "stack_bb": 100.0,
            "street": "river",
            "correct_action": "CALL" if analysis["call_ok"] else "FOLD",
            "analysis": analysis,
        }
    # Çok nadir: hiç uygun spot çıkmazsa son denemeyi yine de döndür
    return {
        "hero_cards": hero_s, "board": board_s,
        "villain_range": villain_range, "villain_desc": villain_desc,
        "villain_style": style_name,
        "pot_bb": 20.0, "to_call_bb": to_call, "position": "BB", "table": "6-max",
        "stack_bb": 100.0, "street": "river",
        "correct_action": "CALL" if analysis["call_ok"] else "FOLD",
        "analysis": analysis,
    }


def grade(spot: dict, action: str) -> dict:
    """Öğrencinin CALL/FOLD kararını değerlendir. Döner: doğru mu + açıklama."""
    correct = spot.get("correct_action", "FOLD")
    a = spot.get("analysis", {})
    is_correct = (action or "").upper() == correct
    return {
        "correct": is_correct,
        "your_action": (action or "").upper(),
        "correct_action": correct,
        "analysis": a,
    }
