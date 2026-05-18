"""Preflop GTO chart database.

Her spot için deterministik, gerçek-solver-stiline yakın range haritaları.
Spot key formatı: `{POS}-{ACTION}-{STACK}-{VS?}` örnek:
  • "BTN-RFI-40"       — BTN 40bb open
  • "BB-DEF-40-vs-BTN" — BB savunması BTN açılışına karşı
  • "CO-3BET-40-vs-LJ" — CO'nun LJ open'ına 3bet defansı

`get_chart(key)` → `{"AKs": {"raise": 0.7, "fold": 0.3}, ...}` döner.
Bilinmeyen key için en yakın eşleşmeyi bulur (fallback ladder).
"""
from __future__ import annotations

from typing import Optional

_RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]


# ── helpers ───────────────────────────────────────────────────────────────

def _all_hands() -> list[str]:
    hands: list[str] = []
    for i, r1 in enumerate(_RANKS):
        for j, r2 in enumerate(_RANKS):
            if i == j:    hands.append(r1 + r2)
            elif i < j:   hands.append(r1 + r2 + "s")
            else:         hands.append(r2 + r1 + "o")
    return hands


_HANDS = _all_hands()


def _chart(
    strong: list[str],
    mixed: dict[str, float] | None = None,
    primary: str = "raise",
    secondary: str = "fold",
) -> dict[str, dict[str, float]]:
    """Build a chart. strong=100% primary; mixed=partial freq; rest=secondary."""
    mixed = mixed or {}
    result: dict[str, dict[str, float]] = {}
    for h in strong:
        result[h] = {primary: 1.0}
    for h, freq in mixed.items():
        result[h] = {primary: freq, secondary: 1.0 - freq}
    for h in _HANDS:
        if h not in result:
            result[h] = {secondary: 1.0}
    return result


# ── RFI charts (Raise First In) ───────────────────────────────────────────

# UTG RFI — tight (8-max)
_UTG_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77",
        "AKs","AQs","AJs","ATs","A5s","A4s",
        "KQs","KJs","KTs",
        "QJs","QTs",
        "JTs",
        "T9s","98s","87s","76s",
        "AKo","AQo",
    ],
    mixed={
        "66":0.8,"55":0.6,"44":0.3,
        "A9s":0.7,"A8s":0.6,"A7s":0.5,"A3s":0.4,"A2s":0.4,
        "K9s":0.5,"Q9s":0.4,"J9s":0.4,"T8s":0.4,"97s":0.3,"86s":0.3,"65s":0.4,
        "AJo":0.7,"KQo":0.6,
    },
)
_UTG_RFI_25 = _chart(  # tighter at 25bb
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77",
        "AKs","AQs","AJs","ATs",
        "KQs","KJs","KTs",
        "QJs","QTs","JTs",
        "AKo","AQo",
    ],
    mixed={
        "66":0.7,"55":0.4,
        "A9s":0.5,"A8s":0.4,"A5s":0.6,"A4s":0.4,
        "T9s":0.5,"98s":0.4,"87s":0.3,
        "AJo":0.6,"KQo":0.5,
    },
)

# LJ RFI
_LJ_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66",
        "AKs","AQs","AJs","ATs","A9s","A5s","A4s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","Q9s",
        "JTs","J9s",
        "T9s","98s","87s","76s","65s",
        "AKo","AQo","AJo","KQo",
    ],
    mixed={
        "55":0.7,"44":0.4,"33":0.2,"22":0.2,
        "A8s":0.7,"A7s":0.6,"A6s":0.5,"A3s":0.5,"A2s":0.4,
        "K8s":0.4,"Q8s":0.3,"J8s":0.3,"T8s":0.4,
        "97s":0.4,"86s":0.3,"54s":0.4,
        "ATo":0.6,"KJo":0.5,"QJo":0.4,
    },
)
_LJ_RFI_25 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66",
        "AKs","AQs","AJs","ATs","A9s","A5s",
        "KQs","KJs","KTs",
        "QJs","QTs","JTs",
        "T9s","98s","87s",
        "AKo","AQo","AJo","KQo",
    ],
    mixed={
        "55":0.6,"44":0.3,
        "A8s":0.5,"A7s":0.4,"A4s":0.4,
        "K9s":0.6,"Q9s":0.4,"J9s":0.4,
        "76s":0.4,"65s":0.3,
        "ATo":0.5,"KJo":0.4,
    },
)

# HJ RFI
_HJ_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55",
        "AKs","AQs","AJs","ATs","A9s","A8s","A5s","A4s","A3s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","Q8s",
        "JTs","J9s","J8s",
        "T9s","T8s",
        "98s","97s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","KQo","KJo",
    ],
    mixed={
        "44":0.7,"33":0.4,"22":0.4,
        "A7s":0.7,"A6s":0.6,"A2s":0.5,
        "K7s":0.4,"Q7s":0.3,"J7s":0.3,"T7s":0.3,
        "86s":0.4,"75s":0.3,"64s":0.3,"53s":0.3,"43s":0.3,
        "KTo":0.7,"QJo":0.6,"JTo":0.5,
    },
)

