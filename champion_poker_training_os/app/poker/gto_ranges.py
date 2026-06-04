"""GTO preflop range datasetı.

Veri kaynağı: GTOWizard public charts, Upswing Poker free preflop guide,
Jonathan Little's solver-derived ranges. Pros training siteleri konsensus.

Tabloda her el için aksiyon FREKANSI tutuluyor (0-100). Örnek:
    "K7s": {"raise": 55, "call": 0, "fold": 45}
→ %55 raise, %45 fold (mixed strategy).

Saf strategy → tek aksiyon %100, kalanlar 0.

Henüz tüm pozisyon × stack × scenario doldurulmadı.
Şu an: 6-max cash 100bb RFI tam dolu (UTG..BB).
TODO: MTT 40bb, 20bb push/fold, vs RFI 3-bet, 4-bet defend.
"""
from __future__ import annotations

from typing import Dict, List

# ── HAND KEYS ─────────────────────────────────────────────────────────
# Tüm 169 hand kombosu için canonical key seti.
RANKS_DESC = list("AKQJT98765432")


def all_hand_keys() -> List[str]:
    """169 hand key: AA, AKs, AKo, ..., 22 sırasıyla."""
    keys: List[str] = []
    for i, hi in enumerate(RANKS_DESC):
        for j, lo in enumerate(RANKS_DESC):
            if i == j:
                keys.append(hi + lo)
            elif i < j:
                keys.append(hi + lo + "s")
            else:
                keys.append(lo + hi + "o")
    return keys


# ── ACTION FREQUENCY DICT ─────────────────────────────────────────────
# Her el için {action: pct}. Aksiyon tipleri: raise, call, fold.
# Toplam = 100. Saf folds için boş dict → her zaman fold.

ActionFreq = Dict[str, int]


def pure_raise() -> ActionFreq:
    return {"raise": 100, "call": 0, "fold": 0}


def pure_fold() -> ActionFreq:
    return {"raise": 0, "call": 0, "fold": 100}


def mixed(raise_pct: int, call_pct: int = 0) -> ActionFreq:
    """raise + call + fold = 100."""
    fold_pct = 100 - raise_pct - call_pct
    return {"raise": raise_pct, "call": call_pct, "fold": max(0, fold_pct)}


# ── 6-MAX CASH 100BB RFI ──────────────────────────────────────────────
# Solver-derived ranges (GTOWizard free tier konsensusu).
# Açıklama: bir spot için sadece raise yüzdeleri verilir, fold = 100 - raise.
# RFI'da call yoktur (kimse limpemez 100bb cash'te — açık veya katla).

