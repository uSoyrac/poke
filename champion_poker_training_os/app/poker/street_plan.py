"""Çok-sokaklı plan — elit koç: 'iyi oyun izole karar değil, ÇOK-SOKAKLI PLAN.'

Flop/turn'de el sınıfına + board dokusuna göre: kaç sokak value/barrel, hangi
kartlar devam eder, hangileri (scare) yavaşlatır. Size plandan çıkar. Saf
(Qt/DB bağımsız), heuristik (CONCEPT — yön/şekil doğru, solver-exact değil).
"""
from __future__ import annotations

from typing import List, Tuple

from app.engine.hand_state import Card
from app.engine.evaluator import evaluate_best_hand
from app.poker.combinatorics import parse_cards

_RANKS = "23456789TJQKA"


def _rv(r: str) -> int:
    return _RANKS.index(r)


def _draws(hero: List[Card], board: List[Card]) -> Tuple[float, List[str]]:
    """Hero'nun draw equity tahmini (0..1) + etiketler. Flush draw / OESD /
    gutshot. Kabaca (Rule of 2&4 sezgisi); CONCEPT."""
    cards = hero + board
    labels: List[str] = []
    eq = 0.0
    # Flush draw: bir suit'ten tam 4 (hero en az 1 katkı)
    for s in "cdhs":
        suited = [c for c in cards if c.suit == s]
        if len(suited) == 4 and any(c.suit == s for c in hero):
            eq = max(eq, 0.35); labels.append("flush draw")
    # Düz (straight) draw: ardışıklık penceresi
    vals = sorted({_rv(c.rank) for c in cards})
    # wheel için A'yı 0 gibi de değerlendir
    if _rv("A") in vals:
        vals = sorted(set(vals + [-1]))
    best_run = 0
    for v in vals:
        run = 1
        while (v + run) in vals:
            run += 1
        best_run = max(best_run, run)
    # 4-ardışık → OESD/gutshot ayrımı kabaca
    if best_run >= 4:
        eq = max(eq, 0.32); labels.append("açık-uçlu düz draw")
    elif _has_gutshot(vals):
        eq = max(eq, 0.16); labels.append("gutshot")
    return eq, labels


def _has_gutshot(vals: List[int]) -> bool:
    """5'lik bir pencerede tam 4 değer varsa (bir iç boşluk) → gutshot."""
    vs = set(vals)
    for lo in range(-1, 10):
        window = set(range(lo, lo + 5))
        if len(window & vs) == 4:
            return True
    return False


def _is_top_pair(hero: List[Card], board: List[Card]) -> bool:
    if not board:
        return False
    top = max(_rv(c.rank) for c in board)
    hero_ranks = {_rv(c.rank) for c in hero}
    return top in hero_ranks


def street_plan(hero_cards, board, in_position: bool = True,
                has_initiative: bool = True) -> dict:
    """Flop/turn için çok-sokaklı plan. Döner: kind, streets, plan_text."""
    hero = parse_cards(hero_cards)
    bd = parse_cards(board)
    if len(hero) < 2 or len(bd) < 3:
        return {"kind": "n/a", "streets": 0, "plan": ""}

    rank = evaluate_best_hand(hero, bd)[0]      # 0=royal … 9=high card
    draw_eq, draw_lbl = _draws(hero, bd)

    from app.poker.postflop_gto import classify_board
    tex = classify_board(bd)
    wet = tex.wetness

    # ── El sınıfı ──
    if rank <= 6 or (rank == 7):                # set/trips+ veya two pair
        kind = "güçlü value"
    elif rank == 8 and _is_top_pair(hero, bd):
        kind = "top pair (ince value)"
    elif draw_eq >= 0.30:
        kind = "güçlü draw (semi-bluff)"
    elif rank == 8:
        kind = "orta pair (showdown)"
    elif draw_eq >= 0.15:
        kind = "zayıf draw"
    else:
        kind = "hava (air)"

    streets_left = 2 if len(bd) == 3 else 1     # flop→2, turn→1

    # ── Plan + scare/continue kartları ──
    scare = []
    if tex.two_tone or tex.monotone:
        scare.append("flush kartı")
    if tex.connected:
        scare.append("düz kartı")
    scare.append("üst overcard")

    if kind == "güçlü value":
        plan = (f"{min(streets_left+1,3)} sokak VALUE planı — pot'u büyüt, "
                f"flop+turn+river bet. Çoğu kart devam; sadece açık nut-değişimi "
                f"({', '.join(scare)}) gelirse fren/pot kontrol. Size: büyük "
                f"(value maks.).")
    elif kind == "top pair (ince value)":
        plan = ("2 sokak İNCE value — flop bet + iyi turn'de bir bet daha; "
                "river'da büyük pot'tan kaçın (check-back/küçük). Scare kart "
                f"({', '.join(scare)}) gelirse yavaşla — orta el, 3 sokak değil.")
    elif kind == "güçlü draw (semi-bluff)":
        plan = (f"SEMI-BLUFF planı ({', '.join(draw_lbl) or 'draw'}): flop "
                "bet/raise + iyi turn'de barrel (fold equity + draw). Draw "
                "tamamlanırsa VALUE'ya döner; brick river'da blöf-seç ya da "
                "give-up. Size: yarı-pot+ (denial + tamamlama).")
    elif kind == "orta pair (showdown)":
        plan = ("POT KONTROL — orta-güç showdown değeri. 1 sokak ya da "
                "check/call; büyük pot'a girme (ters seçim: daha iyiyi call "
                "ettirir, daha kötüyü kaçırır). Bluff-catch'e hazır ol.")
    elif kind == "zayıf draw":
        plan = ("İnce semi-bluff / check — zayıf draw. IP'de ucuz gör (equity "
                "realize), OOP'de check-call/check-fold. Barrel'ı sadece iyi "
                "fold equity + ek equity varsa.")
    else:  # air
        plan = (f"POLARİZE blöf ya da give-up. Blöf seçeceksen barrel kartlarını "
                f"({', '.join(scare)} senin range'ine yarayanlar) seç + "
                "blocker'lı eller; havasız checklerini koru. Tek blöf değil, "
                "turn/river barrel planı kur.")

    return {"kind": kind, "streets": streets_left, "wetness": round(wet, 2),
            "draw_eq": round(draw_eq, 2), "plan": plan}


def coach_plan_line(p: dict) -> str:
    """street_plan çıktısını tek satır koç metnine çevir."""
    if not p.get("plan"):
        return ""
    return f"El: {p['kind']} → {p['plan']}"