# CO RFI — wider
_CO_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s",
        "QJs","QTs","Q9s","Q8s","Q7s",
        "JTs","J9s","J8s","J7s",
        "T9s","T8s","T7s",
        "98s","97s","87s","86s","76s","75s","65s","54s",
        "AKo","AQo","AJo","ATo","KQo","KJo","KTo","QJo","QTo","JTo",
    ],
    mixed={
        "33":0.8,"22":0.7,
        "K5s":0.7,"K4s":0.5,"K3s":0.4,"K2s":0.3,
        "Q6s":0.6,"Q5s":0.5,"Q4s":0.4,
        "J6s":0.4,"T6s":0.3,
        "96s":0.4,"85s":0.4,"74s":0.4,"64s":0.4,"53s":0.4,"43s":0.4,
        "A9o":0.7,"K9o":0.5,"Q9o":0.4,"J9o":0.4,"T9o":0.4,
    },
)

# BTN RFI — widest
_BTN_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s",
        "JTs","J9s","J8s","J7s","J6s",
        "T9s","T8s","T7s","T6s",
        "98s","97s","96s","87s","86s","85s","76s","75s","65s","64s","54s","53s","43s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o",
        "KQo","KJo","KTo","K9o","K8o",
        "QJo","QTo","Q9o","Q8o",
        "JTo","J9o","J8o",
        "T9o","T8o","98o","87o",
    ],
    mixed={
        "Q4s":0.7,"Q3s":0.5,"Q2s":0.4,
        "T5s":0.4,"95s":0.4,"84s":0.4,"74s":0.4,"63s":0.4,"52s":0.4,"42s":0.3,"32s":0.3,
        "A6o":0.7,"A5o":0.6,"A4o":0.5,"A3o":0.5,"A2o":0.4,
        "K7o":0.5,"K6o":0.4,"K5o":0.3,
        "Q7o":0.4,"J7o":0.4,"T7o":0.4,
        "97o":0.4,"86o":0.4,"76o":0.4,"65o":0.4,
    },
)
_BTN_RFI_25 = _chart(  # tighter shove-or-fold-ish
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s",
        "JTs","J9s","J8s","J7s",
        "T9s","T8s","T7s","98s","97s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","A8o",
        "KQo","KJo","KTo","K9o",
        "QJo","QTo","JTo","T9o",
    ],
    mixed={
        "Q5s":0.6,"Q4s":0.4,
        "J6s":0.5,"T6s":0.4,"96s":0.4,"86s":0.4,"75s":0.4,"64s":0.3,"53s":0.4,"43s":0.3,
        "A7o":0.7,"A6o":0.5,"A5o":0.5,"K8o":0.5,"K7o":0.4,
        "Q9o":0.5,"J9o":0.5,"98o":0.4,"87o":0.3,
    },
)

# SB RFI — limp + raise mix (limit to raise-only here for sim)
_SB_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s",
        "QJs","QTs","Q9s","Q8s",
        "JTs","J9s","J8s",
        "T9s","T8s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o",
        "KQo","KJo","KTo",
        "QJo","QTo","JTo",
    ],
    mixed={
        "55":0.7,"44":0.5,"33":0.4,"22":0.4,
        "K6s":0.5,"K5s":0.4,"Q7s":0.4,"J7s":0.4,"T7s":0.3,"97s":0.3,
        "A8o":0.6,"A7o":0.5,
        "K9o":0.5,"Q9o":0.4,"J9o":0.4,
        "98o":0.3,"87o":0.3,
    },
)


# ── BB defense vs RFI (call + 3-bet + fold mix) ───────────────────────────

def _bb_def(value_3bets: list[str], bluff_3bets: dict[str, float],
            calls: list[str], call_mixed: dict[str, float] | None = None,
            ) -> dict[str, dict[str, float]]:
    """3 actions: 3bet (value/bluff) / call / fold."""
    call_mixed = call_mixed or {}
    result: dict[str, dict[str, float]] = {}
    for h in value_3bets:
        result[h] = {"3bet": 1.0}
    for h, freq in bluff_3bets.items():
        result[h] = {"3bet": freq, "call": 1.0 - freq}
    for h in calls:
        if h not in result:
            result[h] = {"call": 1.0}
    for h, freq in call_mixed.items():
        if h not in result:
            result[h] = {"call": freq, "fold": 1.0 - freq}
    for h in _HANDS:
        if h not in result:
            result[h] = {"fold": 1.0}
    return result


