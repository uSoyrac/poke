"""Minimal River Solver — Discounted CFR for heads-up river decisions.

Game tree (heads-up, hero first to act):
    Hero: BET B or CHECK
      if BET:
        Villain: CALL or FOLD
          CALL → showdown (winner takes pot + 2B)
          FOLD → hero wins pot
      if CHECK:
        Villain: BET B or CHECK
          if BET:
            Hero: CALL or FOLD
              CALL → showdown
              FOLD → villain wins pot
          if CHECK → showdown

Information sets:
    - Hero acting first (1 per hero hand)
    - Villain facing hero bet (1 per villain hand)
    - Villain acting after check (1 per villain hand)
    - Hero facing villain bet after check (1 per hero hand)

Algorithm: Vanilla CFR with regret-matching (Discounted CFR optimization
left out for v1 — adds complexity, marginal benefit on river-only tree).

Convergence: 1000 iterations → strategies stabilize for small ranges.
Performance: O(iters × |hero_range| × |villain_range|) evaluations.
20-hand ranges × 1000 iter = 400K evaluations ≈ 5-10 seconds.

Algorithm sourced from public CFR literature (Zinkevich et al. 2007,
"Regret Minimization in Games with Incomplete Information"). Implementation
written from scratch — no AGPL/GPL code reuse.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, cards_from_str
from app.poker.mc_equity import expand_range


# ── ACTIONS ───────────────────────────────────────────────────────────
BET = "bet"
CHECK = "check"
CALL = "call"
FOLD = "fold"

# Info set keys (player-action context)
HERO_FIRST = "hero_first"        # Hero acts first → BET / CHECK
VILL_VS_BET = "vill_vs_bet"      # Villain facing hero's bet → CALL / FOLD
VILL_AFTER_CHK = "vill_after_chk"  # Villain after hero check → BET / CHECK
HERO_VS_BET = "hero_vs_bet"      # Hero facing villain's bet → CALL / FOLD


# ── STRATEGY RESULT ───────────────────────────────────────────────────

@dataclass
class HandStrategy:
    """Per-hand strategy in each info set."""
    hand_label: str           # e.g. "AsKs"
    # Hero
    bet_freq: float = 0.0     # %
    check_freq: float = 0.0
    # Hero facing bet (after villain bets a check-back)
    call_freq_vs_bet: float = 0.0
    fold_freq_vs_bet: float = 0.0
    # Villain facing hero bet
    v_call_freq: float = 0.0
    v_fold_freq: float = 0.0
    # Villain after check
    v_bet_freq: float = 0.0
    v_check_freq: float = 0.0


@dataclass
class SolverResult:
    hero_strategies: List[HandStrategy]
    villain_strategies: List[HandStrategy]
    iterations: int
    elapsed_ms: int
    hero_ev: float            # average hero EV per hand combo
    villain_ev: float

    def hero_dominant(self) -> List[Tuple[str, str, float]]:
        """[(hand, dominant action, freq), ...]"""
        out = []
        for s in self.hero_strategies:
            if s.bet_freq >= s.check_freq:
                out.append((s.hand_label, "BET", s.bet_freq))
            else:
                out.append((s.hand_label, "CHECK", s.check_freq))
        return out


# ── SOLVER ────────────────────────────────────────────────────────────

class RiverSolver:
    """Heads-up river CFR solver."""

    def __init__(
        self,
        hero_range,                # list of hand keys or (Card, Card) tuples
        villain_range,
        board: List[Card] | str,
        pot: float = 100.0,
        bet_size_frac: float = 0.75,  # bet = 75% of pot
    ):
        # Expand ranges if strings
        if hero_range and isinstance(hero_range[0], str):
            hero_range = expand_range(hero_range)
        if villain_range and isinstance(villain_range[0], str):
            villain_range = expand_range(villain_range)

        if isinstance(board, str):
            board = cards_from_str(board)

        self.hero_range = hero_range
        self.villain_range = villain_range
        self.board = board
        self.pot = pot
        self.bet_size = pot * bet_size_frac
        # Total pot after both bet = pot + 2*bet
        self.showdown_pot_after_bet = pot + 2 * self.bet_size
        self.showdown_pot_no_bet = pot

        # Pre-evaluate all hand strengths on this board (cached for speed)
        self.hero_ranks: Dict[int, Tuple[int, List[int], str]] = {}
        for i, (c1, c2) in enumerate(hero_range):
            self.hero_ranks[i] = evaluate_best_hand([c1, c2], board)
        self.villain_ranks: Dict[int, Tuple[int, List[int], str]] = {}
        for j, (c1, c2) in enumerate(villain_range):
            self.villain_ranks[j] = evaluate_best_hand([c1, c2], board)

        # Pre-compute hand collision matrix: hero hand i vs villain hand j
        # → True if they share a card (this combo pair is impossible)
        self.collision: List[List[bool]] = []
        for i, (h1, h2) in enumerate(hero_range):
            row = []
            h_codes = {(h1.rank, h1.suit), (h2.rank, h2.suit)}
            for j, (v1, v2) in enumerate(villain_range):
                v_codes = {(v1.rank, v1.suit), (v2.rank, v2.suit)}
                row.append(bool(h_codes & v_codes))
            self.collision.append(row)

        # CFR state — regret and strategy tables
        # Key: (info_set, hand_idx) → {action: regret_sum}
        self.regret_sum: Dict[Tuple[str, int], Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        # Average strategy accumulator
        self.strategy_sum: Dict[Tuple[str, int], Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )

    # ── REGRET MATCHING ───────────────────────────────────────────────
    def get_strategy(self, info_set: str, hand_idx: int,
                     actions: List[str]) -> Dict[str, float]:
        """Compute current strategy via regret-matching (positive regrets only)."""
        key = (info_set, hand_idx)
        regrets = self.regret_sum[key]
        positive = {a: max(0.0, regrets[a]) for a in actions}
        total = sum(positive.values())
        if total > 0:
            return {a: positive[a] / total for a in actions}
        # Uniform if all regrets ≤ 0
        return {a: 1.0 / len(actions) for a in actions}

    def get_average_strategy(self, info_set: str, hand_idx: int,
                              actions: List[str]) -> Dict[str, float]:
        key = (info_set, hand_idx)
        sums = self.strategy_sum[key]
        total = sum(sums.get(a, 0.0) for a in actions)
        if total > 0:
            return {a: sums.get(a, 0.0) / total for a in actions}
        return {a: 1.0 / len(actions) for a in actions}

    # ── SHOWDOWN ──────────────────────────────────────────────────────
    def _showdown_value(self, h_idx: int, v_idx: int, pot_size: float,
                        hero_paid: float, villain_paid: float) -> Tuple[float, float]:
        """Return (hero_ev, villain_ev) from showdown.

        EV is from the perspective of net change from the start of the river
        (i.e., not counting prior street investments — only the river bet).
        """
        cmp = _compare_hands(self.hero_ranks[h_idx], self.villain_ranks[v_idx])
        if cmp < 0:        # hero wins
            return (pot_size - hero_paid, -villain_paid)
        if cmp > 0:        # villain wins
            return (-hero_paid, pot_size - villain_paid)
        # Tie
        half = pot_size / 2
        return (half - hero_paid, half - villain_paid)

    # ── GAME TREE EV ──────────────────────────────────────────────────
    def _terminal_ev_hero_bets_v_folds(self) -> Tuple[float, float]:
        """Hero bets, villain folds → hero wins pot (no risk on the bet)."""
        return (self.pot, 0.0)

    def _terminal_ev_hero_checks_v_checks(self, h: int, v: int) -> Tuple[float, float]:
        """Both check → showdown for pot only."""
        return self._showdown_value(h, v, self.pot, 0.0, 0.0)

    def _terminal_ev_hero_bets_v_calls(self, h: int, v: int) -> Tuple[float, float]:
        """Hero bets, villain calls → showdown with both paying B."""
        return self._showdown_value(
            h, v, self.showdown_pot_after_bet,
            self.bet_size, self.bet_size,
        )

    def _terminal_ev_hero_chks_v_bets_h_folds(self) -> Tuple[float, float]:
        """Hero checks, villain bets, hero folds → villain wins pot."""
        return (0.0, self.pot)

    def _terminal_ev_hero_chks_v_bets_h_calls(self, h: int, v: int) -> Tuple[float, float]:
        """Hero checks, villain bets B, hero calls → showdown."""
        return self._showdown_value(
            h, v, self.showdown_pot_after_bet,
            self.bet_size, self.bet_size,
        )

    # ── CFR ITERATION ─────────────────────────────────────────────────
    def _train_iteration(self) -> None:
        """One CFR iteration over all hero × villain combos."""
        n_h = len(self.hero_range)
        n_v = len(self.villain_range)

        # Strategies for this iteration (per hand)
        hero_first_strat = [
            self.get_strategy(HERO_FIRST, h, [BET, CHECK])
            for h in range(n_h)
        ]
        vill_vs_bet_strat = [
            self.get_strategy(VILL_VS_BET, v, [CALL, FOLD])
            for v in range(n_v)
        ]
        vill_after_chk_strat = [
            self.get_strategy(VILL_AFTER_CHK, v, [BET, CHECK])
            for v in range(n_v)
        ]
        hero_vs_bet_strat = [
            self.get_strategy(HERO_VS_BET, h, [CALL, FOLD])
            for h in range(n_h)
        ]

        # ── HERO ACTING FIRST ──────────────────────────────────────────
        # For each hero hand, compute counterfactual value of each action
        # by integrating over the villain's range (weighted by 1/n_v).
        for h in range(n_h):
            # Expected utility if hero BETS this hand
            ev_bet = 0.0
            ev_check = 0.0
            valid_villains = 0
            for v in range(n_v):
                if self.collision[h][v]:
                    continue
                valid_villains += 1
                # Hero bets: villain calls or folds with v's mixed strategy
                vs_strat = vill_vs_bet_strat[v]
                hero_ev_v_call, _ = self._terminal_ev_hero_bets_v_calls(h, v)
                hero_ev_v_fold = self._terminal_ev_hero_bets_v_folds()[0]
                ev_bet += vs_strat[CALL] * hero_ev_v_call + vs_strat[FOLD] * hero_ev_v_fold

                # Hero checks: villain bets or checks
                vc_strat = vill_after_chk_strat[v]
                # If villain bets, hero plays HERO_VS_BET strategy
                hvb = hero_vs_bet_strat[h]
                hero_ev_vbet_call, _ = self._terminal_ev_hero_chks_v_bets_h_calls(h, v)
                hero_ev_vbet_fold = self._terminal_ev_hero_chks_v_bets_h_folds()[0]
                ev_after_vbet = hvb[CALL] * hero_ev_vbet_call + hvb[FOLD] * hero_ev_vbet_fold
                # If villain checks, showdown
                hero_ev_vchk, _ = self._terminal_ev_hero_checks_v_checks(h, v)
                ev_check += vc_strat[BET] * ev_after_vbet + vc_strat[CHECK] * hero_ev_vchk

            if valid_villains == 0:
                continue
            ev_bet /= valid_villains
            ev_check /= valid_villains

            # Update regrets
            strat = hero_first_strat[h]
            node_value = strat[BET] * ev_bet + strat[CHECK] * ev_check
            self.regret_sum[(HERO_FIRST, h)][BET] += ev_bet - node_value
            self.regret_sum[(HERO_FIRST, h)][CHECK] += ev_check - node_value
            # Average strategy accumulator
            self.strategy_sum[(HERO_FIRST, h)][BET] += strat[BET]
            self.strategy_sum[(HERO_FIRST, h)][CHECK] += strat[CHECK]

        # ── VILLAIN VS HERO BET ────────────────────────────────────────
        for v in range(n_v):
            ev_call = 0.0
            ev_fold = 0.0
            valid_heroes = 0
            for h in range(n_h):
                if self.collision[h][v]:
                    continue
                # Weight by probability that hero would have bet this hand
                w = hero_first_strat[h][BET]
                if w <= 0:
                    continue
                valid_heroes += w
                # Villain calls: showdown with B in (villain pays B)
                _, vc_call = self._terminal_ev_hero_bets_v_calls(h, v)
                ev_call += w * vc_call
                # Villain folds: villain pays 0 (just loses the pot)
                _, vc_fold = self._terminal_ev_hero_bets_v_folds()
                ev_fold += w * vc_fold

            if valid_heroes <= 0:
                continue
            ev_call /= valid_heroes
            ev_fold /= valid_heroes

            strat = vill_vs_bet_strat[v]
            node_value = strat[CALL] * ev_call + strat[FOLD] * ev_fold
            self.regret_sum[(VILL_VS_BET, v)][CALL] += ev_call - node_value
            self.regret_sum[(VILL_VS_BET, v)][FOLD] += ev_fold - node_value
            self.strategy_sum[(VILL_VS_BET, v)][CALL] += strat[CALL]
            self.strategy_sum[(VILL_VS_BET, v)][FOLD] += strat[FOLD]

        # ── VILLAIN AFTER HERO CHECK ───────────────────────────────────
        for v in range(n_v):
            ev_bet = 0.0
            ev_check = 0.0
            valid_heroes = 0
            for h in range(n_h):
                if self.collision[h][v]:
                    continue
                w = hero_first_strat[h][CHECK]
                if w <= 0:
                    continue
                valid_heroes += w
                # Villain bets: hero plays HERO_VS_BET strategy
                hvb = hero_vs_bet_strat[h]
                _, v_after_h_call = self._terminal_ev_hero_chks_v_bets_h_calls(h, v)
                _, v_after_h_fold = self._terminal_ev_hero_chks_v_bets_h_folds()
                v_ev_bet = hvb[CALL] * v_after_h_call + hvb[FOLD] * v_after_h_fold
                ev_bet += w * v_ev_bet
                # Villain checks: showdown
                _, v_check = self._terminal_ev_hero_checks_v_checks(h, v)
                ev_check += w * v_check

            if valid_heroes <= 0:
                continue
            ev_bet /= valid_heroes
            ev_check /= valid_heroes

            strat = vill_after_chk_strat[v]
            node_value = strat[BET] * ev_bet + strat[CHECK] * ev_check
            self.regret_sum[(VILL_AFTER_CHK, v)][BET] += ev_bet - node_value
            self.regret_sum[(VILL_AFTER_CHK, v)][CHECK] += ev_check - node_value
            self.strategy_sum[(VILL_AFTER_CHK, v)][BET] += strat[BET]
            self.strategy_sum[(VILL_AFTER_CHK, v)][CHECK] += strat[CHECK]

        # ── HERO FACING VILLAIN BET (after check) ──────────────────────
        for h in range(n_h):
            ev_call = 0.0
            ev_fold = 0.0
            valid_villains = 0
            for v in range(n_v):
                if self.collision[h][v]:
                    continue
                w = vill_after_chk_strat[v][BET]
                if w <= 0:
                    continue
                valid_villains += w
                hero_ev_call, _ = self._terminal_ev_hero_chks_v_bets_h_calls(h, v)
                hero_ev_fold = self._terminal_ev_hero_chks_v_bets_h_folds()[0]
                ev_call += w * hero_ev_call
                ev_fold += w * hero_ev_fold

            if valid_villains <= 0:
                continue
            ev_call /= valid_villains
            ev_fold /= valid_villains

            strat = hero_vs_bet_strat[h]
            node_value = strat[CALL] * ev_call + strat[FOLD] * ev_fold
            self.regret_sum[(HERO_VS_BET, h)][CALL] += ev_call - node_value
            self.regret_sum[(HERO_VS_BET, h)][FOLD] += ev_fold - node_value
            self.strategy_sum[(HERO_VS_BET, h)][CALL] += strat[CALL]
            self.strategy_sum[(HERO_VS_BET, h)][FOLD] += strat[FOLD]

    # ── PUBLIC SOLVE ──────────────────────────────────────────────────
    def solve(self, iterations: int = 1000) -> SolverResult:
        t0 = time.time()
        for _ in range(iterations):
            self._train_iteration()

        # Build per-hand strategies from average
        hero_strategies = []
        for i, (c1, c2) in enumerate(self.hero_range):
            label = f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}"
            hf = self.get_average_strategy(HERO_FIRST, i, [BET, CHECK])
            hvb = self.get_average_strategy(HERO_VS_BET, i, [CALL, FOLD])
            hero_strategies.append(HandStrategy(
                hand_label=label,
                bet_freq=round(100 * hf[BET], 1),
                check_freq=round(100 * hf[CHECK], 1),
                call_freq_vs_bet=round(100 * hvb[CALL], 1),
                fold_freq_vs_bet=round(100 * hvb[FOLD], 1),
            ))

        villain_strategies = []
        for j, (c1, c2) in enumerate(self.villain_range):
            label = f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}"
            vvb = self.get_average_strategy(VILL_VS_BET, j, [CALL, FOLD])
            vac = self.get_average_strategy(VILL_AFTER_CHK, j, [BET, CHECK])
            villain_strategies.append(HandStrategy(
                hand_label=label,
                v_call_freq=round(100 * vvb[CALL], 1),
                v_fold_freq=round(100 * vvb[FOLD], 1),
                v_bet_freq=round(100 * vac[BET], 1),
                v_check_freq=round(100 * vac[CHECK], 1),
            ))

        elapsed = int((time.time() - t0) * 1000)
        return SolverResult(
            hero_strategies=hero_strategies,
            villain_strategies=villain_strategies,
            iterations=iterations,
            elapsed_ms=elapsed,
            hero_ev=0.0,        # TODO: aggregate node EVs
            villain_ev=0.0,
        )
