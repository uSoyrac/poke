"""Range vs Range avantajı — elit koç: 'kim bahis atmalı?'

İki sürücü:
  • RANGE avantajı  = hangi range'in toplam equity'si yüksek (board'da kim daha
    çok kazanır).
  • NUT avantajı    = hangi range'de daha çok ÜST combo (set+/iki-pair+) var
    (kim büyük bahis/overbet atabilir).

Bu ikisi c-bet kararını belirler: ikisi de sendeyse küçük-yüksek-frekans range
bet; nut sende değilse yavaşla. Saf (Qt/DB bağımsız).

River'da (5 kart) equity EXACT (tüm combo-çiftleri kıyaslanır); flop/turn'de
runout için sınırlı Monte Carlo.
"""
from __future__ import annotations

import random
from itertools import combinations
from typing import List, Tuple

from app.engine.hand_state import Card
from app.engine.evaluator import evaluate_best_hand, _compare_hands
from app.poker.combinatorics import parse_cards, range_combos

_RANKS = "23456789TJQKA"
_SUITS = "cdhs"

# "Nut" eşiği: three-of-a-kind (set/trips) veya daha iyi (rank ≤ 6).
# (HAND_RANKS: 6=Three of a Kind, 7=Two Pair, 8=One Pair, 9=High Card)
_NUT_RANK_MAX = 6


def _nut_fraction(combos, board: List[Card]) -> float:
    """Bir range'in kaç %'i board'da 'nutted' (set+ )."""
    if not combos:
        return 0.0
    n = sum(1 for c0, c1 in combos
            if evaluate_best_hand([c0, c1], board)[0] <= _NUT_RANK_MAX)
    return 100.0 * n / len(combos)


def _river_equity(hero_combos, vill_combos, board) -> float:
    """5-kart board: hero range'inin villain range'ine karşı EXACT equity %
    (tüm geçerli combo-çiftleri; kazanma + ½ beraberlik)."""
    wins = ties = total = 0
    for h0, h1 in hero_combos:
        hk = {h0.code, h1.code}
        hb = evaluate_best_hand([h0, h1], board)
        for v0, v1 in vill_combos:
            if v0.code in hk or v1.code in hk:
                continue                      # kart çakışması — atla
            total += 1
            cmp = _compare_hands(hb, evaluate_best_hand([v0, v1], board))
            if cmp < 0:
                wins += 1
            elif cmp == 0:
                ties += 1
    if total == 0:
        return 50.0
    return 100.0 * (wins + 0.5 * ties) / total


def _mc_equity(hero_combos, vill_combos, board, dead, iterations, rng) -> float:
    """<5 kart board: turn/river runout için sınırlı Monte Carlo equity."""
    remaining = [Card(r, s) for r in _RANKS for s in _SUITS
                 if f"{r}{s}" not in {c.code for c in dead}]
    need = 5 - len(board)
    wins = ties = total = 0
    for _ in range(iterations):
        h = rng.choice(hero_combos)
        v = rng.choice(vill_combos)
        used = {h[0].code, h[1].code, v[0].code, v[1].code}
        if len(used) < 4:                     # hero/villain kart paylaşıyor
            continue
        pool = [c for c in remaining if c.code not in used]
        runout = rng.sample(pool, need)
        full = board + runout
        cmp = _compare_hands(evaluate_best_hand(list(h), full),
                             evaluate_best_hand(list(v), full))
        total += 1
        if cmp < 0:
            wins += 1
        elif cmp == 0:
            ties += 1
    return 100.0 * (wins + 0.5 * ties) / max(total, 1)


def range_vs_range(hero_range, villain_range, board, iterations: int = 1500,
                   rng=None) -> dict:
    """İki range'in board'da karşılıklı equity + nut avantajı.

    Döner: hero_equity, villain_equity, range_advantage ('hero'/'villain'/'eşit'),
    nut_hero %, nut_villain %, nut_advantage.
    """
    rng = rng or random
    board_c = parse_cards(board)
    hero_c = range_combos(hero_range, board_c)
    vill_c = range_combos(villain_range, board_c)
    if not hero_c or not vill_c:
        return {"hero_equity": 50.0, "villain_equity": 50.0,
                "range_advantage": "eşit", "nut_hero": 0.0, "nut_villain": 0.0,
                "nut_advantage": "eşit"}

    if len(board_c) >= 5:
        he = _river_equity(hero_c, vill_c, board_c)
    else:
        he = _mc_equity(hero_c, vill_c, board_c, board_c, iterations, rng)
    ve = round(100.0 - he, 1)
    he = round(he, 1)

    nut_h = round(_nut_fraction(hero_c, board_c), 1)
    nut_v = round(_nut_fraction(vill_c, board_c), 1)

    def _adv(a, b, tol):
        return "hero" if a > b + tol else ("villain" if b > a + tol else "eşit")

    return {
        "hero_equity": he, "villain_equity": ve,
        "range_advantage": _adv(he, ve, 1.5),
        "nut_hero": nut_h, "nut_villain": nut_v,
        "nut_advantage": _adv(nut_h, nut_v, 1.0),
    }


def coach_range_adv_line(r: dict) -> str:
    """range_vs_range çıktısını tek satır koç metnine çevir."""
    ra = {"hero": "SENDE", "villain": "VILLAIN'da", "eşit": "eşit"}[r["range_advantage"]]
    na = {"hero": "SENDE", "villain": "VILLAIN'da", "eşit": "eşit"}[r["nut_advantage"]]
    tip = ("ikisi de sende → küçük, yüksek-frekans range bet"
           if r["range_advantage"] == "hero" and r["nut_advantage"] == "hero"
           else "nut avantajı sende değil → yavaşla / polarize ol"
           if r["nut_advantage"] != "hero"
           else "range avantajı var ama nut dengeli → ölçülü bet")
    return (f"Range avantajı: {ra} (eq %{r['hero_equity']:.0f} vs %{r['villain_equity']:.0f}) · "
            f"Nut avantajı: {na} (set+ %{r['nut_hero']:.0f} vs %{r['nut_villain']:.0f}) → {tip}")