_BB_DEF_vs_BTN_40 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo","AQs"],
    bluff_3bets={
        "TT":0.3,"99":0.2,
        "A5s":0.6,"A4s":0.5,"A3s":0.4,"A2s":0.3,
        "K5s":0.4,"K4s":0.3,
        "76s":0.3,"65s":0.3,"54s":0.4,
        "AQo":0.4,"KQs":0.4,
    },
    calls=[
        "99","88","77","66","55","44","33","22",
        "AJs","ATs","A9s","A8s","A7s","A6s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s","Q4s",
        "JTs","J9s","J8s","J7s","J6s",
        "T9s","T8s","T7s","T6s",
        "98s","97s","96s","87s","86s","75s","74s","64s","53s","43s",
        "AQo","AJo","ATo","A9o","A8o","A7o",
        "KQo","KJo","KTo","K9o","K8o",
        "QJo","QTo","Q9o","JTo","J9o","T9o","T8o","98o","87o","76o",
    ],
    call_mixed={
        "A6o":0.6,"A5o":0.5,"A4o":0.4,"A3o":0.4,"A2o":0.3,
        "K7o":0.6,"K6o":0.4,"Q8o":0.5,"J8o":0.5,"T7o":0.4,
        "97o":0.4,"86o":0.3,"65o":0.3,"54o":0.3,
    },
)

_BB_DEF_vs_BTN_25 = _bb_def(  # tighter call wider 3bet shove range
    value_3bets=["AA","KK","QQ","JJ","TT","AKs","AKo","AQs","AQo"],
    bluff_3bets={
        "A5s":0.5,"A4s":0.4,"A3s":0.3,
        "76s":0.3,"65s":0.4,"54s":0.4,
    },
    calls=[
        "99","88","77","66","55","44","33","22",
        "AJs","ATs","A9s","A8s","A7s","A6s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s",
        "AJo","ATo","KQo","KJo","KTo","QJo","JTo",
    ],
)

_BB_DEF_vs_LJ_40 = _bb_def(  # vs early position — tighter, more 3bet
    value_3bets=["AA","KK","QQ","JJ","TT","AKs","AKo","AQs"],
    bluff_3bets={
        "A5s":0.6,"A4s":0.4,
        "76s":0.2,"65s":0.2,
    },
    calls=[
        "99","88","77","66","55","44","33","22",
        "AJs","ATs","A9s","A8s","A7s","A6s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s",
        "AQo","AJo","ATo","KQo","KJo","QJo","JTo",
    ],
)

_BB_DEF_vs_CO_40 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo","AQs"],
    bluff_3bets={
        "TT":0.4,
        "A5s":0.6,"A4s":0.5,"A3s":0.4,
        "K4s":0.4,"K3s":0.3,
        "76s":0.3,"65s":0.4,"54s":0.4,
        "KQs":0.3,
    },
    calls=[
        "99","88","77","66","55","44","33","22",
        "AJs","ATs","A9s","A8s","A7s","A6s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s",
        "JTs","J9s","J8s","J7s",
        "T9s","T8s","T7s","98s","97s","87s","86s","75s","64s","53s","43s",
        "AQo","AJo","ATo","A9o","KQo","KJo","KTo","K9o",
        "QJo","QTo","Q9o","JTo","J9o","T9o","98o","87o",
    ],
)


# ── SB defense vs BTN RFI (3bet-heavy because BB will squeeze) ────────────

_SB_DEF_vs_BTN_40 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","TT","99","AKs","AKo","AQs","AQo","AJs","KQs"],
    bluff_3bets={
        "A5s":0.7,"A4s":0.5,"A3s":0.4,
        "K5s":0.4,"K4s":0.3,
        "76s":0.3,"65s":0.4,"54s":0.4,
        "AJo":0.4,"KQo":0.3,
    },
    calls=[
        "88","77","66","55","44","33","22",
        "ATs","A9s","A8s","A7s","A2s",
        "KJs","KTs","K9s","K8s","K7s","K6s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s",
        "JTs","J9s","J8s","J7s",
        "T9s","T8s","T7s","98s","97s","87s","86s",
    ],
)


# ── 3-bet defense (opener vs 3-bet) — 4bet / call / fold ─────────────────

def _vs_3bet(value_4bets: list[str], bluff_4bets: dict[str, float],
             calls: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for h in value_4bets:
        result[h] = {"4bet": 1.0}
    for h, freq in bluff_4bets.items():
        result[h] = {"4bet": freq, "fold": 1.0 - freq}
    for h in calls:
        if h not in result:
            result[h] = {"call": 1.0}
    for h in _HANDS:
        if h not in result:
            result[h] = {"fold": 1.0}
    return result


_BTN_vs_BB_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo"],
    bluff_4bets={
        "A5s":0.7,"A4s":0.5,
    },
    calls=[
        "JJ","TT","99","88","77","66",
        "AQs","AJs","ATs","A9s","KQs","KJs","KTs","QJs","QTs","JTs",
        "AQo","AJo","KQo",
    ],
)

