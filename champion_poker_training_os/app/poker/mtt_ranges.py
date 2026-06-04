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
    # Yayınlanmış Nash open-jam (HRC/SnapShove) ile yeniden kalibre (D88):
    # geç pozisyon kısa stack'te ~%5-8 GENİŞ (eski tablo BTN/CO/SB'de tight'tı).
    # Değişmezler korunur: SB > BTN > CO > MP > UTG; stack↑ → range daralır.
    6:  {"UTG": 28, "MP": 34, "CO": 42, "BTN": 58, "SB": 72},
    8:  {"UTG": 20, "MP": 26, "CO": 34, "BTN": 50, "SB": 64},
    10: {"UTG": 16, "MP": 21, "CO": 28, "BTN": 43, "SB": 56},
    12: {"UTG": 13, "MP": 17, "CO": 23, "BTN": 36, "SB": 50},
    15: {"UTG": 10, "MP": 13, "CO": 18, "BTN": 28, "SB": 42},
    20: {"UTG": 7,  "MP": 9,  "CO": 13, "BTN": 20, "SB": 32},
    25: {"UTG": 5,  "MP": 6,  "CO": 9,  "BTN": 14, "SB": 24},
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

    # BB'nin "first-in OPEN" range'i YOKTUR — preflop son oynayan odur. Folded-to
    # BB pot'u kazanır (karar yok); limp'lenen pot ise bir OPSİYON spotudur:
    # limper'lara karşı polarize iso-raise (~top %16), gerisi CHECK. ASLA %100
    # raise değil. POS_RFI_TARGET_PCT['BB']=100 bir "geniş DEFEND" işareti, açış
    # genişliği değil — build_mtt_rfi onu yanlış okuyup tüm gridi kırmızı yapardı.
    if _normalize_pos_rfi(position) == "BB":
        return _fill_top_pct(16.0)

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


# ── ICM-ADJUSTED PUSH/FOLD ────────────────────────────────────────────
# Bubble / final-table'da her chip kaybı her chip kazancından pahalı
# (bubble factor > 1). Bu yüzden jam ve özellikle CALL range'leri daralır.
# icm.py risk_premium + push_fold_range_width ICM multiplier'ı kullanır.

def build_icm_push_fold(position: str, stack_bb: float,
                        stage: str = "bubble") -> Dict[str, ActionFreq]:
    """ICM-adjusted jam range. stage: chipEV / bubble / final table / satellite."""
    from app.poker.icm import push_fold_range_width
    # chipEV jam %'sini al, ICM multiplier uygula
    chip_pct = mtt_jam_pct(position, stack_bb)
    # push_fold_range_width ICM multiplier'ını oran olarak çıkar
    chipev_w = push_fold_range_width(stack_bb, "chipEV")
    icm_w = push_fold_range_width(stack_bb, stage)
    mult = (icm_w / chipev_w) if chipev_w > 0 else 1.0
    adj_pct = chip_pct * mult
    return _fill_top_pct(adj_pct)


def build_icm_call_vs_jam(stack_bb: float, stage: str = "bubble",
                          bubble_factor_val: float = 1.5) -> Dict[str, ActionFreq]:
    """ICM-adjusted call-vs-jam. Bubble factor yüksekse call çok daralır.

    bubble_factor_val: icm.bubble_factor() çıktısı (1.0 = chipEV, 2.0 = ağır ICM).
    Call eşiği bubble factor ile orantılı daralır.
    """
    chip_pct = call_vs_jam_pct(stack_bb)
    # Bubble factor 1.0 → tam, 2.0 → ~yarı
    bf_mult = 1.0 / max(1.0, bubble_factor_val)
    stage_mult = {
        "chipEV": 1.0, "bubble": 0.60, "final table": 0.70,
        "satellite": 0.45, "PKO": 1.0,
    }.get(stage, 0.75)
    adj_pct = chip_pct * bf_mult * (stage_mult / 0.6 if stage != "chipEV" else 1.0)
    adj_pct = max(2.0, min(chip_pct, adj_pct))
    ranked = get_ranked_hands()
    result: Dict[str, ActionFreq] = {}
    total = 1326
    target = total * adj_pct / 100
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


