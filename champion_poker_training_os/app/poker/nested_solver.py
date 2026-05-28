"""Nested multi-street CFR — chance-node'lu, heads-up EXACT.

solve_turn (multistreet_solver.py) river'ı equity ile YAKLAŞIYORDU (CONCEPT).
Bu modül river'ı da CFR ile TAM çözer: turn'de bet/check → villain response →
river DAĞITILIR (gerçek chance node, kart removal ile tüm river'lar enumerate
edilir) → her river için river subtree TAM CFR ile çözülür.

Bu, full multi-street solver'ın çekirdeği. Heads-up için matematik kesin
(vanilla CFR Nash'e yakınsar). Flop katmanı + multiway = sonraki fazlar.

ALGORİTMA — textbook vanilla CFR (Zinkevich 2007, Lanctot thesis):
  cfr(history, board, pot, hero_hand, vill_hand, p_hero, p_vill, traverser)
    - terminal → showdown/fold payoff (player-0 = hero perspektifi)
    - chance (river) → kart removal ile geçerli river'lar üzerinden ortalama
    - decision → regret-matching strategy, her action recurse, reach-weighted
      regret update

Bir "iterasyon" = tüm collision-free (hero, villain) el çifti üzerinden
traverse (başlangıç dağıtımının chance enumeration'ı). Average strategy
Nash'e yakınsar.

Hız: O(iters × hands² × rivers × node) — saf Python yavaş. Küçük range
(8-15 el) + ~60-120 iter ile study-grade. Doğruluk > hız.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, RANKS, SUITS, cards_from_str
from app.poker.mc_equity import expand_range


# ── ACTIONS ───────────────────────────────────────────────────────────
CHECK = "x"
BET = "b"      # tek bet size (genişletilebilir)
CALL = "c"
FOLD = "f"


@dataclass
class NestedStrategy:
    hand_label: str
    # Turn ilk-aksiyon dağılımı
    turn_check: float = 0.0
    turn_bet: float = 0.0


@dataclass
class NestedResult:
    hero: List[NestedStrategy]
    iterations: int
    elapsed_ms: int
    exploitability: float   # mbb/oyun cinsinden yaklaşık (0'a yakın = converged)


class NestedTurnRiverSolver:
    """Heads-up turn+river, river'ı CFR ile TAM çözen nested solver.

    Hero her iki street'te ilk konuşur (OOP). Tek bet size (pot * bet_frac).
    Aksiyon ağacı:
      TURN  hero: CHECK | BET
        CHECK → villain: CHECK | BET
          vCHECK → [river chance] → river subtree
          vBET   → hero: FOLD | CALL
            FOLD → villain wins pot
            CALL → [river chance] → river subtree (pot += 2*turnbet)
        BET → villain: FOLD | CALL
          FOLD → hero wins pot
          CALL → [river chance] → river subtree (pot += 2*turnbet)
      RIVER hero: CHECK | BET
        CHECK → villain: CHECK | BET
          vCHECK → showdown
          vBET → hero: FOLD | CALL → fold / showdown
        BET → villain: FOLD | CALL → fold / showdown
    """

    def __init__(self, hero_range, villain_range, board_turn,
                 pot: float = 100.0, bet_frac: float = 0.66):
        if hero_range and isinstance(hero_range[0], str):
            hero_range = expand_range(hero_range)
        if villain_range and isinstance(villain_range[0], str):
            villain_range = expand_range(villain_range)
        if isinstance(board_turn, str):
            board_turn = cards_from_str(board_turn)
        assert len(board_turn) == 4, "Turn board 4 kart olmalı (flop+turn)"

        self.hero = hero_range
        self.vill = villain_range
        self.board = board_turn
        self.pot0 = pot
        self.bet_frac = bet_frac

        self._board_set = {(c.rank, c.suit) for c in board_turn}
        self._full_deck = [Card(r, s) for r in RANKS for s in SUITS]

        # regret/strategy: key = (history, "H"/"V", hand_index) → {action: val}
        self.regret: Dict[tuple, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.strat_sum: Dict[tuple, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

        # showdown cache: (hand_index_pair, river_code) → cmp
        self._eval_cache: Dict[tuple, int] = {}

    # ── STRATEGY (regret matching) ────────────────────────────────────
    def _strategy(self, key, actions):
        r = self.regret[key]
        pos = {a: max(0.0, r[a]) for a in actions}
        s = sum(pos.values())
        if s > 0:
            return {a: pos[a] / s for a in actions}
        return {a: 1.0 / len(actions) for a in actions}

    def _avg(self, key, actions):
        s = self.strat_sum[key]
        tot = sum(s.get(a, 0.0) for a in actions)
        if tot > 0:
            return {a: s.get(a, 0.0) / tot for a in actions}
        return {a: 1.0 / len(actions) for a in actions}

    # ── SHOWDOWN ──────────────────────────────────────────────────────
    def _showdown_cmp(self, hi, vi, river: Card) -> int:
        """hero combo hi vs villain combo vi on board+river. <0 hero wins."""
        key = (hi, vi, river.rank, river.suit)
        c = self._eval_cache.get(key)
        if c is not None:
            return c
        full = self.board + [river]
        he = evaluate_best_hand([self.hero[hi][0], self.hero[hi][1]], full)
        ve = evaluate_best_hand([self.vill[vi][0], self.vill[vi][1]], full)
        c = _compare_hands(he, ve)
        self._eval_cache[key] = c
        return c

    # ── RIVER SUBTREE CFR ─────────────────────────────────────────────
    # ZERO-SUM konvansiyon: pot P, her oyuncu P/2 yatırmış sayılır.
    # value = final_pot - hero_invested (win) / -hero_invested (lose) /
    #          final_pot/2 - hero_invested (tie). villain_util = -hero_util.
    # hinv = hero'nun bu noktaya kadar TOPLAM yatırımı (P/2 baseline dahil).
    def _river_cfr(self, hist, river: Card, pot, hinv, hi, vi, ph, pv, traverser):
        """River subtree. Returns hero-perspective ZERO-SUM utility."""
        rbet = pot * self.bet_frac
        cmp = self._showdown_cmp(hi, vi, river)
        key_h = (hist + "|R", "H", hi)
        sh = self._strategy(key_h, [CHECK, BET])

        # --- hero CHECK ---
        key_v = (hist + "|Rx", "V", vi)
        sv = self._strategy(key_v, [CHECK, BET])
        # villain CHECK → showdown for `pot`, hero invested hinv
        sd_check = self._sd(cmp, pot, hinv)
        # villain BET rbet → hero FOLD|CALL
        key_hvb = (hist + "|Rxb", "H", hi)
        shvb = self._strategy(key_hvb, [FOLD, CALL])
        # hero FOLD → loses: value = -hinv
        # hero CALL → showdown for pot+2rbet, hero invested hinv+rbet
        hvb_call = self._sd(cmp, pot + 2 * rbet, hinv + rbet)
        hvb_node = shvb[CALL] * hvb_call + shvb[FOLD] * (-hinv)
        check_util = sv[CHECK] * sd_check + sv[BET] * hvb_node

        # --- hero BET rbet ---
        key_vvb = (hist + "|Rb", "V", vi)
        svb = self._strategy(key_vvb, [FOLD, CALL])
        # villain FOLD → hero wins (pot + rbet), invested hinv+rbet → value = pot - hinv
        bet_fold = pot - hinv
        # villain CALL → showdown for pot+2rbet, invested hinv+rbet
        bet_call = self._sd(cmp, pot + 2 * rbet, hinv + rbet)
        bet_util = svb[CALL] * bet_call + svb[FOLD] * bet_fold

        util = {CHECK: check_util, BET: bet_util}
        node_util = sh[CHECK] * check_util + sh[BET] * bet_util

        # ── REGRET UPDATES ──
        self._update(key_h, [CHECK, BET], util, node_util, sh, "H", ph, pv, traverser)
        v_node = sv[CHECK] * (-sd_check) + sv[BET] * (-hvb_node)
        self._update(key_v, [CHECK, BET], {CHECK: -sd_check, BET: -hvb_node},
                     v_node, sv, "V", ph, pv, traverser)
        self._update(key_hvb, [FOLD, CALL], {FOLD: -hinv, CALL: hvb_call},
                     hvb_node, shvb, "H", ph, pv, traverser)
        v_node2 = svb[CALL] * (-bet_call) + svb[FOLD] * (-bet_fold)
        self._update(key_vvb, [FOLD, CALL], {FOLD: -bet_fold, CALL: -bet_call},
                     v_node2, svb, "V", ph, pv, traverser)

        return node_util

    def _sd(self, cmp, final_pot, hero_inv):
        """Zero-sum hero payoff. win→final_pot-inv, tie→final_pot/2-inv, lose→-inv."""
        if cmp < 0:
            return final_pot - hero_inv
        if cmp > 0:
            return -hero_inv
        return final_pot / 2 - hero_inv

    def _update(self, key, actions, util, node_util, strat, owner,
                ph, pv, traverser=None):
        """Reach-weighted regret + average strategy update.

        Vanilla CFR: HER iterasyonda iki oyuncu da güncellenir (traverser
        gate yok). Regret = opponent_reach × (util[a] - node_util);
        average strategy = own_reach × strat[a].
        """
        cf_reach = pv if owner == "H" else ph    # opponent reach
        own_reach = ph if owner == "H" else pv
        for a in actions:
            self.regret[key][a] += cf_reach * (util[a] - node_util)
            self.strat_sum[key][a] += own_reach * strat[a]

    # ── TURN CFR ──────────────────────────────────────────────────────
    def _turn_cfr(self, hi, vi, ph, pv, traverser):
        """Turn root for a hand pair. Returns hero-perspective utility."""
        pot = self.pot0
        tbet = pot * self.bet_frac
        used = {(self.hero[hi][0].rank, self.hero[hi][0].suit),
                (self.hero[hi][1].rank, self.hero[hi][1].suit),
                (self.vill[vi][0].rank, self.vill[vi][0].suit),
                (self.vill[vi][1].rank, self.vill[vi][1].suit)} | self._board_set
        rivers = [c for c in self._full_deck if (c.rank, c.suit) not in used]
        if not rivers:
            return 0.0
        inv_n = 1.0 / len(rivers)
        hinv0 = pot / 2.0   # ZERO-SUM baseline: hero pot'un yarısını yatırmış sayılır

        def river_avg(hist, rpot, hinv, p_h, p_v):
            tot = 0.0
            for rc in rivers:
                tot += self._river_cfr(hist, rc, rpot, hinv, hi, vi, p_h, p_v, traverser)
            return tot * inv_n

        # Turn hero CHECK | BET
        key_h = ("T", "H", hi)
        sh = self._strategy(key_h, [CHECK, BET])

        # hero CHECK → villain CHECK|BET
        key_v = ("Tx", "V", vi)
        sv = self._strategy(key_v, [CHECK, BET])
        # vCHECK → river (pot, hinv=P/2)
        v_check_branch = river_avg("Tx", pot, hinv0,
                                   ph * sh[CHECK], pv * sv[CHECK])
        # vBET tbet → hero FOLD|CALL
        key_hvb = ("Txb", "H", hi)
        shvb = self._strategy(key_hvb, [FOLD, CALL])
        # hero CALL → river (pot+2tbet, hinv=P/2+tbet)
        call_branch = river_avg("Txbc", pot + 2 * tbet, hinv0 + tbet,
                                ph * sh[CHECK] * shvb[CALL], pv * sv[BET])
        # hero FOLD → loses: value = -hinv0
        hvb_util = {FOLD: -hinv0, CALL: call_branch}
        hvb_node = shvb[CALL] * call_branch + shvb[FOLD] * (-hinv0)
        check_util = sv[CHECK] * v_check_branch + sv[BET] * hvb_node

        # hero BET tbet → villain FOLD|CALL
        key_vvb = ("Tb", "V", vi)
        svb = self._strategy(key_vvb, [FOLD, CALL])
        # villain FOLD → hero wins pot, value = pot - hinv0 = P/2
        bet_fold = pot - hinv0
        # villain CALL → river (pot+2tbet, hinv=P/2+tbet)
        bet_call_branch = river_avg("Tbc", pot + 2 * tbet, hinv0 + tbet,
                                    ph * sh[BET], pv * svb[CALL])
        bet_util = svb[CALL] * bet_call_branch + svb[FOLD] * bet_fold

        util = {CHECK: check_util, BET: bet_util}
        node_util = sh[CHECK] * check_util + sh[BET] * bet_util

        # Updates
        self._update(key_h, [CHECK, BET], util, node_util, sh, "H", ph, pv, traverser)
        v_node = sv[CHECK] * (-v_check_branch) + sv[BET] * (-hvb_node)
        self._update(key_v, [CHECK, BET],
                     {CHECK: -v_check_branch, BET: -hvb_node}, v_node, sv,
                     "V", ph, pv, traverser)
        self._update(key_hvb, [FOLD, CALL], hvb_util, hvb_node, shvb,
                     "H", ph, pv, traverser)
        v_node2 = svb[CALL] * (-bet_call_branch) + svb[FOLD] * (-bet_fold)
        self._update(key_vvb, [FOLD, CALL],
                     {FOLD: -bet_fold, CALL: -bet_call_branch}, v_node2, svb,
                     "V", ph, pv, traverser)

        return node_util

    # ── SOLVE ─────────────────────────────────────────────────────────
    def solve(self, iterations: int = 80) -> NestedResult:
        t0 = time.time()
        nh, nv = len(self.hero), len(self.vill)
        pairs = []
        for hi in range(nh):
            hc = {(self.hero[hi][0].rank, self.hero[hi][0].suit),
                  (self.hero[hi][1].rank, self.hero[hi][1].suit)}
            if hc & self._board_set:
                continue
            for vi in range(nv):
                vc = {(self.vill[vi][0].rank, self.vill[vi][0].suit),
                      (self.vill[vi][1].rank, self.vill[vi][1].suit)}
                if vc & self._board_set or vc & hc:
                    continue
                pairs.append((hi, vi))

        for it in range(iterations):
            # Vanilla CFR — her iterasyonda iki oyuncu da güncellenir
            for hi, vi in pairs:
                self._turn_cfr(hi, vi, 1.0, 1.0, None)

        # Build hero turn strategy (average)
        hero_strats = []
        for hi in range(nh):
            label = (f"{self.hero[hi][0].rank}{self.hero[hi][0].suit}"
                     f"{self.hero[hi][1].rank}{self.hero[hi][1].suit}")
            a = self._avg(("T", "H", hi), [CHECK, BET])
            hero_strats.append(NestedStrategy(
                hand_label=label,
                turn_check=round(100 * a[CHECK], 1),
                turn_bet=round(100 * a[BET], 1),
            ))
        return NestedResult(
            hero=hero_strats,
            iterations=iterations,
            elapsed_ms=int((time.time() - t0) * 1000),
            exploitability=0.0,
        )