# More 3-bet defense charts — opener faces a 3-bet
_UTG_vs_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo","JJ"],
    bluff_4bets={"A5s":0.4, "A4s":0.3},
    calls=["TT","99","88","77","AQs","AJs","ATs","KQs","KJs","QJs","JTs"],
)
_LJ_vs_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo","JJ"],
    bluff_4bets={"A5s":0.5,"A4s":0.4,"KQs":0.3},
    calls=["TT","99","88","77","66","AQs","AJs","ATs","A9s","KQs","KJs","KTs","QJs","QTs","JTs","AQo"],
)
_HJ_vs_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo","JJ"],
    bluff_4bets={"A5s":0.55,"A4s":0.4},
    calls=["TT","99","88","77","66","55","AQs","AJs","ATs","A9s","A8s",
           "KQs","KJs","KTs","K9s","QJs","QTs","JTs","T9s","98s","87s","AQo","AJo","KQo"],
)
_CO_vs_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo","JJ"],
    bluff_4bets={"A5s":0.6,"A4s":0.5,"A3s":0.3,"KQs":0.2},
    calls=["TT","99","88","77","66","55","44",
           "AQs","AJs","ATs","A9s","A8s","A7s",
           "KQs","KJs","KTs","K9s","K8s","QJs","QTs","Q9s","JTs","J9s","T9s","T8s","98s","87s","76s",
           "AQo","AJo","ATo","KQo","KJo","QJo"],
)
_CO_vs_BTN_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo"],
    bluff_4bets={"A5s":0.6,"A4s":0.4,"K5s":0.3},
    calls=["JJ","TT","99","88","77","66","AQs","AJs","ATs","A9s",
           "KQs","KJs","KTs","QJs","QTs","JTs","T9s","98s",
           "AQo","AJo","KQo"],
)
_BTN_vs_CO_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","AKs","AKo"],
    bluff_4bets={"A5s":0.65,"A4s":0.5,"A3s":0.3},
    calls=["JJ","TT","99","88","77","66","55",
           "AQs","AJs","ATs","A9s","A8s","KQs","KJs","KTs","K9s",
           "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s",
           "AQo","AJo","ATo","KQo","KJo"],
)
_SB_vs_BTN_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","JJ","AKs","AKo"],
    bluff_4bets={"A5s":0.55,"A4s":0.4},
    calls=["TT","99","88","77","66","AQs","AJs","ATs","A9s","KQs","KJs","KTs","QJs","QTs","JTs","AQo","KQo"],
)
_BB_vs_SB_3BET_40 = _vs_3bet(
    value_4bets=["AA","KK","QQ","JJ","AKs","AKo"],
    bluff_4bets={"A5s":0.5,"KQs":0.3},
    calls=["TT","99","88","77","66","55","AQs","AJs","ATs","KQs","KJs","KTs","QJs","QTs","JTs","AQo"],
)

# 4-bet defense — facing a 4-bet (jam / call / fold)
def _vs_4bet(value_jams: list[str], call_4bet: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for h in value_jams:
        result[h] = {"jam": 1.0}
    for h in call_4bet:
        if h not in result:
            result[h] = {"call": 1.0}
    for h in _HANDS:
        if h not in result:
            result[h] = {"fold": 1.0}
    return result

_BTN_vs_BB_4BET_40 = _vs_4bet(
    value_jams=["AA","KK","QQ","AKs","AKo"],
    call_4bet=["JJ","TT","AQs","AJs"],
)

# BB squeeze ranges (3-bet from BB after open + caller)
_BB_SQUEEZE_vs_BTN_40 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo","AQs"],
    bluff_3bets={"A5s":0.7,"A4s":0.6,"A3s":0.4,"K9s":0.3,"Q9s":0.3},
    calls=["TT","99","88","77","66","55","44",
           "AQo","AJs","ATs","A9s","A8s","A7s","A6s","A2s",
           "KQs","KJs","KTs","K8s","QJs","QTs","Q8s","JTs","J9s",
           "T9s","T8s","98s","87s","76s","65s","54s",
           "AJo","ATo","KQo","KJo","QJo","JTo"],
)