RFI_100BB_6MAX: Dict[str, Dict[str, ActionFreq]] = {
    # UTG (~18% RFI) — en sıkı pozisyon
    "UTG": {
        # Premium pairs ve broadways → pure raise
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A8s": pure_raise(), "A5s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "QJs": pure_raise(), "JTs": pure_raise(), "T9s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(),
        # Mixed (kısmi açış)
        "55": mixed(75), "44": mixed(50), "33": mixed(35), "22": mixed(30),
        "A7s": mixed(85), "A6s": mixed(80),
        "A4s": mixed(90), "A3s": mixed(85), "A2s": mixed(75),
        "K9s": mixed(70), "K8s": mixed(30),
        "Q9s": mixed(50), "J9s": mixed(35),
        "98s": mixed(75), "87s": mixed(65), "76s": mixed(70), "65s": mixed(55), "54s": mixed(40),
        "ATo": mixed(70), "A9o": mixed(20),
        "KQo": mixed(80), "KJo": mixed(45), "QJo": mixed(20),
    },
    # MP / LJ (~22% RFI)
    "MP": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(), "55": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A8s": pure_raise(),
        "A7s": pure_raise(), "A5s": pure_raise(), "A4s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(), "K9s": pure_raise(),
        "QJs": pure_raise(), "QTs": pure_raise(),
        "JTs": pure_raise(), "T9s": pure_raise(), "98s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(),
        "KQo": pure_raise(),
        # Mixed
        "44": mixed(85), "33": mixed(55), "22": mixed(45),
        "A6s": mixed(85), "A3s": mixed(90), "A2s": mixed(85),
        "K8s": mixed(60), "K7s": mixed(35),
        "Q9s": mixed(75), "Q8s": mixed(30),
        "J9s": mixed(65), "J8s": mixed(25),
        "T8s": mixed(40),
        "87s": mixed(80), "76s": mixed(75), "65s": mixed(70), "54s": mixed(55),
        "ATo": mixed(85), "A9o": mixed(35), "KJo": mixed(80), "KTo": mixed(45), "QJo": mixed(55), "JTo": mixed(25),
    },
    # CO (~28% RFI)
    "CO": {
        # Tam açış: 99+, AJ+, ATs+, KQs, KJs+, QJs, JTs (pure)
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(), "55": pure_raise(), "44": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(), "ATs": pure_raise(),
        "A9s": pure_raise(), "A8s": pure_raise(), "A7s": pure_raise(), "A6s": pure_raise(),
        "A5s": pure_raise(), "A4s": pure_raise(), "A3s": pure_raise(), "A2s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(), "K9s": pure_raise(),
        "QJs": pure_raise(), "QTs": pure_raise(), "Q9s": pure_raise(),
        "JTs": pure_raise(), "J9s": pure_raise(), "T9s": pure_raise(), "98s": pure_raise(),
        "87s": pure_raise(), "76s": pure_raise(), "65s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(), "ATo": pure_raise(),
        "KQo": pure_raise(), "KJo": pure_raise(),
        # Mixed
        "33": pure_raise(), "22": mixed(85),
        "K8s": pure_raise(), "K7s": mixed(85), "K6s": mixed(65), "K5s": mixed(55), "K4s": mixed(35),
        "Q8s": pure_raise(), "Q7s": mixed(50),
        "J8s": pure_raise(), "J7s": mixed(30),
        "T8s": pure_raise(), "T7s": mixed(35),
        "97s": mixed(70), "86s": mixed(45),
        "54s": pure_raise(), "43s": mixed(60), "53s": mixed(35),
        "KTo": pure_raise(), "K9o": mixed(75), "K8o": mixed(40),
        "QJo": pure_raise(), "QTo": mixed(80), "Q9o": mixed(40),
        "JTo": mixed(85), "J9o": mixed(45),
        "T9o": mixed(60), "98o": mixed(35),
        "A9o": mixed(85), "A8o": mixed(60), "A7o": mixed(45), "A5o": mixed(45),
    },
    # BTN (~48% RFI) — en geniş pozisyon
    "BTN": {
        # Geniş açış range'i
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(),
        "55": pure_raise(), "44": pure_raise(), "33": pure_raise(), "22": pure_raise(),
        # Tüm A-x suited
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(), "ATs": pure_raise(),
        "A9s": pure_raise(), "A8s": pure_raise(), "A7s": pure_raise(), "A6s": pure_raise(),
        "A5s": pure_raise(), "A4s": pure_raise(), "A3s": pure_raise(), "A2s": pure_raise(),
        # Tüm K-x suited
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "K9s": pure_raise(), "K8s": pure_raise(), "K7s": pure_raise(),
        "K6s": pure_raise(), "K5s": pure_raise(), "K4s": pure_raise(),
        # Q-x suited (Q5s+)
        "QJs": pure_raise(), "QTs": pure_raise(), "Q9s": pure_raise(),
        "Q8s": pure_raise(), "Q7s": pure_raise(), "Q6s": pure_raise(), "Q5s": pure_raise(),
        # J-x suited (J7s+)
        "JTs": pure_raise(), "J9s": pure_raise(), "J8s": pure_raise(), "J7s": pure_raise(),
        # T-x suited (T7s+)
        "T9s": pure_raise(), "T8s": pure_raise(), "T7s": pure_raise(),
        # Suited connectors / one-gappers
        "98s": pure_raise(), "97s": pure_raise(), "87s": pure_raise(), "86s": pure_raise(),
        "76s": pure_raise(), "65s": pure_raise(), "54s": pure_raise(),
        # Offsuit
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(),
        "ATo": pure_raise(), "A9o": pure_raise(), "A8o": pure_raise(),
        "KQo": pure_raise(), "KJo": pure_raise(), "KTo": pure_raise(),
        "QJo": pure_raise(), "QTo": pure_raise(), "JTo": pure_raise(),
        # Mixed
        "K3s": pure_raise(), "K2s": mixed(85),
        "Q4s": pure_raise(), "Q3s": mixed(80), "Q2s": mixed(55),
        "J6s": pure_raise(), "J5s": mixed(70), "J4s": mixed(40), "J3s": mixed(25),
        "T6s": mixed(75), "T5s": mixed(35),
        "96s": mixed(80), "95s": mixed(40),
        "85s": mixed(50),
        "75s": pure_raise(), "74s": mixed(35),
        "64s": mixed(75), "53s": mixed(65), "43s": mixed(85), "42s": mixed(25), "32s": mixed(40),
        "A7o": pure_raise(), "A6o": mixed(80), "A5o": pure_raise(), "A4o": mixed(70), "A3o": mixed(55), "A2o": mixed(40),
        "K9o": pure_raise(), "K8o": mixed(75), "K7o": mixed(40), "K6o": mixed(20),
        "Q9o": pure_raise(), "Q8o": mixed(50), "Q7o": mixed(20),
        "J9o": pure_raise(), "J8o": mixed(40), "J7o": mixed(15),
        "T9o": pure_raise(), "T8o": mixed(45),
        "98o": mixed(55), "97o": mixed(20), "87o": mixed(35), "76o": mixed(20),
    },
    # SB (~40% RFI - karışık limp/raise stratejisi GTOWizard'da)
    # Burada SADECE raise-first stratejisi (limp'siz, basitlik için)
    "SB": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(),
        "55": pure_raise(), "44": pure_raise(), "33": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A8s": pure_raise(),
        "A7s": pure_raise(), "A6s": pure_raise(), "A5s": pure_raise(),
        "A4s": pure_raise(), "A3s": pure_raise(), "A2s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "K9s": pure_raise(), "K8s": pure_raise(), "K7s": pure_raise(),
        "QJs": pure_raise(), "QTs": pure_raise(), "Q9s": pure_raise(), "Q8s": pure_raise(),
        "JTs": pure_raise(), "J9s": pure_raise(), "J8s": pure_raise(),
        "T9s": pure_raise(), "T8s": pure_raise(),
        "98s": pure_raise(), "97s": pure_raise(),
        "87s": pure_raise(), "86s": pure_raise(),
        "76s": pure_raise(), "65s": pure_raise(), "54s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(), "ATo": pure_raise(),
        "A9o": pure_raise(), "A8o": pure_raise(),
        "KQo": pure_raise(), "KJo": pure_raise(), "KTo": pure_raise(), "K9o": pure_raise(),
        "QJo": pure_raise(), "QTo": pure_raise(),
        "JTo": pure_raise(),
        # Mixed
        "22": mixed(85),
        "K6s": mixed(85), "K5s": mixed(75), "K4s": mixed(45), "K3s": mixed(30),
        "Q7s": mixed(70), "Q6s": mixed(45),
        "J7s": mixed(40),
        "T7s": mixed(45), "96s": mixed(45), "75s": mixed(70), "64s": mixed(50), "53s": mixed(40), "43s": mixed(45),
        "A7o": mixed(85), "A6o": mixed(75), "A5o": mixed(85), "A4o": mixed(70), "A3o": mixed(55), "A2o": mixed(35),
        "K8o": mixed(70), "K7o": mixed(35),
        "Q9o": mixed(85), "Q8o": mixed(45),
        "J9o": mixed(75), "J8o": mixed(35),
        "T9o": mixed(75), "T8o": mixed(35),
        "98o": mixed(55), "87o": mixed(30),
    },
    # BB → RFI değil. RFI durumunda BB defending pozisyonu (vs RFI senaryosu).
    # Burada placeholder — vs RFI tablosunda ele alınacak.
    "BB": {},
}


