"""MTT (turnuva) range engine — stack-depth aware, ante + Nash temelli.

Cash (100bb, ante yok) ile MTT'nin farkları:
  1. ANTE: MTT'de ante var → pot preflop daha büyük → açış daha kârlı
     → range'ler ~%2-4 genişler, sizing 2-2.3x'e düşer
  2. STACK DEPTH: turnuva boyunca stack değişir; her derinlik farklı strateji
     - 200bb deep: suited hands + implied odds kazanır, dominated offsuit kaybeder
     - 100bb: baseline (ante ile cash gibi)
     - 40bb: 3-bet-or-fold artar, flat azalır, daha linear
     - 20bb: çok sıkı open / open-jam karışımı
     - <15bb: saf push/fold (Nash)
  3. ICM: pay jump / bubble yakını → call range daralır (chipEV'den sapar)

Bu modül:
  - mtt_jam_pct(pos, stack) → Nash-kalibre jam yüzdesi
  - build_mtt_push_fold(pos, stack) → jam (all-in) range
  - build_call_vs_jam(pos, stack, vs_pos) → jam'a karşı call range
  - build_mtt_rfi(pos, stack) → ante-aware açış range'i (depth-shaped)

Push/fold yüzdeleri yayınlanmış Nash equilibrium (HoldemResources /
SnapShove standardı, chipEV) yaklaşımına kalibre. Algoritma + sayılar
kamuya açık poker teorisinden — kendi implementation.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.poker.gto_ranges import ActionFreq, pure_fold, pure_raise, mixed
from app.poker.gto_generator import get_ranked_hands, _combo_count


# ── PUSH/FOLD NASH JAM % (chipEV, unopened jam) ───────────────────────
# stack_bb → {position: jam_pct}
# Pozisyon arkasındaki oyuncu sayısına göre: SB (1 arkada) en geniş,
# UTG (5 arkada) en sıkı. Yayınlanmış Nash chart'larına kalibre.
JAM_PCT: Dict[int, Dict[str, float]] = {
    6:  {"UTG": 22, "MP": 27, "CO": 34, "BTN": 50, "SB": 68},
    8:  {"UTG": 18, "MP": 22, "CO": 28, "BTN": 42, "SB": 60},
    10: {"UTG": 14, "MP": 17, "CO": 22, "BTN": 35, "SB": 52},
    12: {"UTG": 12, "MP": 15, "CO": 19, "BTN": 30, "SB": 46},
    15: {"UTG": 10, "MP": 12, "CO": 16, "BTN": 25, "SB": 40},
    20: {"UTG": 7,  "MP": 9,  "CO": 12, "BTN": 18, "SB": 30},
    25: {"UTG": 5,  "MP": 6,  "CO": 8,  "BTN": 13, "SB": 22},
}


def mtt_jam_pct(position: str, stack_bb: float) -> float:
    """Pozisyon + stack için Nash jam yüzdesi (interpolasyonla)."""
    pos = _normalize_pos(position)
    stacks = sorted(JAM_PCT.keys())
    # Clamp
    if stack_bb <= stacks[0]:
        return JAM_PCT[stacks[0]].get(pos, 15)
    if stack_bb >= stacks[-1]:
        return JAM_PCT[stacks[-1]].get(pos, 5)
    # Linear interpolate between two nearest stack buckets
    for i in range(len(stacks) - 1):
        lo, hi = stacks[i], stacks[i + 1]
        if lo <= stack_bb <= hi:
            lo_pct = JAM_PCT[lo].get(pos, 15)
            hi_pct = JAM_PCT[hi].get(pos, 5)
            t = (stack_bb - lo) / (hi - lo)
            return lo_pct + t * (hi_pct - lo_pct)
    return 15


def _normalize_pos(position: str) -> str:
    pos = position.upper()
    if pos in ("LJ", "UTG+1"):
        return "MP"
    if pos == "HJ":
        return "CO"
    if pos == "BB":
        return "SB"   # BB jam (vs SB) ≈ SB width
    return pos if pos in ("UTG", "MP", "CO", "BTN", "SB") else "CO"


# ── CALL-vs-JAM % (jam'a karşı call) ──────────────────────────────────
# Jam'a call etmek jam etmekten daha sıkı (pot odds + no fold equity).
# stack_bb → call %
CALL_VS_JAM_PCT: Dict[int, float] = {
    6:  38, 8: 32, 10: 26, 12: 22, 15: 18, 20: 13, 25: 9,
}


def call_vs_jam_pct(stack_bb: float) -> float:
    stacks = sorted(CALL_VS_JAM_PCT.keys())
    if stack_bb <= stacks[0]:
        return CALL_VS_JAM_PCT[stacks[0]]
    if stack_bb >= stacks[-1]:
        return CALL_VS_JAM_PCT[stacks[-1]]
    for i in range(len(stacks) - 1):
        lo, hi = stacks[i], stacks[i + 1]
        if lo <= stack_bb <= hi:
            t = (stack_bb - lo) / (hi - lo)
            return CALL_VS_JAM_PCT[lo] + t * (CALL_VS_JAM_PCT[hi] - CALL_VS_JAM_PCT[lo])
    return 15


# ── RANGE BUILDERS ────────────────────────────────────────────────────

def _fill_top_pct(target_pct: float, action_builder=pure_raise,
                  mixed_band: float = 0.12) -> Dict[str, ActionFreq]:
    """Top-X% range'i doldur, boundary'de mixed band oluştur."""
    ranked = get_ranked_hands()
    result: Dict[str, ActionFreq] = {}
    total = 1326
    target_combos = total * target_pct / 100
    band_start = target_combos * (1 - mixed_band)
    acc = 0
    for hk in ranked:
        c = _combo_count(hk)
        if acc < band_start:
            result[hk] = action_builder()
        elif acc < target_combos:
            pos_in = (acc - band_start) / max(target_combos - band_start, 1)
            freq = int(round(85 - pos_in * 55))   # 85% → 30%
            result[hk] = mixed(max(30, freq))
        else:
            break
        acc += c
    return result


def build_mtt_push_fold(position: str, stack_bb: float) -> Dict[str, ActionFreq]:
    """Jam (all-in) range — kısa stack Nash."""
    pct = mtt_jam_pct(position, stack_bb)
    return _fill_top_pct(pct)


def build_call_vs_jam(stack_bb: float) -> Dict[str, ActionFreq]:
    """Jam'a karşı call range (call=raise field olarak işaretlenir)."""
    pct = call_vs_jam_pct(stack_bb)
    # call'ı 'call' action olarak işaretle
    ranked = get_ranked_hands()
    result: Dict[str, ActionFreq] = {}
    total = 1326
    target = total * pct / 100
    acc = 0
    for hk in ranked:
        c = _combo_count(hk)
        if acc < target * 0.88:
            result[hk] = {"raise": 0, "call": 100, "fold": 0}
        elif acc < target:
            result[hk] = {"raise": 0, "call": 55, "fold": 45}
        else:
            break
        acc += c
    return result