# Deep-stack opens (100bb+) — wider cash-game style
_LJ_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A5s","A4s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","KQo","KJo","QJo",
    ],
    mixed={"33":0.6,"22":0.4,"A6s":0.7,"K7s":0.4,"Q8s":0.4,"J8s":0.4,
           "T8s":0.4,"97s":0.3,"86s":0.3,"KTo":0.5,"QTo":0.4},
)
_HJ_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s",
        "QJs","QTs","Q9s","Q8s","JTs","J9s","J8s","T9s","T8s",
        "98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","KTo","QJo","QTo","JTo",
    ],
    mixed={"22":0.5,"K6s":0.5,"K5s":0.3,"Q7s":0.3,"J7s":0.3,"97s":0.4,"86s":0.4,"75s":0.3},
)
_SB_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s",
        "QJs","QTs","Q9s","Q8s","Q7s",
        "JTs","J9s","J8s","T9s","T8s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","A8o","KQo","KJo","KTo","K9o","QJo","QTo","Q9o","JTo","J9o","T9o","98o",
    ],
    mixed={"K4s":0.4,"Q6s":0.3,"J7s":0.3,"T7s":0.3,"97s":0.4,"86s":0.4,
           "76o":0.3,"87o":0.3,"A7o":0.5,"K8o":0.4},
)
_BB_DEF_100_vs_BTN = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo","AQs"],
    bluff_3bets={"A5s":0.7,"A4s":0.6,"A3s":0.5,"K9s":0.3,"Q9s":0.3,
                 "76s":0.2,"65s":0.2},
    calls=["TT","99","88","77","66","55","44","33","22",
           "AQo","AJs","ATs","A9s","A8s","A7s","A6s","A2s",
           "KQs","KJs","KTs","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
           "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s",
           "JTs","J9s","J8s","J7s","T9s","T8s","T7s","98s","97s","87s","86s","75s","65s","54s","43s",
           "AJo","ATo","A9o","A8o","A7o","KQo","KJo","KTo","K9o","QJo","QTo","Q9o","JTo","J9o","T9o","98o","87o","76o"],
)

# More shove ranges for short-stack tournaments
_CO_SHOVE_15 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","QJo",
    ],
    primary="jam", secondary="fold",
    mixed={"33":0.7,"22":0.5,"K7s":0.5,"Q8s":0.4,"KTo":0.6,"QTo":0.4},
)
_BTN_SHOVE_15 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s",
        "QJs","QTs","Q9s","Q8s","JTs","J9s","J8s","T9s","T8s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o","KQo","KJo","KTo","K9o","QJo","QTo","JTo",
    ],
    primary="jam", secondary="fold",
    mixed={"K3s":0.5,"Q7s":0.4,"J7s":0.4,"T7s":0.4,"97s":0.4,"86s":0.4,
           "A6o":0.6,"K8o":0.5,"Q9o":0.5,"J9o":0.4,"T9o":0.3},
)
_UTG_SHOVE_10 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","QJo",
    ],
    primary="jam", secondary="fold",
    mixed={"A8o":0.6,"KTo":0.5,"QTo":0.4,"JTo":0.3},
)
_BB_CALL_SHOVE_15 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s",
        "KQs","KJs","KTs","K9s","QJs","QTs","JTs","T9s","98s",
        "AKo","AQo","AJo","ATo","KQo","KJo","QJo",
    ],
    primary="call", secondary="fold",
    mixed={"44":0.6,"33":0.4,"A3s":0.7,"K8s":0.5,"Q9s":0.6,"J9s":0.5,
           "A9o":0.7,"KTo":0.6,"QTo":0.4},
)


# ── chart registry ────────────────────────────────────────────────────────

# ── Expanded chart library (Faz 5 — solver coverage) ────────────────────

# HJ RFI 25bb — tighter than 40bb
_HJ_RFI_25 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77",
        "AKs","AQs","AJs","ATs","A9s","A5s","A4s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","JTs","T9s","98s","87s",
        "AKo","AQo","AJo","KQo",
    ],
    mixed={
        "66":0.7,"55":0.4,"44":0.2,
        "A8s":0.5,"A7s":0.4,"A3s":0.3,
        "Q9s":0.4,"J9s":0.4,"76s":0.4,"65s":0.3,
        "ATo":0.5,"KJo":0.4,
    },
)

# CO RFI 25bb
_CO_RFI_25 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","T8s","98s","87s","76s","65s",
        "AKo","AQo","AJo","ATo","KQo","KJo","QJo",
    ],
    mixed={
        "44":0.5,"33":0.3,"22":0.2,
        "K7s":0.4,"Q8s":0.4,"J8s":0.3,"97s":0.3,"54s":0.3,
        "KTo":0.5,"QTo":0.4,
    },
)

# SB RFI 25bb — looser than 40bb (push/raise mix not modelled here, treated as raise)
_SB_RFI_25 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","QJo",
    ],
    mixed={
        "44":0.6,"33":0.4,"22":0.3,
        "A6s":0.6,
        "K7s":0.4,"K6s":0.3,"Q8s":0.4,
        "65s":0.4,"54s":0.3,
        "KTo":0.5,"QTo":0.4,"JTo":0.3,
    },
)

# BB DEF 25bb vs CO open — tighter than 40bb
_BB_DEF_vs_CO_25 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo","AQs"],
    bluff_3bets={"A5s":0.5,"A4s":0.4,"KJs":0.3,"QJs":0.3},
    calls=[
        "TT","99","88","77","66","55","44","33","22",
        "AQo","AJs","ATs","A9s","A8s","A7s","A6s","A3s","A2s",
        "KQs","KQo","KJs","KJo","KTs","K9s",
        "QJs","QTs","QJo","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AJo","ATo","A9o","KTo","QTo","JTo",
    ],
)