# ── vs RFI — BB DEFEND (BTN açışına karşı, 100bb) ─────────────────────
# BB her zaman zaten BB ödediği için MDF ile çok geniş defend eder.
# %52 toplam range (call ağırlıklı + biraz 3-bet).
# Bu tablo "key = defend eden pozisyon", içinde her el için
# {raise=3-bet, call=defend, fold} action.

def mixed_call(call_pct: int, raise_pct: int = 0) -> ActionFreq:
    """Call ağırlıklı mixed strategy helper."""
    fold = max(0, 100 - call_pct - raise_pct)
    return {"raise": raise_pct, "call": call_pct, "fold": fold}


VS_RFI_BB_DEFEND_100BB: dict[str, dict[str, ActionFreq]] = {
    # BB vs BTN open ~2.5x — MDF yaklaşık %52
    "vs_BTN": {
        # Pure 3-bet (linear value)
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "AKs": pure_raise(), "AKo": pure_raise(),
        # Mixed 3-bet (TT+AQ+ biraz, ayrıca polarized bluff 3-bet'ler A5s, K5s vb.)
        "TT": mixed(60, 30),                 # 60% 3-bet, 30% call
        "99": mixed(35, 50),                 # 35% 3-bet, 50% call
        "AQs": mixed(80, 15),
        "AQo": mixed(70, 20),
        "AJs": mixed(50, 45),
        "ATs": mixed(40, 55),
        "A5s": mixed(60, 30),                # polarized bluff/value
        "A4s": mixed(45, 40),
        "KQs": mixed(40, 55),
        "KJs": mixed(35, 55),
        "76s": mixed(25, 60),                # SC bluff 3-bet
        # Pure call (flat defend wide)
        "88": mixed_call(85), "77": mixed_call(85), "66": mixed_call(85),
        "55": mixed_call(85), "44": mixed_call(80), "33": mixed_call(75), "22": mixed_call(70),
        "A9s": mixed_call(90), "A8s": mixed_call(90), "A7s": mixed_call(85),
        "A6s": mixed_call(85), "A3s": mixed_call(75), "A2s": mixed_call(70),
        "KTs": mixed_call(90), "K9s": mixed_call(85), "K8s": mixed_call(75),
        "K7s": mixed_call(70), "K6s": mixed_call(60), "K5s": mixed(20, 50),  # part bluff
        "K4s": mixed_call(55), "K3s": mixed_call(45),
        "QJs": mixed_call(90), "QTs": mixed_call(85), "Q9s": mixed_call(80),
        "Q8s": mixed_call(70), "Q7s": mixed_call(55), "Q6s": mixed_call(45),
        "JTs": mixed_call(90), "J9s": mixed_call(80), "J8s": mixed_call(65), "J7s": mixed_call(50),
        "T9s": mixed_call(85), "T8s": mixed_call(75), "T7s": mixed_call(55),
        "98s": mixed_call(80), "97s": mixed_call(65), "87s": mixed_call(70),
        "86s": mixed_call(55), "65s": mixed_call(70), "75s": mixed_call(60),
        "54s": mixed_call(65), "64s": mixed_call(45), "53s": mixed_call(45), "43s": mixed_call(35),
        # Offsuit defends (daha sıkı)
        "AJo": mixed(40, 50), "ATo": mixed_call(80),
        "A9o": mixed_call(70), "A8o": mixed_call(60),
        "KQo": mixed(30, 55), "KJo": mixed_call(70),
        "KTo": mixed_call(60), "K9o": mixed_call(45),
        "QJo": mixed_call(65), "QTo": mixed_call(55), "Q9o": mixed_call(35),
        "JTo": mixed_call(60), "J9o": mixed_call(40),
        "T9o": mixed_call(45), "98o": mixed_call(35), "87o": mixed_call(25),
    },
    # BB vs CO open ~2.5x — biraz daha sıkı defend
    "vs_CO": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "AKs": pure_raise(), "AKo": pure_raise(),
        "TT": mixed(70, 25), "99": mixed(45, 45),
        "AQs": mixed(85, 12), "AQo": mixed(75, 18),
        "AJs": mixed(55, 40), "ATs": mixed(35, 55),
        "A5s": mixed(65, 25), "A4s": mixed(40, 40),
        "KQs": mixed(40, 55), "KJs": mixed(30, 60),
        "88": mixed_call(85), "77": mixed_call(85), "66": mixed_call(80),
        "55": mixed_call(75), "44": mixed_call(65), "33": mixed_call(55), "22": mixed_call(45),
        "A9s": mixed_call(85), "A8s": mixed_call(80), "A7s": mixed_call(75),
        "A6s": mixed_call(70), "A3s": mixed_call(60), "A2s": mixed_call(50),
        "KTs": mixed_call(85), "K9s": mixed_call(70),
        "K8s": mixed_call(55), "K7s": mixed_call(40), "K6s": mixed_call(30),
        "QJs": mixed_call(85), "QTs": mixed_call(75), "Q9s": mixed_call(60),
        "JTs": mixed_call(85), "J9s": mixed_call(70), "T9s": mixed_call(75),
        "T8s": mixed_call(55), "98s": mixed_call(65), "87s": mixed_call(55),
        "76s": mixed(20, 55), "65s": mixed_call(55), "54s": mixed_call(50),
        "AJo": mixed(35, 50), "ATo": mixed_call(70),
        "KQo": mixed(25, 60), "KJo": mixed_call(60),
        "KTo": mixed_call(45), "QJo": mixed_call(50), "JTo": mixed_call(40),
    },
    # ── BB vs UTG open (~18% RFI) — en sıkı opener → en sıkı defend (~38%) ─
    # UTG range güçlü olduğu için BB linear 3-bet (value) + az polarized bluff.
    # Çoğu el flat call (pot odds + position next street).
    "vs_UTG": {
        # 3-bet value (UTG'nin güçlü range'ine karşı sıkı value)
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "AKs": pure_raise(), "AKo": pure_raise(),
        "JJ": mixed(70, 25), "TT": mixed(45, 45),
        "AQs": mixed(55, 40), "AJs": mixed(30, 55),
        # 3-bet bluff (ace-blocker polarized)
        "A5s": mixed(45, 30), "A4s": mixed(35, 30),
        # Pure call — pairs + suited broadways + suited connectors
        "99": mixed_call(85), "88": mixed_call(85), "77": mixed_call(85),
        "66": mixed_call(80), "55": mixed_call(75), "44": mixed_call(60),
        "33": mixed_call(45), "22": mixed_call(40),
        "AQo": mixed_call(70), "AJo": mixed_call(45), "ATo": mixed_call(30),
        "ATs": mixed_call(80), "A9s": mixed_call(70), "A8s": mixed_call(55),
        "A7s": mixed_call(45), "A6s": mixed_call(40),
        "A3s": mixed_call(45), "A2s": mixed_call(40),
        "KQs": mixed_call(85), "KJs": mixed_call(80), "KTs": mixed_call(70),
        "K9s": mixed_call(45), "KQo": mixed_call(55), "KJo": mixed_call(30),
        "QJs": mixed_call(85), "QTs": mixed_call(75), "Q9s": mixed_call(50),
        "JTs": mixed_call(85), "J9s": mixed_call(55), "J8s": mixed_call(35),
        "T9s": mixed_call(80), "T8s": mixed_call(50),
        "98s": mixed_call(70), "97s": mixed_call(40),
        "87s": mixed_call(65), "86s": mixed_call(35),
        "76s": mixed_call(60), "65s": mixed_call(55), "54s": mixed_call(45),
    },
    # ── BB vs MP open (~22%) — biraz daha geniş defend (~42%) ─────────────
    "vs_MP": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "AKs": pure_raise(), "AKo": pure_raise(), "JJ": pure_raise(),
        "TT": mixed(60, 35), "99": mixed(35, 50),
        "AQs": mixed(65, 30), "AQo": mixed(45, 40),
        "AJs": mixed(40, 50), "ATs": mixed(20, 65),
        "KQs": mixed(30, 60), "KJs": mixed(20, 65),
        # bluff 3-bet
        "A5s": mixed(55, 25), "A4s": mixed(45, 25), "A3s": mixed(30, 30),
        # flat
        "88": mixed_call(85), "77": mixed_call(85), "66": mixed_call(80),
        "55": mixed_call(75), "44": mixed_call(65), "33": mixed_call(50), "22": mixed_call(45),
        "AJo": mixed_call(55), "ATo": mixed_call(40), "A9o": mixed_call(20),
        "A9s": mixed_call(80), "A8s": mixed_call(70), "A7s": mixed_call(60),
        "A6s": mixed_call(50), "A2s": mixed_call(45),
        "KTs": mixed_call(80), "K9s": mixed_call(60), "K8s": mixed_call(35),
        "KQo": mixed_call(60), "KJo": mixed_call(40), "KTo": mixed_call(25),
        "QJs": mixed_call(85), "QTs": mixed_call(80), "Q9s": mixed_call(60), "Q8s": mixed_call(35),
        "QJo": mixed_call(40),
        "JTs": mixed_call(85), "J9s": mixed_call(65), "J8s": mixed_call(45),
        "T9s": mixed_call(85), "T8s": mixed_call(60), "T7s": mixed_call(35),
        "98s": mixed_call(75), "97s": mixed_call(50),
        "87s": mixed_call(70), "86s": mixed_call(45),
        "76s": mixed_call(65), "75s": mixed_call(40), "65s": mixed_call(60), "54s": mixed_call(50),
    },
    # ── BB vs SB open (~40%, heads-up) — çok geniş defend (~58%) ──────────
    # SB range zayıf/geniş + BB postflop pozisyonda (SB önce konuşur) →
    # BB hem geniş 3-bet hem çok geniş flat. En geniş defend spotu.
    "vs_SB": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(), "JJ": pure_raise(),
        "AKs": pure_raise(), "AKo": pure_raise(), "AQs": pure_raise(),
        "TT": mixed(75, 22), "99": mixed(55, 38),
        "AQo": mixed(60, 32), "AJs": mixed(55, 40), "ATs": mixed(40, 52),
        "KQs": mixed(45, 50), "KJs": mixed(35, 55),
        # bluff 3-bet (geniş — SB range zayıf)
        "A5s": mixed(60, 30), "A4s": mixed(55, 30), "A3s": mixed(45, 35), "A2s": mixed(35, 40),
        "K5s": mixed(30, 40), "76s": mixed(30, 55), "65s": mixed(25, 55),
        # flat — çok geniş
        "88": mixed_call(88), "77": mixed_call(88), "66": mixed_call(85),
        "55": mixed_call(82), "44": mixed_call(75), "33": mixed_call(70), "22": mixed_call(65),
        "AJo": mixed_call(75), "ATo": mixed_call(65), "A9o": mixed_call(50), "A8o": mixed_call(40),
        "A9s": mixed_call(85), "A8s": mixed_call(80), "A7s": mixed_call(75),
        "A6s": mixed_call(70),
        "KTs": mixed_call(85), "K9s": mixed_call(75), "K8s": mixed_call(60), "K7s": mixed_call(50),
        "K6s": mixed_call(45), "K4s": mixed_call(40),
        "KQo": mixed_call(70), "KJo": mixed_call(60), "KTo": mixed_call(50), "K9o": mixed_call(35),
        "QJs": mixed_call(85), "QTs": mixed_call(82), "Q9s": mixed_call(70), "Q8s": mixed_call(55),
        "Q7s": mixed_call(40),
        "QJo": mixed_call(60), "QTo": mixed_call(45), "Q9o": mixed_call(30),
        "JTs": mixed_call(85), "J9s": mixed_call(75), "J8s": mixed_call(55), "J7s": mixed_call(35),
        "JTo": mixed_call(55), "J9o": mixed_call(35),
        "T9s": mixed_call(82), "T8s": mixed_call(65), "T7s": mixed_call(45),
        "T9o": mixed_call(45),
        "98s": mixed_call(78), "97s": mixed_call(55), "96s": mixed_call(35),
        "98o": mixed_call(30),
        "87s": mixed_call(72), "86s": mixed_call(50), "75s": mixed_call(45),
        "54s": mixed_call(60), "64s": mixed_call(40), "53s": mixed_call(40), "43s": mixed_call(35),
    },
}


