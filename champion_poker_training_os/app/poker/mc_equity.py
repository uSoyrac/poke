"""Monte Carlo Equity Calculator — pure Python, no deps.

Range vs Range (or Range vs Hand) equity calculation on any board state
(0-5 community cards). Used by:
  - Quiz mode → "Senin equity'in %47'ydi, fold doğruydu"
  - Hand History → "Bu eli %38 equity ile call'ladın, kötü call"
  - GTO chart → range vs popular defend range visualization
  - Bot AI → equity-aware decision making

Algorithm (Monte Carlo simulation):
  For N iterations:
    1. Draw random hand from Range A (excluding board)
    2. Draw random hand from Range B (excluding board + A)
    3. Draw remaining community cards to complete 5
    4. Evaluate both hands → compare → win/tie/loss
  Return: (a_win_pct, tie_pct, b_win_pct)

10K iterations → ~±1% precision in 0.3-1.0 seconds.

Mevcut app/poker/equity.py (preflop lookup) korunur — bu Monte Carlo
ek bir API katmanıdır. İlham: dickreuter/Poker'ın MC fikri + fedden/poker_ai
abstraction prensipleri. Kod tamamen yeniden yazıldı (GPL kontaminasyon
yok). Standart MC algoritması — yasal.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, RANKS, SUITS


# ── HAND KEY → CONCRETE COMBOS ────────────────────────────────────────

def expand_hand_key(hand_key: str) -> List[Tuple[Card, Card]]:
    """Convert 'AKs' / 'QJo' / '77' to all concrete (Card, Card) pairs."""
    if not hand_key or len(hand_key) < 2:
        return []
    r1, r2 = hand_key[0].upper(), hand_key[1].upper()
    if r1 not in RANKS or r2 not in RANKS:
        return []

    combos: List[Tuple[Card, Card]] = []
    if len(hand_key) == 2:
        # Pair (e.g. "AA") — only if both ranks are the same
        if r1 != r2:
            # "AK" is ambiguous (suited or offsuit?). Require explicit s/o suffix.
            return []
        # Pair: 4C2 = 6 combos
        for i, s1 in enumerate(SUITS):
            for s2 in SUITS[i + 1:]:
                combos.append((Card(r1, s1), Card(r1, s2)))
    elif hand_key.endswith("s"):
        # Suited: 4 combos
        for s in SUITS:
            combos.append((Card(r1, s), Card(r2, s)))
    else:
        # Offsuit: 12 combos
        for s1 in SUITS:
            for s2 in SUITS:
                if s1 != s2:
                    combos.append((Card(r1, s1), Card(r2, s2)))
    return combos


def expand_range(hand_keys: List[str]) -> List[Tuple[Card, Card]]:
    out: List[Tuple[Card, Card]] = []
    for hk in hand_keys:
        out.extend(expand_hand_key(hk))
    return out


# ── DECK ──────────────────────────────────────────────────────────────

def _make_deck() -> List[Card]:
    return [Card(r, s) for r in RANKS for s in SUITS]


# ── EQUITY RESULT ─────────────────────────────────────────────────────

@dataclass
class EquityResult:
    a_win_pct: float
    tie_pct: float
    b_win_pct: float
    iterations: int          # valid iterations (after collision skips)
    elapsed_ms: int

    @property
    def a_equity(self) -> float:
        """A'nın beklenen equity'i (wins + half-ties)."""
        return self.a_win_pct + self.tie_pct / 2

    @property
    def b_equity(self) -> float:
        return self.b_win_pct + self.tie_pct / 2

    def __repr__(self) -> str:
        return (f"EquityResult(A={self.a_equity:.1f}%, "
                f"B={self.b_equity:.1f}%, "
                f"iters={self.iterations}, "
                f"{self.elapsed_ms}ms)")


# ── MONTE CARLO SIMULATION ────────────────────────────────────────────

def calculate_equity(
    range_a,
    range_b,
    board: Optional[List[Card]] = None,
    iterations: int = 10000,
    seed: Optional[int] = None,
) -> EquityResult:
    """Compute A vs B equity via Monte Carlo simulation.

    range_a / range_b:
      List of (Card, Card) tuples OR list of hand_key strings.

    board: 0-5 Card objects.

    iterations: 10K = ~1% precision in 0.3-1.0s.
    """
    t0 = time.time()
    rng = random.Random(seed) if seed is not None else random

    # Expand if strings
    if range_a and isinstance(range_a[0], str):
        range_a = expand_range(range_a)
    if range_b and isinstance(range_b[0], str):
        range_b = expand_range(range_b)

    if not range_a or not range_b:
        return EquityResult(0.0, 0.0, 0.0, 0,
                            int((time.time() - t0) * 1000))

    board = list(board) if board else []
    board_set: Set[Tuple[str, str]] = {(c.rank, c.suit) for c in board}
    full_deck = _make_deck()
    remaining_pool = [c for c in full_deck if (c.rank, c.suit) not in board_set]
    cards_needed = 5 - len(board)

    a_wins = 0
    ties = 0
    b_wins = 0
    valid = 0

    for _ in range(iterations):
        # 1) Draw hand from A
        ha = rng.choice(range_a)
        ha_codes = {(ha[0].rank, ha[0].suit), (ha[1].rank, ha[1].suit)}
        if ha_codes & board_set:
            continue

        # 2) Draw hand from B (no collision with board or A)
        hb = None
        for _attempt in range(8):
            cand = rng.choice(range_b)
            cand_codes = {(cand[0].rank, cand[0].suit),
                          (cand[1].rank, cand[1].suit)}
            if not (cand_codes & board_set) and not (cand_codes & ha_codes):
                hb = cand
                break
        if hb is None:
            continue
        hb_codes = {(hb[0].rank, hb[0].suit), (hb[1].rank, hb[1].suit)}

        # 3) Complete board with random remaining cards
        if cards_needed > 0:
            available = [c for c in remaining_pool
                         if (c.rank, c.suit) not in ha_codes
                         and (c.rank, c.suit) not in hb_codes]
            if len(available) < cards_needed:
                continue
            runout = rng.sample(available, cards_needed)
            full_board = board + runout
        else:
            full_board = board

        # 4) Evaluate
        a_eval = evaluate_best_hand(list(ha), full_board)
        b_eval = evaluate_best_hand(list(hb), full_board)
        cmp = _compare_hands(a_eval, b_eval)

        valid += 1
        if cmp < 0:
            a_wins += 1
        elif cmp > 0:
            b_wins += 1
        else:
            ties += 1

    elapsed = int((time.time() - t0) * 1000)
    if valid == 0:
        return EquityResult(0.0, 0.0, 0.0, 0, elapsed)

    return EquityResult(
        a_win_pct=round(100 * a_wins / valid, 2),
        tie_pct=round(100 * ties / valid, 2),
        b_win_pct=round(100 * b_wins / valid, 2),
        iterations=valid,
        elapsed_ms=elapsed,
    )


# ── CONVENIENCE WRAPPERS ──────────────────────────────────────────────

def equity_hand_vs_hand(
    hand_a: str,     # e.g. "AsKs" or "As Ks"
    hand_b: str,
    board: str = "",
    iterations: int = 10000,
) -> EquityResult:
    """Single hand vs single hand."""
    from app.engine.hand_state import cards_from_str
    ca = cards_from_str(hand_a)
    cb = cards_from_str(hand_b)
    bd = cards_from_str(board) if board else []
    return calculate_equity([(ca[0], ca[1])], [(cb[0], cb[1])],
                            board=bd, iterations=iterations)


def equity_hand_vs_range(
    hand: str,
    range_keys: List[str],
    board: str = "",
    iterations: int = 10000,
) -> EquityResult:
    from app.engine.hand_state import cards_from_str
    ca = cards_from_str(hand)
    bd = cards_from_str(board) if board else []
    return calculate_equity(
        [(ca[0], ca[1])],
        expand_range(range_keys),
        board=bd, iterations=iterations,
    )


def equity_range_vs_range(
    range_a_keys: List[str],
    range_b_keys: List[str],
    board: str = "",
    iterations: int = 10000,
) -> EquityResult:
    from app.engine.hand_state import cards_from_str
    bd = cards_from_str(board) if board else []
    return calculate_equity(
        expand_range(range_a_keys),
        expand_range(range_b_keys),
        board=bd, iterations=iterations,
    )


# ── RANGE FROM GTO TABLE ──────────────────────────────────────────────

def gto_range_for(position: str, scenario: str = "RFI",
                   stack_depth: int = 100, mode: str = "cash",
                   threshold_pct: int = 10,
                   include_call: bool = True) -> List[str]:
    """Pull the open/defend range from gto_ranges as a list of hand keys.

    threshold_pct: include hands where raise + (call if include_call) > N%
    """
    from app.poker.gto_ranges import all_hand_keys, get_action
    out: List[str] = []
    for hk in all_hand_keys():
        a = get_action(position, hk, scenario, stack_depth, mode)
        score = a.get("raise", 0) + (a.get("call", 0) if include_call else 0)
        if score > threshold_pct:
            out.append(hk)
    return out
