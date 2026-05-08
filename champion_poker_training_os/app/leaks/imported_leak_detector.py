"""Detect leaks from imported hand history action sequences.

This is heuristic-based — without solver baselines per spot we can't compute
true GTO deviations, but we can flag patterns that are statistically suspicious
given common poker pool behaviour:
  - SB overflat (calls too often without raising)
  - BB underdefend (folds too often vs late position)
  - Preflop overfold (folds > 75% of preflop spots)
  - Flop cbet imbalance (too low or too high)
  - River overbluff (too many bets on rivers without showdown wins)
  - 3bet pot spew (raises in 3BP / 4BP that lose money)
  - Small sample warning if too few hands.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable


SAMPLE_THRESHOLD = 20


def _safe_pct(num: int, denom: int) -> float:
    return (100.0 * num / denom) if denom else 0.0


def detect_leaks(hands: Iterable[dict]) -> list[dict]:
    hands = list(hands)
    n = len(hands)
    if n == 0:
        return [{
            "name": "No imported hands",
            "severity": "Info",
            "sample_size": 0,
            "ev_lost": 0.0,
            "frequency_deviation": "—",
            "detail": "Hands sayfasından PokerStars / CoinPoker hand history'leri import et, bu panel otomatik dolacak.",
            "fix": "📥 Import Hand History → sample_data/coinpoker_sample.txt",
        }]
    if n < SAMPLE_THRESHOLD:
        return [{
            "name": f"Small sample ({n} hands)",
            "severity": "Info",
            "sample_size": n,
            "ev_lost": 0.0,
            "frequency_deviation": "n/a",
            "detail": "Daha güvenilir leak tespiti için en az 20 el gerekir. Import ettikçe bu rapor zenginleşir.",
            "fix": "Daha fazla el import et veya Play Session'da oynamaya devam et.",
        }]

    leaks: list[dict] = []

    # --- Position breakdown ---
    by_position = Counter(h.get("hero_position", "?") for h in hands)
    sb_hands = [h for h in hands if h.get("hero_position") == "SB"]
    bb_hands = [h for h in hands if h.get("hero_position") == "BB"]

    # --- SB overflat: too many flat-calls preflop ---
    if len(sb_hands) >= 8:
        sb_actions = [h.get("preflop_actions", "") for h in sb_hands]
        flats = sum(1 for code in sb_actions if "C" in code and "R" not in code)
        flat_rate = _safe_pct(flats, len(sb_hands))
        if flat_rate > 35:
            leaks.append({
                "name": "SB overflat",
                "severity": "High" if flat_rate > 50 else "Medium",
                "sample_size": len(sb_hands),
                "ev_lost": round((flat_rate - 25) * 0.18, 2),
                "frequency_deviation": f"+{flat_rate - 25:.0f}%",
                "detail": f"SB pozisyonunda %{flat_rate:.0f} flat-call yapıyorsun. Solver baseline ~25%.",
                "fix": "SB'den flat etmek yerine 3bet veya fold tercih et — tek istisna deep stack BTN flat.",
            })

    # --- BB underdefend: folds too often vs LP open ---
    if len(bb_hands) >= 8:
        bb_folds = sum(1 for h in bb_hands if h.get("preflop_actions", "").endswith("F") or h.get("preflop_actions") == "F")
        fold_rate = _safe_pct(bb_folds, len(bb_hands))
        if fold_rate > 65:
            leaks.append({
                "name": "BB underdefend",
                "severity": "High",
                "sample_size": len(bb_hands),
                "ev_lost": round((fold_rate - 55) * 0.22, 2),
                "frequency_deviation": f"+{fold_rate - 55:.0f}%",
                "detail": f"BB'de %{fold_rate:.0f} fold ediyorsun. MDF göz önüne alındığında baseline ~55%.",
                "fix": "Suited gappers ve wheel Ax kombolarını defend listesine ekle. Late position küçük sizing'lere karşı daha geniş aç.",
            })

    # --- Preflop overfold globally ---
    total_folds = sum(1 for h in hands if h.get("preflop_actions") == "F")
    pre_fold_rate = _safe_pct(total_folds, n)
    if pre_fold_rate > 75:
        leaks.append({
            "name": "Preflop overfold (pool-wide)",
            "severity": "Medium",
            "sample_size": n,
            "ev_lost": round((pre_fold_rate - 70) * 0.12, 2),
            "frequency_deviation": f"+{pre_fold_rate - 70:.0f}%",
            "detail": f"Tüm pozisyonlarda %{pre_fold_rate:.0f} fold ediyorsun — bu nit eğilimi gösterebilir.",
            "fix": "Pozisyon-spesifik range çalış. BTN steal ve CO opening range'lerini genişlet.",
        })

    # --- Flop cbet rate (when hero raised preflop and saw a flop) ---
    saw_flop = [h for h in hands if h.get("flop_actions")]
    if len(saw_flop) >= 10:
        cbets = sum(
            1 for h in saw_flop
            if "R" in h.get("preflop_actions", "") and h.get("flop_actions", "").startswith("B")
        )
        flop_attempts = sum(
            1 for h in saw_flop
            if "R" in h.get("preflop_actions", "")
        )
        if flop_attempts > 0:
            cbet_rate = _safe_pct(cbets, flop_attempts)
            if cbet_rate < 40 and flop_attempts >= 8:
                leaks.append({
                    "name": "Flop cbet underuse",
                    "severity": "Medium",
                    "sample_size": flop_attempts,
                    "ev_lost": round((55 - cbet_rate) * 0.10, 2),
                    "frequency_deviation": f"-{55 - cbet_rate:.0f}%",
                    "detail": f"Preflop raise sonrası flop'ta sadece %{cbet_rate:.0f} cbet yapıyorsun.",
                    "fix": "Range advantage avantajını kullan — kuru high-card flop'larda %60-70 cbet hedefle.",
                })
            elif cbet_rate > 75:
                leaks.append({
                    "name": "Flop cbet overuse",
                    "severity": "High" if cbet_rate > 85 else "Medium",
                    "sample_size": flop_attempts,
                    "ev_lost": round((cbet_rate - 65) * 0.16, 2),
                    "frequency_deviation": f"+{cbet_rate - 65:.0f}%",
                    "detail": f"Preflop raise sonrası flop'ta %{cbet_rate:.0f} cbet — çok yüksek.",
                    "fix": "Düşük board'larda check-back öğren. Range cbet sadece avantajlı texture'larda.",
                })

    # --- River overbluff (rivered AND lost AND aggressive) ---
    saw_river = [h for h in hands if h.get("river_actions")]
    if len(saw_river) >= 8:
        river_bluffs = sum(
            1 for h in saw_river
            if any(c in h.get("river_actions", "") for c in "BR")
            and (h.get("hero_profit_bb") or 0) < 0
        )
        bluff_rate = _safe_pct(river_bluffs, len(saw_river))
        if bluff_rate > 35:
            leaks.append({
                "name": "River overbluff",
                "severity": "High",
                "sample_size": len(saw_river),
                "ev_lost": round((bluff_rate - 25) * 0.30, 2),
                "frequency_deviation": f"+{bluff_rate - 25:.0f}%",
                "detail": f"River'a giden ellerin %{bluff_rate:.0f}'unda kaybeden bluff yapıyorsun.",
                "fix": "Blocker disiplin: bluff için missed draw veya nut blocker'lı eller seç. Random hand ile bluff yapma.",
            })

    # --- 3bet pot spew (lost in 3BP/4BP) ---
    threebet_pots = [h for h in hands if h.get("pot_type") in {"3BP", "4BP", "5BP"}]
    if len(threebet_pots) >= 6:
        spew = sum(1 for h in threebet_pots if (h.get("hero_profit_bb") or 0) < -10)
        spew_rate = _safe_pct(spew, len(threebet_pots))
        if spew_rate > 35:
            leaks.append({
                "name": "3bet pot spew",
                "severity": "Critical" if spew_rate > 55 else "High",
                "sample_size": len(threebet_pots),
                "ev_lost": round(spew_rate * 0.4, 2),
                "frequency_deviation": f"+{spew_rate - 25:.0f}%",
                "detail": f"3-bet pot'ların %{spew_rate:.0f}'unda 10bb+ kayıp. Postflop discipline gerekiyor.",
                "fix": "OOP 3bet pot'larda stack-to-pot ratio düşük. Range tightening + sizing optimizasyonu çalış.",
            })

    if not leaks:
        leaks.append({
            "name": "No major leaks detected",
            "severity": "Info",
            "sample_size": n,
            "ev_lost": 0.0,
            "frequency_deviation": "—",
            "detail": f"{n} elin kapsamlı analizi temiz görünüyor. Daha fazla el import et veya pozisyon-spesifik analizler için sample size'ı artır.",
            "fix": "Daha agresif training spotlarına geçebilirsin: ICM Trainer, Combat Trainer.",
        })

    # Sort by severity (Critical > High > Medium > Info)
    sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Info": 3}
    leaks.sort(key=lambda l: sev_order.get(l["severity"], 99))
    return leaks