# ── vs RFI — IP COLD CALL (BTN vs CO açış, 100bb) ─────────────────────
# Late-position cold call range — squeeze ekonomisi ile sıkı.
VS_RFI_BTN_VS_CO_100BB: dict[str, ActionFreq] = {
    "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
    "JJ": pure_raise(), "AKs": pure_raise(), "AKo": pure_raise(),
    "TT": mixed(85, 10),
    "99": mixed(45, 45), "88": mixed(25, 60),
    "AQs": mixed(80, 18), "AQo": mixed(55, 35),
    "AJs": mixed(30, 60), "ATs": mixed(15, 70),
    "A5s": mixed(60, 30), "A4s": mixed(50, 30),
    "KQs": mixed(25, 65), "KJs": mixed_call(75),
    "QJs": mixed_call(75), "JTs": mixed_call(75),
    "77": mixed_call(80), "66": mixed_call(70), "55": mixed_call(60), "44": mixed_call(45),
    "33": mixed_call(35), "22": mixed_call(25),
    "A9s": mixed_call(70), "A8s": mixed_call(60), "A7s": mixed_call(55),
    "KTs": mixed_call(75), "K9s": mixed_call(55),
    "QTs": mixed_call(70), "Q9s": mixed_call(45),
    "T9s": mixed_call(70), "98s": mixed_call(55), "87s": mixed_call(50), "76s": mixed(20, 45),
}