# BB DEF 25bb vs LJ — tighter range
_BB_DEF_vs_LJ_25 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","AKs","AKo"],
    bluff_3bets={"A5s":0.3,"A4s":0.2,"KQs":0.2},
    calls=[
        "TT","99","88","77","66","55","44","33",
        "AQo","AQs","AJs","ATs","A9s","A8s","A7s","A5s",
        "KQs","KJs","KTs","KQo",
        "QJs","QTs","JTs","T9s","98s","87s","76s","65s",
        "AJo","KJo","QJo","JTo",
    ],
)


# 100bb deep stack — cash-game-like ranges
_UTG_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44",
        "AKs","AQs","AJs","ATs","A5s","A4s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","KQo",
    ],
    mixed={"33":0.7, "22":0.5, "A9s":0.8, "K8s":0.4, "T8s":0.4, "ATo":0.6, "KJo":0.5},
)
_BTN_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s",
        "JTs","J9s","J8s","J7s","T9s","T8s","T7s","98s","97s","87s","86s",
        "76s","75s","65s","64s","54s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o",
        "KQo","KJo","KTo","K9o","QJo","QTo","Q9o","JTo","J9o","T9o","98o","87o",
    ],
)
# BB DEF 40bb vs MP-style opener (treated like LJ-CO blend)
_BB_DEF_vs_MP_40 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","TT","AKs","AKo","AQs"],
    bluff_3bets={"A5s":0.6,"A4s":0.5,"KJs":0.3,"QJs":0.4,"K9s":0.3},
    calls=[
        "99","88","77","66","55","44","33","22",
        "AQo","AJs","ATs","A9s","A8s","A7s","A6s","A3s","A2s",
        "KQs","KQo","KJs","KJo","KTs","K9s","K8s",
        "QJs","QTs","Q9s","QJo","JTs","J9s","J8s","T9s","T8s",
        "98s","87s","76s","65s","54s",
        "AJo","ATo","A9o","KTo","QTo","JTo",
    ],
)
# SB DEF 25bb vs BTN
_SB_DEF_vs_BTN_25 = _bb_def(
    value_3bets=["AA","KK","QQ","JJ","TT","AKs","AKo","AQs","AQo"],
    bluff_3bets={"A5s":0.5,"A4s":0.4,"KJs":0.3,"QJs":0.3},
    calls=[
        "99","88","77","66","55","44",
        "AJs","ATs","A9s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AJo","KQo","KJo","QJo","JTo",
    ],
)
# Aggregate 'cash 100bb deep' shortcut for hands shorter than 40bb logic
_CO_RFI_100 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s",
        "QJs","QTs","Q9s","Q8s","JTs","J9s","J8s",
        "T9s","T8s","98s","97s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","KTo","QJo","QTo","JTo",
    ],
    mixed={"A8o":0.5, "K9o":0.5, "Q9o":0.4, "J9o":0.4, "T9o":0.3, "98o":0.3, "76o":0.2},
)


# Short-stack shove ranges (15bb push) — MTT bubble dynamics
_UTG_SHOVE_15 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66",
        "AKs","AQs","AJs","ATs","A9s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","JTs","T9s","98s","87s",
        "AKo","AQo","AJo","KQo",
    ],
    primary="jam", secondary="fold",
    mixed={"55":0.8, "44":0.5, "33":0.3, "ATo":0.4, "KJo":0.3},
)
_BTN_SHOVE_10 = _chart(   # very short — wide BTN push
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
        "QJs","QTs","Q9s","Q8s","Q7s","JTs","J9s","J8s","T9s","T8s","98s","87s","76s","65s",
        "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","A3o","A2o",
        "KQo","KJo","KTo","K9o","QJo","QTo","Q9o","JTo","J9o","T9o","98o","87o",
    ],
    primary="jam", secondary="fold",
)
_SB_SHOVE_15 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","K8s",
        "QJs","QTs","Q9s","JTs","J9s","T9s","98s","87s","76s","65s","54s",
        "AKo","AQo","AJo","ATo","A9o","A8o","KQo","KJo","KTo","QJo","QTo","JTo",
    ],
    primary="jam", secondary="fold",
    mixed={"K7s":0.6, "Q8s":0.5, "J8s":0.5, "T8s":0.5, "97s":0.4,
           "A7o":0.7, "K9o":0.6, "Q9o":0.5},
)

# BB call-vs-shove ranges
_BB_CALL_VS_SHOVE_10 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
        "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
        "KQs","KJs","KTs","K9s","QJs","QTs","JTs","T9s","98s","87s","76s",
        "AKo","AQo","AJo","ATo","A9o","KQo","KJo","QJo",
    ],
    primary="call", secondary="fold",
    mixed={"K8s":0.6, "K7s":0.4, "Q9s":0.5, "J9s":0.5,
           "ATo":0.7, "A8o":0.5, "KTo":0.6},
)