# ── BOUNTY / PKO PUSH-FOLD & CALL ─────────────────────────────────────
# Bounty (rakibi elersen ödül) call/jam range'i GENİŞLETİR — extra EV.
# bounty_pct: rakibin bounty'sinin pot/stack'e oranı (0.0-1.0+).
# Tipik PKO: bounty ≈ buyin'in yarısı → effective call threshold ~%15-25 düşer.

def build_pko_call_vs_jam(stack_bb: float,
                          bounty_ratio: float = 0.5) -> Dict[str, ActionFreq]:
    """Bounty-aware call range. bounty_ratio = bounty_value / effective_stack.

    Bounty ne kadar büyükse call o kadar genişler (rakibi elersen bounty alırsın).
    """
    base_pct = call_vs_jam_pct(stack_bb)
    # Bounty her %50 oranında call range'i ~%30 genişletir
    widen = 1.0 + bounty_ratio * 0.6
    adj_pct = min(base_pct * widen, 60)   # cap %60
    ranked = get_ranked_hands()
    result: Dict[str, ActionFreq] = {}
    total = 1326
    target = total * adj_pct / 100
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


def build_pko_jam(position: str, stack_bb: float,
                  bounty_ratio: float = 0.5) -> Dict[str, ActionFreq]:
    """Bounty-aware jam range — biraz daha geniş (bounty ele geçirme şansı)."""
    base_pct = mtt_jam_pct(position, stack_bb)
    widen = 1.0 + bounty_ratio * 0.25   # jam daha az genişler (zaten geniş)
    return _fill_top_pct(min(base_pct * widen, 85))


# ── SQUEEZE (open + caller'a karşı 3-bet) ─────────────────────────────
# Squeeze: birisi açtı, birisi call etti, sen 3-bet ediyorsun.
# Dead money var (caller'ın parası) ama multiway risk → daha SIKI + value-weighted.
# Caller sayısı arttıkça squeeze daralır.

def build_squeeze(position: str, stack_bb: float = 100,
                  num_callers: int = 1) -> Dict[str, ActionFreq]:
    """Squeeze 3-bet range. num_callers arttıkça daralır + value-weighted."""
    # Base squeeze % — tek caller'a karşı ~%6-8, position'a göre
    base = {"UTG": 4, "MP": 5, "CO": 6, "BTN": 8, "SB": 7, "BB": 9}.get(
        _normalize_pos_rfi(position), 6)
    # Her ekstra caller squeeze'i %30 daraltır
    base *= (0.70 ** (num_callers - 1))
    ranked = get_ranked_hands()
    result: Dict[str, ActionFreq] = {}
    total = 1326
    target = total * base / 100
    # Squeeze polarize: value (üst) pure raise + bazı bluff (A5s-A3s, suited)
    acc = 0
    for hk in ranked:
        c = _combo_count(hk)
        if acc < target * 0.80:
            result[hk] = pure_raise()
        elif acc < target:
            result[hk] = mixed(70)
        else:
            break
        acc += c
    # Polarized bluffs (blocker + playability)
    for bluff in ("A5s", "A4s", "A3s", "KQs", "76s"):
        if bluff not in result:
            result[bluff] = mixed(35)
    return result


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
    if scenario == "ICM Push/Fold":
        return build_icm_push_fold(position, stack_depth, "bubble").get(hand_key, pure_fold())
    if scenario == "PKO Jam":
        return build_pko_jam(position, stack_depth, 0.5).get(hand_key, pure_fold())
    if scenario == "Squeeze":
        return build_squeeze(position, stack_depth, 1).get(hand_key, pure_fold())
    if scenario == "RFI":
        return build_mtt_rfi(position, stack_depth).get(hand_key, pure_fold())
    # vs RFI / vs 3-bet → cash heuristic'e düş (MTT ayarı stack mult ile zaten)
    from app.poker.gto_generator import heuristic_get_action
    return heuristic_get_action(position, hand_key, scenario, stack_depth,
                                "MTT", vs_position)