# ── vs 3-BET (BTN open → BB 3-bets → BTN 4-bet/call/fold decision) ────
# 100bb, BTN opens 2.5x, BB 3-bets to 11bb, BTN faces decision
VS_3BET_BTN_VS_BB_100BB: dict[str, ActionFreq] = {
    # Pure 4-bet value
    "AA": pure_raise(), "KK": pure_raise(),
    # Mixed value + bluff
    "QQ": mixed(75, 25),                       # 75% 4-bet, 25% call
    "JJ": mixed(20, 65),                       # mostly call
    "AKs": mixed(70, 25),
    "AKo": mixed(60, 30),
    # Pure call
    "TT": mixed_call(95), "99": mixed_call(70), "88": mixed_call(50),
    "AQs": mixed_call(85), "AQo": mixed_call(55), "AJs": mixed_call(75),
    "ATs": mixed_call(60), "KQs": mixed_call(75), "KJs": mixed_call(50),
    "QJs": mixed_call(40), "JTs": mixed_call(30),
    # Pure / mixed bluff 4-bet (polarized)
    "A5s": mixed(60, 20),                      # bluff 4bet candidate
    "A4s": mixed(45, 15),
    "A3s": mixed(30, 10),
    "K5s": mixed(20, 0),                       # rare bluff
    # Everything else: fold
}