# ── MTT RFI (ante-aware, depth-shaped) ────────────────────────────────
# Cash 100bb baseline'a göre ayarlamalar.
# % adjustment per depth (ante widening + ICM/depth tightening net etkisi)

MTT_RFI_ADJUST = {
    # depth_bb: (pct_multiplier, note)
    200: (1.04, "deep — suited hands + implied odds"),
    150: (1.03, "deep — slightly more speculative"),
    100: (1.02, "baseline + ante widening"),
    80:  (1.01, "near-baseline"),
    60:  (0.98, "tighter — less implied odds"),
    40:  (0.92, "3-bet-or-fold artar, flat azalır"),
    30:  (0.85, "shallow — linear, high-card heavy"),
    25:  (0.78, "pre-jam zone"),
    20:  (0.70, "open-jam karışımı"),
}


def _rfi_adjust_mult(stack_bb: float) -> float:
    depths = sorted(MTT_RFI_ADJUST.keys())
    if stack_bb <= depths[0]:
        return MTT_RFI_ADJUST[depths[0]][0]
    if stack_bb >= depths[-1]:
        return MTT_RFI_ADJUST[depths[-1]][0]
    for i in range(len(depths) - 1):
        lo, hi = depths[i], depths[i + 1]
        if lo <= stack_bb <= hi:
            t = (stack_bb - lo) / (hi - lo)
            lo_m = MTT_RFI_ADJUST[lo][0]
            hi_m = MTT_RFI_ADJUST[hi][0]
            return lo_m + t * (hi_m - lo_m)
    return 1.0


def build_mtt_rfi(position: str, stack_bb: float) -> Dict[str, ActionFreq]:
    """Ante-aware MTT açış range'i. <=15bb → push/fold'a yönlendirir."""
    if stack_bb <= 15:
        return build_mtt_push_fold(position, stack_bb)

    # Cash baseline RFI %'sini al, MTT ayarı uygula
    from app.poker.gto_generator import POS_RFI_TARGET_PCT
    base_pct = POS_RFI_TARGET_PCT.get(_normalize_pos_rfi(position), 25)
    mult = _rfi_adjust_mult(stack_bb)
    target = base_pct * mult

    # Depth shape: deep stacks (150bb+) suited connector/suited ace bonus
    result = _fill_top_pct(target)
    if stack_bb >= 150:
        # Derin: bazı suited connector/gapper ekle (implied odds)
        for hk in ("54s", "65s", "76s", "87s", "98s", "T9s", "J9s", "T8s",
                   "97s", "86s", "75s", "64s", "53s"):
            if hk not in result:
                result[hk] = mixed(45)
    elif stack_bb <= 40:
        # Shallow: suited gapper'ları kıs, broadway/pair ağırlık
        for hk in ("53s", "64s", "75s", "86s", "97s", "J8s", "Q8s", "K7s"):
            if hk in result and result[hk].get("raise", 0) < 60:
                result.pop(hk, None)
    return result


def _normalize_pos_rfi(position: str) -> str:
    pos = position.upper()
    if pos == "UTG+1":
        return "MP"
    return pos


# ── UNIFIED MTT GET_ACTION ────────────────────────────────────────────

def mtt_get_action(
    position: str,
    hand_key: str,
    scenario: str = "RFI",
    stack_depth: int = 100,
    vs_position: Optional[str] = None,
) -> ActionFreq:
    """MTT mode lookup. cash get_action'dan ayrı — ante + depth + Nash."""
    if scenario in ("Push/Fold", "Jam"):
        return build_mtt_push_fold(position, stack_depth).get(hand_key, pure_fold())
    if scenario == "Call vs Jam":
        return build_call_vs_jam(stack_depth).get(hand_key, pure_fold())
    if scenario == "RFI":
        return build_mtt_rfi(position, stack_depth).get(hand_key, pure_fold())
    # vs RFI / vs 3-bet → cash heuristic'e düş (MTT ayarı stack mult ile zaten)
    from app.poker.gto_generator import heuristic_get_action
    return heuristic_get_action(position, hand_key, scenario, stack_depth,
                                "MTT", vs_position)