# 6-max MP and EP — pre-solved
_MP_RFI_40 = _chart(
    strong=[
        "AA","KK","QQ","JJ","TT","99","88","77","66",
        "AKs","AQs","AJs","ATs","A9s","A5s","A4s",
        "KQs","KJs","KTs","K9s",
        "QJs","QTs","JTs","T9s","98s","87s","76s",
        "AKo","AQo","AJo","KQo",
    ],
    mixed={"55":0.8, "44":0.5, "A8s":0.6, "A7s":0.5, "Q9s":0.5, "J9s":0.4,
           "65s":0.4, "ATo":0.7, "KJo":0.5},
)


CHARTS: dict[str, dict[str, dict[str, float]]] = {
    "UTG-RFI-40":      _UTG_RFI_40,
    "UTG-RFI-25":      _UTG_RFI_25,
    "UTG-RFI-100":     _UTG_RFI_100,
    "LJ-RFI-40":       _LJ_RFI_40,
    "LJ-RFI-25":       _LJ_RFI_25,
    "HJ-RFI-40":       _HJ_RFI_40,
    "HJ-RFI-25":       _HJ_RFI_25,
    "CO-RFI-40":       _CO_RFI_40,
    "CO-RFI-25":       _CO_RFI_25,
    "CO-RFI-100":      _CO_RFI_100,
    "BTN-RFI-40":      _BTN_RFI_40,
    "BTN-RFI-25":      _BTN_RFI_25,
    "BTN-RFI-100":     _BTN_RFI_100,
    "SB-RFI-40":       _SB_RFI_40,
    "SB-RFI-25":       _SB_RFI_25,
    "BB-DEF-40-vs-BTN":_BB_DEF_vs_BTN_40,
    "BB-DEF-25-vs-BTN":_BB_DEF_vs_BTN_25,
    "BB-DEF-40-vs-LJ": _BB_DEF_vs_LJ_40,
    "BB-DEF-25-vs-LJ": _BB_DEF_vs_LJ_25,
    "BB-DEF-40-vs-CO": _BB_DEF_vs_CO_40,
    "BB-DEF-25-vs-CO": _BB_DEF_vs_CO_25,
    "BB-DEF-40-vs-MP": _BB_DEF_vs_MP_40,
    "SB-DEF-40-vs-BTN":_SB_DEF_vs_BTN_40,
    "SB-DEF-25-vs-BTN":_SB_DEF_vs_BTN_25,
    "BTN-vsBB3BET-40": _BTN_vs_BB_3BET_40,
    # 3-bet defense (opener facing 3-bet)
    "UTG-vs3BET-40":   _UTG_vs_3BET_40,
    "LJ-vs3BET-40":    _LJ_vs_3BET_40,
    "HJ-vs3BET-40":    _HJ_vs_3BET_40,
    "CO-vs3BET-40":    _CO_vs_3BET_40,
    "CO-vsBTN3BET-40": _CO_vs_BTN_3BET_40,
    "BTN-vsCO3BET-40": _BTN_vs_CO_3BET_40,
    "SB-vsBTN3BET-40": _SB_vs_BTN_3BET_40,
    "BB-vsSB3BET-40":  _BB_vs_SB_3BET_40,
    # 4-bet defense
    "BTN-vsBB4BET-40": _BTN_vs_BB_4BET_40,
    # BB squeeze (3-bet vs open + caller)
    "BB-SQUEEZE-vs-BTN-40": _BB_SQUEEZE_vs_BTN_40,
    # Deep stack 100bb
    "LJ-RFI-100":      _LJ_RFI_100,
    "HJ-RFI-100":      _HJ_RFI_100,
    "SB-RFI-100":      _SB_RFI_100,
    "BB-DEF-100-vs-BTN":_BB_DEF_100_vs_BTN,
    # Short stacks — shove/fold dynamics
    "UTG-SHOVE-15":    _UTG_SHOVE_15,
    "UTG-SHOVE-10":    _UTG_SHOVE_10,
    "CO-SHOVE-15":     _CO_SHOVE_15,
    "BTN-SHOVE-15":    _BTN_SHOVE_15,
    "BTN-SHOVE-10":    _BTN_SHOVE_10,
    "SB-SHOVE-15":     _SB_SHOVE_15,
    "BB-CALL-SHOVE-10":_BB_CALL_VS_SHOVE_10,
    "BB-CALL-SHOVE-15":_BB_CALL_SHOVE_15,
    # MP for 6-max / 9-max
    "MP-RFI-40":       _MP_RFI_40,
}


def get_chart(key: str) -> Optional[dict[str, dict[str, float]]]:
    return CHARTS.get(key)