# vs 3-bet — UTG opened (tightest opener) then faces a 3-bet.
# UTG range is already strong → continues a lot, folds bottom.
VS_3BET_UTG_100BB: dict[str, ActionFreq] = {
    "AA": pure_raise(), "KK": pure_raise(),
    "QQ": mixed(60, 38), "AKs": mixed(45, 50), "AKo": mixed(35, 50),
    # call-heavy continues
    "JJ": mixed_call(92), "TT": mixed_call(85), "99": mixed_call(55),
    "AQs": mixed_call(80), "AQo": mixed_call(45), "AJs": mixed_call(65),
    "ATs": mixed_call(45), "KQs": mixed_call(65), "KJs": mixed_call(40),
    "QJs": mixed_call(35), "JTs": mixed_call(30), "88": mixed_call(35),
    # bluff 4-bet
    "A5s": mixed(35, 10), "A4s": mixed(25, 5),
}

# vs 3-bet — MP opened then faces a 3-bet (slightly wider than UTG).
VS_3BET_MP_100BB: dict[str, ActionFreq] = {
    "AA": pure_raise(), "KK": pure_raise(),
    "QQ": mixed(65, 32), "AKs": mixed(55, 42), "AKo": mixed(45, 45),
    "JJ": mixed(20, 70), "TT": mixed_call(88), "99": mixed_call(70),
    "88": mixed_call(45),
    "AQs": mixed_call(82), "AQo": mixed_call(50), "AJs": mixed_call(70),
    "ATs": mixed_call(50), "KQs": mixed_call(70), "KJs": mixed_call(48),
    "KTs": mixed_call(30), "QJs": mixed_call(45), "QTs": mixed_call(30),
    "JTs": mixed_call(38), "T9s": mixed_call(25),
    "A5s": mixed(40, 12), "A4s": mixed(30, 8), "A3s": mixed(20, 5),
}

# vs 3-bet — CO opened then faces a 3-bet (wider — CO range looser).
VS_3BET_CO_100BB: dict[str, ActionFreq] = {
    "AA": pure_raise(), "KK": pure_raise(),
    "QQ": mixed(70, 28), "AKs": mixed(62, 35), "AKo": mixed(52, 40),
    "JJ": mixed(25, 68), "TT": mixed(15, 75), "99": mixed_call(78),
    "88": mixed_call(60), "77": mixed_call(40),
    "AQs": mixed_call(85), "AQo": mixed_call(55), "AJs": mixed_call(75),
    "ATs": mixed_call(58), "A9s": mixed_call(35),
    "KQs": mixed_call(78), "KJs": mixed_call(55), "KTs": mixed_call(38),
    "QJs": mixed_call(55), "QTs": mixed_call(40), "JTs": mixed_call(48),
    "T9s": mixed_call(38), "98s": mixed_call(28),
    "A5s": mixed(45, 15), "A4s": mixed(38, 12), "A3s": mixed(28, 8),
}

# SB vs BTN open — SB is OOP, so 3-bet-or-fold (almost no flatting).
# SB 3-bets a polarized range (value + blockers); folds the rest.
VS_RFI_SB_VS_BTN_100BB: dict[str, ActionFreq] = {
    # 3-bet value (pure)
    "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
    "JJ": pure_raise(), "AKs": pure_raise(), "AKo": pure_raise(),
    "TT": mixed(80, 0), "AQs": mixed(85, 0), "AQo": mixed(65, 0),
    "AJs": mixed(60, 0), "KQs": mixed(55, 0),
    # 3-bet bluff (blockers + suited playables)
    "A5s": mixed(70, 0), "A4s": mixed(60, 0), "A3s": mixed(45, 0), "A2s": mixed(35, 0),
    "K5s": mixed(30, 0), "K4s": mixed(25, 0),
    "76s": mixed(35, 0), "65s": mixed(35, 0), "54s": mixed(30, 0),
    "ATs": mixed(40, 0), "KJs": mixed(40, 0), "QJs": mixed(35, 0), "JTs": mixed(30, 0),
    "99": mixed(50, 0), "88": mixed(35, 0),
    # A few flats (deep, can call IP-ish vs BTN since only BB behind)
    "AJo": mixed(30, 0), "KQo": mixed(35, 0),
    # everything else fold
}


