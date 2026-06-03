"""Kombinatorik — elit koçun kalbi: 'tek el değil, COMBO say.'

River bluff-catch kararlarının çoğu, villain'ın range'indeki value vs bluff
combo SAYISINI ve hero'nun elinin hangilerini BLOKLADIĞINI saymakla çözülür.
Bu modül bunu yapar (dead-card duyarlı, gerçek el-değerlendiriciyle).

Saf fonksiyonlar (Qt/DB bağımsız). El sınıfı ('AA','AKs','AKo') → somut
combo'lara açılır, board'a karşı value/bluff'a ayrılır, blocker etkisi sayılır.
"""
from __future__ import annotations

from itertools import combinations
from typing import List, Tuple

from app.engine.hand_state import Card
from app.engine.evaluator import evaluate_best_hand, _compare_hands

_RANKS = "23456789TJQKA"
_SUITS = "cdhs"


# ── Kart ayrıştırma ──────────────────────────────────────────────────
def parse_cards(s) -> List[Card]:
    """'Ah Kd' / 'AhKd' / ['Ah','Kd'] → [Card, ...]. Geçersizleri atlar."""
    if isinstance(s, (list, tuple)):
        toks = [str(c) for c in s]
    else:
        cleaned = (str(s).replace("♠", "s").replace("♥", "h")
                   .replace("♦", "d").replace("♣", "c"))
        toks = cleaned.split()
        if len(toks) == 1:                       # 'AhKd7s' bitişik
            t = toks[0]
            toks = [t[i:i + 2] for i in range(0, len(t) - 1, 2)]
    out: List[Card] = []
    for t in toks:
        t = t.strip()
        if len(t) >= 2 and t[0].upper() in _RANKS and t[1].lower() in _SUITS:
            out.append(Card(t[0].upper(), t[1].lower()))
    return out


def _key(c: Card) -> str:
    return f"{c.rank}{c.suit}"


# ── El sınıfı → somut combo'lar (dead-card duyarlı) ─────────────────
def hand_class_combos(hc: str, dead: List[Card] | None = None) -> List[Tuple[Card, Card]]:
    """'AA'/'AKs'/'AKo' → ölü kartlar çıkarılmış somut 2-kart combo listesi."""
    dead_keys = {_key(c) for c in (dead or [])}
    hc = hc.strip()
    if len(hc) < 2:
        return []
    r1, r2 = hc[0].upper(), hc[1].upper()
    suited = hc.endswith("s")
    offsuit = hc.endswith("o")
    out: List[Tuple[Card, Card]] = []
    if r1 == r2:                                  # çift → C(4,2)=6
        cards = [Card(r1, s) for s in _SUITS if f"{r1}{s}" not in dead_keys]
        out = [(a, b) for a, b in combinations(cards, 2)]
    elif suited:                                  # 4 suited
        for s in _SUITS:
            a, b = Card(r1, s), Card(r2, s)
            if _key(a) not in dead_keys and _key(b) not in dead_keys:
                out.append((a, b))
    elif offsuit:                                 # 12 offsuit
        for s1 in _SUITS:
            for s2 in _SUITS:
                if s1 == s2:
                    continue
                a, b = Card(r1, s1), Card(r2, s2)
                if _key(a) not in dead_keys and _key(b) not in dead_keys:
                    out.append((a, b))
    else:                                         # belirtilmemiş → suited+offsuit
        out = (hand_class_combos(hc + "s", dead) + hand_class_combos(hc + "o", dead))
    return out


def range_combos(range_iter, dead: List[Card] | None = None) -> List[Tuple[Card, Card]]:
    """El-sınıfı kümesini somut combo listesine açar (dead-card duyarlı)."""
    out: List[Tuple[Card, Card]] = []
    for hc in range_iter:
        out.extend(hand_class_combos(str(hc), dead))
    return out


# ── Value / bluff ayrımı (hero'ya GÖRE — bluff-catch çerçevesi) ──────
def split_vs_hero(villain_combos, board: List[Card], hero: List[Card]) -> dict:
    """Her villain combo'sunu hero'ya karşı sınıfla: value (villain kazanır) /
    bluff (hero kazanır) / tie. River bluff-catch için doğru çerçeve."""
    hero_best = evaluate_best_hand(list(hero), list(board))
    value = bluff = tie = 0
    for c0, c1 in villain_combos:
        vb = evaluate_best_hand([c0, c1], list(board))
        cmp = _compare_hands(vb, hero_best)
        if cmp < 0:
            value += 1
        elif cmp > 0:
            bluff += 1
        else:
            tie += 1
    return {"value": value, "bluff": bluff, "tie": tie,
            "total": value + bluff + tie}


# ── Tam bluff-catch analizi (combo + blocker + pot odds) ────────────
def bluff_catch_analysis(hero, board, villain_range, pot: float,
                         to_call: float) -> dict:
    """Elit-koç combo analizi: villain range'inde value vs bluff combo sayısı,
    hero'nun blocker etkisi, pot-odds eşiği ve call verdict'i.

    villain_range: el-sınıfı kümesi (ör. {'AA','KK','AhKh',...} ya da
    gto range çıktısı). Döner: koça/UI'a hazır sözlük.
    """
    hero_c = parse_cards(hero)
    board_c = parse_cards(board)
    rng = list(villain_range or [])

    # Hero'nun kartları çıkarılmış (gerçek) split
    dead = board_c + hero_c
    combos = range_combos(rng, dead)
    real = split_vs_hero(combos, board_c, hero_c)

    # Blocker: hero kartları çıkarılMAdan (sadece board ölü) split
    full = split_vs_hero(range_combos(rng, board_c), board_c, hero_c)
    blocked_value = max(0, full["value"] - real["value"])
    blocked_bluff = max(0, full["bluff"] - real["bluff"])

    total = max(1, real["total"])
    # Hero'nun kazanma olasılığı ≈ (bluff + yarım tie) / toplam
    win_pct = 100.0 * (real["bluff"] + 0.5 * real["tie"]) / total
    needed_eq = 100.0 * to_call / max(pot + to_call, 1e-9)
    call_ok = win_pct >= needed_eq

    # Blocker verdict: value bloklamak call'a yarar, bluff bloklamak zarar
    if blocked_value > blocked_bluff:
        blocker_verdict = "iyi (value'larını blokluyorsun → call'a yarar)"
    elif blocked_bluff > blocked_value:
        blocker_verdict = "kötü (bluff'larını blokluyorsun → fold'a yarar)"
    else:
        blocker_verdict = "nötr"

    return {
        "value_combos": real["value"],
        "bluff_combos": real["bluff"],
        "tie_combos": real["tie"],
        "total_combos": real["total"],
        "win_pct": round(win_pct, 1),
        "needed_equity": round(needed_eq, 1),
        "call_ok": call_ok,
        "blocked_value": blocked_value,
        "blocked_bluff": blocked_bluff,
        "blocker_verdict": blocker_verdict,
    }


def coach_combo_line(analysis: dict) -> str:
    """bluff_catch_analysis çıktısını tek satır koç metnine çevir (reveal/koç)."""
    a = analysis
    verdict = "✓ CALL kârlı" if a["call_ok"] else "✗ FOLD (yeterli bluff yok)"
    return (
        f"Combo: {a['value_combos']} value / {a['bluff_combos']} bluff "
        f"(+{a['tie_combos']} tie) → kazanma ~%{a['win_pct']:.0f}, "
        f"gereken %{a['needed_equity']:.0f} → {verdict}. "
        f"Blocker: value −{a['blocked_value']} / bluff −{a['blocked_bluff']} "
        f"({a['blocker_verdict']})."
    )