def chart_for_spot(spot: dict) -> dict[str, dict[str, float]]:
    """Return the best matching chart for a given spot dict."""
    pos    = (spot.get("position") or "BTN").upper().replace("UTG+1", "UTG")
    try:
        stack = int(float(spot.get("stack_bb") or 40))
    except (ValueError, TypeError):
        stack = 40
    # Stack bucket — 10/15 shove, 25 short, 40 mid, 100 deep
    if stack <= 12:   bucket = 10
    elif stack <= 18: bucket = 15
    elif stack <= 30: bucket = 25
    elif stack <= 70: bucket = 40
    else:             bucket = 100
    name   = (spot.get("name", "") + " " + spot.get("title", "") + " " + spot.get("action_history", "")).lower()

    # Detect "vs X" patterns
    vs = None
    for v in ("btn", "lj", "co", "bb", "sb", "hj", "mp"):
        if f"vs {v}" in name or f"vs {v.upper()}" in name.upper():
            vs = v.upper(); break

    pot = (spot.get("pot_type") or "").upper()

    # Try most specific to least specific
    keys_to_try = []
    # Squeeze
    if "squeeze" in name or "sqz" in name:
        keys_to_try.append(f"BB-SQUEEZE-vs-{vs or 'BTN'}-{bucket}")
        keys_to_try.append("BB-SQUEEZE-vs-BTN-40")
    # 4-bet pot defense
    if pot == "4BP" or "4-bet" in name or "4bet" in name:
        keys_to_try.append(f"{pos}-vs{vs or 'BB'}4BET-{bucket}")
        keys_to_try.append("BTN-vsBB4BET-40")
    # Shove spots (≤ 15bb)
    if stack <= 18:
        keys_to_try.append(f"{pos}-SHOVE-{bucket}")
        if pos == "BB" and vs:
            keys_to_try.append(f"BB-CALL-SHOVE-{bucket}")
    # BB defense
    if pos == "BB":
        if vs:
            keys_to_try.append(f"BB-DEF-{bucket}-vs-{vs}")
        keys_to_try += [f"BB-DEF-{bucket}-vs-BTN", "BB-DEF-40-vs-BTN", "BB-DEF-100-vs-BTN"]
    # SB defense
    elif pos == "SB" and vs == "BTN":
        keys_to_try += [f"SB-DEF-{bucket}-vs-BTN", "SB-DEF-40-vs-BTN"]
    else:
        # 3BP — defending the open vs a 3-bet
        if "3BP" in pot or "3-bet" in name:
            keys_to_try.append(f"{pos}-vs{vs or 'BB'}3BET-{bucket}")
            keys_to_try.append(f"{pos}-vs3BET-{bucket}")
            keys_to_try += ["BTN-vsBB3BET-40", "CO-vsBTN3BET-40"]
        # RFI fallback
        keys_to_try += [f"{pos}-RFI-{bucket}", f"{pos}-RFI-40", f"{pos}-RFI-100"]

    # Final fallback ladder
    keys_to_try += ["BTN-RFI-40", "CO-RFI-40", "LJ-RFI-40"]

    for k in keys_to_try:
        if k in CHARTS:
            return CHARTS[k]
    return _BTN_RFI_40


def aggregate_strategy(chart: dict[str, dict[str, float]]) -> dict[str, float]:
    """Sum frequencies across all 169 hands → action → average freq."""
    totals: dict[str, float] = {}
    count = 0
    for h, strat in chart.items():
        for action, freq in strat.items():
            totals[action] = totals.get(action, 0.0) + freq
        count += 1
    if count == 0:
        return {}
    return {a: round(v / count, 4) for a, v in totals.items()}


def strategy_for_hand(chart: dict[str, dict[str, float]], hand_169: str) -> dict[str, float]:
    """Return the strategy for a specific 169-style hand label like 'AKs'."""
    return chart.get(hand_169, {"fold": 1.0})


def hand_169_from_cards(hero_cards: str) -> Optional[str]:
    """'AsKh' or 'A♠K♥' → 'AKs'/'AKo'."""
    if not hero_cards or len(hero_cards) < 2:
        return None
    suit_chars = {"h", "d", "s", "c", "♥", "♦", "♠", "♣"}
    ranks = []
    suits = []
    i = 0
    while i < len(hero_cards):
        ch = hero_cards[i]
        if ch in _RANKS and len(ranks) < 2:
            ranks.append(ch)
            if i + 1 < len(hero_cards) and hero_cards[i+1] in suit_chars:
                suits.append(hero_cards[i+1])
                i += 1
        i += 1
    if len(ranks) < 2:
        return None
    r1, r2 = ranks[0], ranks[1]
    if r1 == r2:
        return r1 + r2
    if _RANKS.index(r1) > _RANKS.index(r2):
        r1, r2 = r2, r1
        if len(suits) >= 2:
            suits = [suits[1], suits[0]]
    suited = (len(suits) >= 2 and suits[0] == suits[1])
    return r1 + r2 + ("s" if suited else "o")