# ── PUSH/FOLD 15bb MTT ─────────────────────────────────────────────────
# Nash chart yaklaşımı — sadece all-in veya fold.
# Pozisyon × hand → all-in (raise) vs fold.
PUSH_FOLD_15BB_BTN: dict[str, ActionFreq] = {
    "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(), "JJ": pure_raise(),
    "TT": pure_raise(), "99": pure_raise(), "88": pure_raise(), "77": pure_raise(),
    "66": pure_raise(), "55": pure_raise(), "44": pure_raise(), "33": pure_raise(),
    "22": mixed(85, 0),
    "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(), "ATs": pure_raise(),
    "A9s": pure_raise(), "A8s": pure_raise(), "A7s": pure_raise(),
    "A6s": pure_raise(), "A5s": pure_raise(), "A4s": pure_raise(),
    "A3s": pure_raise(), "A2s": pure_raise(),
    "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(), "ATo": pure_raise(),
    "A9o": pure_raise(), "A8o": pure_raise(), "A7o": mixed(80, 0), "A6o": mixed(70, 0),
    "A5o": pure_raise(), "A4o": mixed(70, 0), "A3o": mixed(60, 0), "A2o": mixed(50, 0),
    "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
    "K9s": pure_raise(), "K8s": pure_raise(), "K7s": pure_raise(),
    "K6s": pure_raise(), "K5s": mixed(80, 0), "K4s": mixed(60, 0),
    "KQo": pure_raise(), "KJo": pure_raise(), "KTo": pure_raise(),
    "K9o": pure_raise(), "K8o": mixed(70, 0),
    "QJs": pure_raise(), "QTs": pure_raise(), "Q9s": pure_raise(), "Q8s": pure_raise(),
    "QJo": pure_raise(), "QTo": pure_raise(), "Q9o": mixed(70, 0),
    "JTs": pure_raise(), "J9s": pure_raise(), "J8s": pure_raise(),
    "JTo": pure_raise(), "J9o": mixed(60, 0),
    "T9s": pure_raise(), "T8s": pure_raise(),
    "T9o": mixed(70, 0),
    "98s": pure_raise(), "97s": mixed(75, 0),
    "87s": pure_raise(), "76s": pure_raise(), "65s": mixed(85, 0), "54s": mixed(75, 0),
}


# ── DEFAULT FALLBACK (catch-all) ───────────────────────────────────────
# Tabloda eksik olan eller pure_fold() varsayar.

# ── CURATED COVERAGE MAP ──────────────────────────────────────────────
# Hangi (scenario, position, vs_position) kombinasyonları manuel olarak
# curated chart ile kaplanmış? Bunların dışındaki HER spot heuristic
# generator'a düşer (gto_generator.py) → %100 kapsama.

def _is_curated(scenario: str, position: str, stack_depth: int,
                vs_position: str | None) -> bool:
    """Hangi spotlar için curated chart kullanılır?

    DOMAIN-BAĞIMLI KARAR (kör "hepsini aç/kapat" değil):

    • RFI, Push/Fold → curated EXACT (doğrulandı, doğru).

    • vs-RFI (BB defend) → curated DEVRE DIŞI. Bu GENİŞ bir domain
      (BB savunması doğru oynayışta %30-50 olmalı). Elle yazılan curated
      sistematik olarak çok SIKI çıktı (BB vs UTG %14 vs gerçek ~%38).
      Heuristic generator daha doğru aggregate üretiyor (%31 / %51). →
      heuristic kullan.

    • vs-3bet → curated AKTİF (BTN/UTG/MP/CO, cash, ≥60bb). Bu POLARİZE
      bir domain (çoğu el fold; devam edenler value-4bet / flat / bluff-4bet
      olarak ayrışır). Heuristic burada SHAPE'i tamamen yanlış üretiyordu:
      TT/99/AQs/KQs ile %100 4-bet (flat YOK), A5s gibi blocker bluff-4bet
      ellerini %100 fold ediyordu — ders olarak ZARARLI. Curated tablolar
      ders-kitabı şeklinde (pure value, mixed, geniş flat, polarize bluff).
      Aggregate biraz sıkı olsa da SHAPE doğru → curated kullan (APPROX tier).
    """
    if scenario == "RFI" and stack_depth >= 60:
        return position in RFI_100BB_6MAX
    if scenario == "Push/Fold":
        return position in ("BTN", "SB") and 12 <= stack_depth <= 18
    if scenario == "vs 3-bet" and stack_depth >= 60:
        return position in ("BTN", "UTG", "MP", "CO")
    # vs RFI (BB defend) → heuristic (daha doğru, aşağıda fallback eder)
    return False


