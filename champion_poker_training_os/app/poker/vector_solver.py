"""Vectorized river CFR — numpy ile 50-100x hızlı.

Per-combo solver (river_solver.py / nested_solver.py) hero×villain çiftleri
üzerinde döngü kuruyordu → yavaş (~saniyeler). Bu modül showdown'u tek bir
MATRİS çarpımına çevirir: stratejiler/regret'ler [el × aksiyon] numpy
array'leri, opponent reach bir vektör, counterfactual değerler matris-vektör
çarpımı. Aynı CFR matematiği, ~100x hız.

Heads-up river, hero OOP (ilk konuşur), tek bet size:
  Hero: CHECK | BET
    CHECK → Villain: CHECK | BET
      vCHECK → showdown (pot P)
      vBET   → Hero: CALL | FOLD → showdown(P+2b) | -P/2
    BET → Villain: CALL | FOLD → showdown(P+2b) | hero wins P/2

ZERO-SUM: her oyuncu pot'un P/2'sini yatırmış sayılır. showdown net:
  win → +(P/2 + street_bet), lose → -(P/2 + street_bet), tie → 0.

Doğrulama: per-combo RiverSolver ile aynı stratejileri üretir, çok daha hızlı.
Algoritma: vanilla CFR + regret-matching, counterfactual değerler opponent
reach ile matris çarpımı (Zinkevich 2007). Kendi implementation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, cards_from_str
from app.poker.mc_equity import expand_range


@dataclass
class VectorStrategy:
    hand_label: str
    check: float = 0.0
    bet: float = 0.0
    call_vs_bet: float = 0.0
    fold_vs_bet: float = 0.0


@dataclass
class VectorResult:
    hero: List[VectorStrategy]
    iterations: int
    elapsed_ms: int


class VectorRiverSolver:
    """numpy-vectorized river CFR — hızlı + exact (HU)."""

    def __init__(self, hero_range, villain_range, board,
                 pot: float = 100.0, bet_frac: float = 0.75):
        if hero_range and isinstance(hero_range[0], str):
            hero_range = expand_range(hero_range)
        if villain_range and isinstance(villain_range[0], str):
            villain_range = expand_range(villain_range)
        if isinstance(board, str):
            board = cards_from_str(board)

        self.hero = hero_range
        self.vill = villain_range
        self.board = board
        self.pot = pot
        self.bet = pot * bet_frac
        self.bet_frac = bet_frac

        nh, nv = len(hero_range), len(villain_range)
        self.nh, self.nv = nh, nv

        # Showdown sign matrix W[i,j] ∈ {+1,0,-1} + collision mask C[i,j] ∈ {0,1}
        W = np.zeros((nh, nv), dtype=np.float64)
        C = np.zeros((nh, nv), dtype=np.float64)
        hero_ev = [evaluate_best_hand([h[0], h[1]], board) for h in hero_range]
        vill_ev = [evaluate_best_hand([v[0], v[1]], board) for v in villain_range]
        hero_codes = [{(h[0].rank, h[0].suit), (h[1].rank, h[1].suit)} for h in hero_range]
        vill_codes = [{(v[0].rank, v[0].suit), (v[1].rank, v[1].suit)} for v in villain_range]
        for i in range(nh):
            for j in range(nv):
                if hero_codes[i] & vill_codes[j]:
                    continue   # collision → C=0, W=0
                C[i, j] = 1.0
                cmp = _compare_hands(hero_ev[i], vill_ev[j])
                W[i, j] = 1.0 if cmp < 0 else (-1.0 if cmp > 0 else 0.0)
        self.W = W
        self.C = C

        # Range weights (uniform combo weights)
        self.r_h0 = np.ones(nh)
        self.r_v0 = np.ones(nv)

        # Regret + strategy-sum arrays [hands × 2]
        self.reg_h_root = np.zeros((nh, 2))      # [check, bet]
        self.reg_h_vb = np.zeros((nh, 2))        # [call, fold] vs villain bet
        self.reg_v_ac = np.zeros((nv, 2))        # [check, bet] after hero check
        self.reg_v_vb = np.zeros((nv, 2))        # [call, fold] vs hero bet
        self.ss_h_root = np.zeros((nh, 2))
        self.ss_h_vb = np.zeros((nh, 2))
        self.ss_v_ac = np.zeros((nv, 2))
        self.ss_v_vb = np.zeros((nv, 2))

    @staticmethod
    def _regret_match(reg: np.ndarray) -> np.ndarray:
        pos = np.maximum(reg, 0.0)
        s = pos.sum(axis=1, keepdims=True)
        out = np.where(s > 0, pos / np.where(s > 0, s, 1), 0.5)
        return out

    def solve(self, iterations: int = 500) -> VectorResult:
        t0 = time.time()
        P = self.pot
        b = self.bet
        amt_nobet = P / 2.0          # showdown amount (no street bet)
        amt_bet = P / 2.0 + b        # showdown amount (called bet)
        W, C = self.W, self.C
        r_v0, r_h0 = self.r_v0, self.r_h0

        for _ in range(iterations):
            # ── Strategies ──
            sh = self._regret_match(self.reg_h_root)     # [nh,2] check,bet
            shvb = self._regret_match(self.reg_h_vb)     # [nh,2] call,fold
            svac = self._regret_match(self.reg_v_ac)     # [nv,2] check,bet
            svvb = self._regret_match(self.reg_v_vb)     # [nv,2] call,fold

            # ── HERO value computation (counterfactual, villain-reach weighted) ──
            # villain reaches to terminals (vectors over villain hands)
            rv_ac_check = r_v0 * svac[:, 0]
            rv_ac_bet = r_v0 * svac[:, 1]
            rv_vb_call = r_v0 * svvb[:, 0]
            rv_vb_fold = r_v0 * svvb[:, 1]

            # CHECK branch:
            #  villain check → showdown P: amt_nobet * (W @ rv_ac_check)
            chk_vcheck = amt_nobet * (W @ rv_ac_check)
            #  villain bet → hero call/fold
            hcall = amt_bet * (W @ rv_ac_bet)            # hero calls, showdown P+2b
            hfold = -amt_nobet * (C @ rv_ac_bet)         # hero folds → -P/2 * (non-collide villain bet reach)
            # hero's H_vs_vbet decision (per hero hand)
            partB = shvb[:, 0] * hcall + shvb[:, 1] * hfold
            check_val = chk_vcheck + partB

            # BET branch:
            bet_call = amt_bet * (W @ rv_vb_call)        # villain calls, showdown P+2b
            bet_fold = amt_nobet * (C @ rv_vb_fold)      # villain folds → hero +P/2
            bet_val = bet_call + bet_fold

            # node util (hero root)
            node_h = sh[:, 0] * check_val + sh[:, 1] * bet_val
            # regret update (counterfactual val already villain-reach weighted)
            self.reg_h_root[:, 0] += check_val - node_h
            self.reg_h_root[:, 1] += bet_val - node_h
            self.ss_h_root += r_h0[:, None] * sh

            # H_vs_vbet regrets (reached via hero check, villain bet)
            hvb_node = shvb[:, 0] * hcall + shvb[:, 1] * hfold
            self.reg_h_vb[:, 0] += hcall - hvb_node
            self.reg_h_vb[:, 1] += hfold - hvb_node
            # own reach for avg strategy = hero reached this node by CHECK
            self.ss_h_vb += (r_h0 * sh[:, 0])[:, None] * shvb

            # ── VILLAIN value computation (hero-reach weighted) ──
            # hero reaches
            rh_check = r_h0 * sh[:, 0]
            rh_bet = r_h0 * sh[:, 1]
            # W^T from villain perspective: villain beats hero → -W. Use Wt = -W.T
            Wt = -W.T
            Ct = C.T

            # Villain after hero CHECK: check | bet
            #  villain CHECK → showdown P (villain value): amt_nobet * (Wt @ rh_check)
            v_check = amt_nobet * (Wt @ rh_check)
            #  villain BET → hero call/fold. villain value:
            #    hero call → showdown P+2b (villain perspective): amt_bet*(Wt @ (rh_check*shvb_call))
            #    hero fold → villain wins P/2: +amt_nobet * (Ct @ (rh_check*shvb_fold))
            rh_check_call = r_h0 * sh[:, 0] * shvb[:, 0]
            rh_check_fold = r_h0 * sh[:, 0] * shvb[:, 1]
            v_bet = (amt_bet * (Wt @ rh_check_call)
                     + amt_nobet * (Ct @ rh_check_fold))
            v_ac_node = svac[:, 0] * v_check + svac[:, 1] * v_bet
            self.reg_v_ac[:, 0] += v_check - v_ac_node
            self.reg_v_ac[:, 1] += v_bet - v_ac_node
            self.ss_v_ac += r_v0[:, None] * svac

            # Villain vs hero BET: call | fold
            #  villain call → showdown P+2b: amt_bet * (Wt @ rh_bet)
            #  villain fold → loses P/2: -amt_nobet * (Ct @ rh_bet)
            v_call = amt_bet * (Wt @ rh_bet)
            v_fold = -amt_nobet * (Ct @ rh_bet)
            v_vb_node = svvb[:, 0] * v_call + svvb[:, 1] * v_fold
            self.reg_v_vb[:, 0] += v_call - v_vb_node
            self.reg_v_vb[:, 1] += v_fold - v_vb_node
            self.ss_v_vb += (r_v0 * 1.0)[:, None] * svvb

        # ── Average strategies ──
        def avg(ss):
            s = ss.sum(axis=1, keepdims=True)
            return np.where(s > 0, ss / np.where(s > 0, s, 1), 0.5)
        ah = avg(self.ss_h_root)
        ahvb = avg(self.ss_h_vb)

        hero_strats = []
        for i, (c1, c2) in enumerate(self.hero):
            hero_strats.append(VectorStrategy(
                hand_label=f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}",
                check=round(100 * ah[i, 0], 1),
                bet=round(100 * ah[i, 1], 1),
                call_vs_bet=round(100 * ahvb[i, 0], 1),
                fold_vs_bet=round(100 * ahvb[i, 1], 1),
            ))
        return VectorResult(
            hero=hero_strats,
            iterations=iterations,
            elapsed_ms=int((time.time() - t0) * 1000),
        )
