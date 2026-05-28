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
        "88": pure_raise(), "77": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A5s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "QJs": pure_raise(), "JTs": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(),
        # Mixed (kısmi açış)
        "66": mixed(80), "55": mixed(40), "44": mixed(20), "33": mixed(15), "22": mixed(15),
        "A8s": mixed(75), "A7s": mixed(60), "A6s": mixed(55),
        "A4s": mixed(80), "A3s": mixed(75), "A2s": mixed(65),
        "K9s": mixed(40),
        "Q9s": mixed(15),
        "T9s": mixed(70), "98s": mixed(45), "87s": mixed(35), "76s": mixed(45), "65s": mixed(35), "54s": mixed(20),
        "AJo": mixed(75), "ATo": mixed(20),
        "KQo": mixed(50), "KJo": mixed(10),
    },
    # MP / LJ (~21% RFI)
    "MP": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(), "55": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A8s": pure_raise(), "A5s": pure_raise(), "A4s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "QJs": pure_raise(), "QTs": pure_raise(), "JTs": pure_raise(), "T9s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(),
        # Mixed
        "44": mixed(75), "33": mixed(40), "22": mixed(35),
        "A7s": mixed(85), "A6s": mixed(70), "A3s": mixed(85), "A2s": mixed(75),
        "K9s": mixed(70), "K8s": mixed(20),
        "Q9s": mixed(45), "J9s": mixed(30),
        "98s": mixed(75), "87s": mixed(60), "76s": mixed(70), "65s": mixed(60), "54s": mixed(45),
        "ATo": mixed(70), "KQo": mixed(85), "KJo": mixed(45), "QJo": mixed(20),
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
        "33": mixed(85), "22": mixed(70),
        "K8s": mixed(85), "K7s": mixed(55), "K6s": mixed(40), "K5s": mixed(35),
        "Q8s": mixed(70), "J8s": mixed(45), "T8s": mixed(50),
        "54s": mixed(70), "43s": mixed(30),
        "KTo": mixed(75), "QJo": mixed(60), "JTo": mixed(35),
        "A9o": mixed(20),
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
        "K3s": mixed(85), "K2s": mixed(60),
        "Q4s": mixed(85), "Q3s": mixed(55), "Q2s": mixed(35),
        "J6s": mixed(60), "J5s": mixed(35),
        "T6s": mixed(50),
        "96s": mixed(55), "75s": mixed(70), "64s": mixed(40), "53s": mixed(35), "43s": mixed(60), "32s": mixed(15),
        "A7o": mixed(85), "A6o": mixed(60), "A5o": mixed(75), "A4o": mixed(50), "A3o": mixed(35), "A2o": mixed(20),
        "K9o": mixed(85), "K8o": mixed(50), "K7o": mixed(20),
        "Q9o": mixed(70), "Q8o": mixed(25),
        "J9o": mixed(60), "J8o": mixed(15),
        "T9o": mixed(60), "T8o": mixed(20),
        "98o": mixed(30), "87o": mixed(15),
    },
    # SB (~40% RFI - karışık limp/raise stratejisi GTOWizard'da)
    # Burada SADECE raise-first stratejisi (limp'siz, basitlik için)
    "SB": {
        "AA": pure_raise(), "KK": pure_raise(), "QQ": pure_raise(),
        "JJ": pure_raise(), "TT": pure_raise(), "99": pure_raise(),
        "88": pure_raise(), "77": pure_raise(), "66": pure_raise(),
        "55": pure_raise(), "44": pure_raise(),
        "AKs": pure_raise(), "AQs": pure_raise(), "AJs": pure_raise(),
        "ATs": pure_raise(), "A9s": pure_raise(), "A8s": pure_raise(),
        "A7s": pure_raise(), "A6s": pure_raise(), "A5s": pure_raise(),
        "A4s": pure_raise(), "A3s": pure_raise(), "A2s": pure_raise(),
        "KQs": pure_raise(), "KJs": pure_raise(), "KTs": pure_raise(),
        "K9s": pure_raise(), "K8s": pure_raise(),
        "QJs": pure_raise(), "QTs": pure_raise(), "Q9s": pure_raise(),
        "JTs": pure_raise(), "J9s": pure_raise(),
        "T9s": pure_raise(), "98s": pure_raise(), "87s": pure_raise(),
        "76s": pure_raise(), "65s": pure_raise(), "54s": pure_raise(),
        "AKo": pure_raise(), "AQo": pure_raise(), "AJo": pure_raise(), "ATo": pure_raise(),
        "KQo": pure_raise(), "KJo": pure_raise(), "KTo": pure_raise(),
        "QJo": pure_raise(),
        # Mixed
        "33": mixed(80), "22": mixed(65),
        "K7s": mixed(75), "K6s": mixed(60), "K5s": mixed(55),
        "Q8s": mixed(70), "Q7s": mixed(40),
        "J8s": mixed(70), "T8s": mixed(60), "97s": mixed(50), "86s": mixed(35), "75s": mixed(40), "64s": mixed(25),
        "A9o": mixed(85), "A8o": mixed(70), "A7o": mixed(55), "A5o": mixed(70), "A4o": mixed(40), "A3o": mixed(20),
        "K9o": mixed(75), "K8o": mixed(40),
        "Q9o": mixed(55), "J9o": mixed(45), "T9o": mixed(40), "98o": mixed(20),
        "JTo": mixed(75),
    },
    # BB → RFI değil. RFI durumunda BB defending pozisyonu (vs RFI senaryosu).
    # Burada placeholder — vs RFI tablosunda ele alınacak.
    "BB": {},
}


# ── DEFAULT FALLBACK (catch-all) ───────────────────────────────────────
# Tabloda eksik olan eller pure_fold() varsayar.

def get_action(position: str, hand_key: str, scenario: str = "RFI",
               stack_depth: int = 100, mode: str = "cash") -> ActionFreq:
    """Ana lookup API. Tabloda yoksa pure_fold döner."""
    if scenario == "RFI":
        if stack_depth == 100 and mode == "cash":
            table = RFI_100BB_6MAX.get(position, {})
            return table.get(hand_key, pure_fold())
    # TODO: vs_RFI, vs_3bet, push/fold, MTT 40bb, 20bb senaryoları
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