def get_action(position: str, hand_key: str, scenario: str = "RFI",
               stack_depth: int = 100, mode: str = "cash",
               vs_position: str | None = None) -> ActionFreq:
    """Ana lookup API.

    Curated chart varsa onu kullanır (pro-grade public konsensus, ~%95).
    Yoksa heuristic GTO generator'a düşer (gto_generator, ~%75-80) →
    böylece HER (position × scenario × stack × vs_position) kombinasyonu
    tutarlı bir cevap döner. Hiçbir spot 'boş' kalmaz.

    scenario:
      "RFI"        — açış (opener)
      "vs RFI"     — açışa karşı (defender)
      "vs 3-bet"   — 3-bet'e karşı 4-bet defense
      "Push/Fold"  — kısa stack jam/fold
      "Call vs Jam"— jam'a karşı call (MTT)

    mode="MTT" → ante-aware, stack-depth-shaped, Nash push/fold
    (app/poker/mtt_ranges.py). mode="cash" → curated + heuristic.
    """
    # ── MTT MODE → dedicated ante/Nash engine ──────────────────────────
    if mode == "MTT":
        try:
            from app.poker.mtt_ranges import mtt_get_action
            return mtt_get_action(position, hand_key, scenario,
                                  stack_depth, vs_position)
        except Exception:
            pass   # fall through to cash logic on any error

    # ── CURATED LOOKUP (varsa) ─────────────────────────────────────────
    if _is_curated(scenario, position, stack_depth, vs_position):
        if scenario == "RFI":
            if position == "BB":
                # BB'nin curated açış range'i YOK (RFI_100BB_6MAX'te yok) → eski
                # davranış her eli pure_fold yapardı (AA bile fold!). BB preflop
                # son oynayan: folded-to kazanır, limp'lenen pot ise iso-raise
                # opsiyonu. Heuristic'e düş → premium iso (~top %16), MTT ile uyumlu.
                from app.poker.gto_generator import heuristic_get_action
                return heuristic_get_action(position, hand_key, scenario,
                                            stack_depth, mode, vs_position)
            return RFI_100BB_6MAX.get(position, {}).get(hand_key, pure_fold())
        if scenario == "vs RFI":
            if position == "BB":
                opener = vs_position or "BTN"
                sub = VS_RFI_BB_DEFEND_100BB.get(f"vs_{opener}", {})
                return sub.get(hand_key, pure_fold())
            if position == "BTN" and vs_position == "CO":
                return VS_RFI_BTN_VS_CO_100BB.get(hand_key, pure_fold())
            if position == "SB" and vs_position == "BTN":
                return VS_RFI_SB_VS_BTN_100BB.get(hand_key, pure_fold())
        if scenario == "vs 3-bet":
            _vs3 = {
                "BTN": VS_3BET_BTN_VS_BB_100BB,
                "UTG": VS_3BET_UTG_100BB,
                "MP": VS_3BET_MP_100BB,
                "CO": VS_3BET_CO_100BB,
            }
            return _vs3.get(position, {}).get(hand_key, pure_fold())
        if scenario == "Push/Fold":
            if position == "BTN":
                return PUSH_FOLD_15BB_BTN.get(hand_key, pure_fold())
            if position == "SB":
                base = PUSH_FOLD_15BB_BTN.get(hand_key, pure_fold())
                r = max(0, base["raise"] - 15)
                return {"raise": r, "call": 0, "fold": 100 - r}

    # ── HEURISTIC FALLBACK (kapsanmayan tüm spotlar) ───────────────────
    try:
        from app.poker.gto_generator import heuristic_get_action
        return heuristic_get_action(
            position, hand_key, scenario, stack_depth, mode, vs_position
        )
    except Exception:
        return pure_fold()


# ── BACKWARDS COMPAT (eski range_grid.py demo_frequency için) ─────────

def demo_frequency(hand: str, mode: str = "BTN RFI") -> int:
    """Eski API — yeni datadan tek frequency (raise %) döndürür."""
    # mode "BTN RFI" gibi → pozisyon ve scenario ayrıştır
    if " " in mode:
        pos, scen = mode.split(maxsplit=1)
    else:
        pos, scen = "BTN", mode
    pos = pos.upper()
    if pos in ("UTG", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB"):
        if pos == "LJ":
            pos = "MP"
        if pos == "HJ":
            pos = "CO"
        action = get_action(pos, hand, "RFI")
        return action.get("raise", 0)
    return 0


def range_matrix() -> List[List[str]]:
    """13×13 grid sırası — eski API."""
    grid: List[List[str]] = []
    for row, hi in enumerate(RANKS_DESC):
        line: List[str] = []
        for col, lo in enumerate(RANKS_DESC):
            if row == col:
                line.append(hi + lo)
            elif row < col:
                line.append(hi + lo + "s")
            else:
                line.append(lo + hi + "o")
        grid.append(line)
    return grid


# ── POSITION & SCENARIO ENUMS ──────────────────────────────────────────

POSITIONS_6MAX = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
POSITIONS_8MAX = ["UTG", "UTG+1", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
SCENARIOS = ["RFI", "vs RFI", "vs 3-bet", "Push/Fold"]
STACK_DEPTHS = [100, 60, 40, 20]   # bb
MODES = ["cash", "MTT"]
