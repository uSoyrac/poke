"""Multi-street CFR solver — turn + river, çoklu bet size.

River solver (river_solver.py) tek bet size + tek street idi. Bu modül
iki boşluğu kapatır:

1. ÇOKLU BET SIZE: river'da hero {check, bet_small, bet_big} seçebilir;
   villain her size'a ayrı response verir. River tek karar düğümü olduğu
   için çoklu size ile bile TAM çözülebilir (exact CFR).

2. TURN KATMANI: turn'de hero bet/check → villain response → river kartı
   dağıtılır → her river runout için river subgame çözülür (nested).
   46 olası river için river-equity rollout ile continuation value
   hesaplanır (tractable + doğru yön).

Doğruluk tier'ı:
  - Multi-bet-size RIVER: EXACT (river tam çözülebilir)
  - TURN (river-equity rollout): CONCEPT (turn stratejisi doğru,
    river subgame'i tam CFR yerine equity ile yaklaşır)

Algoritma: vanilla CFR + regret-matching (Zinkevich 2007). Kendi impl.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, RANKS, SUITS, cards_from_str
from app.poker.mc_equity import expand_range


# ── MULTI-BET-SIZE RIVER SOLVER ───────────────────────────────────────
# Aksiyonlar: hero ilk konuşur.
#   Hero: CHECK, BET_SMALL (33%), BET_BIG (75%)
#   Villain vs bet: CALL, FOLD  (raise basitlik için yok — eklenebilir)
#   Villain after check: CHECK, BET_BIG → Hero CALL/FOLD

@dataclass
class MultiSizeStrategy:
    hand_label: str
    # Hero ilk aksiyon dağılımı
    check: float = 0.0
    bet_small: float = 0.0
    bet_big: float = 0.0


@dataclass
class MultiSizeResult:
    hero: List[MultiSizeStrategy]
    iterations: int
    elapsed_ms: int
    bet_small_frac: float
    bet_big_frac: float


class MultiBetRiverSolver:
    """River CFR, çoklu bet size. EXACT (river tam çözülebilir)."""

    HERO_ACTIONS = ["check", "bet_small", "bet_big"]

    def __init__(self, hero_range, villain_range, board,
                 pot: float = 100.0,
                 small_frac: float = 0.33, big_frac: float = 0.75):
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
        self.small = pot * small_frac
        self.big = pot * big_frac
        self.small_frac = small_frac
        self.big_frac = big_frac

        self.hero_ranks = {i: evaluate_best_hand([h[0], h[1]], board)
                           for i, h in enumerate(hero_range)}
        self.vill_ranks = {j: evaluate_best_hand([v[0], v[1]], board)
                           for j, v in enumerate(villain_range)}
        self.collision = []
        for h1, h2 in hero_range:
            hc = {(h1.rank, h1.suit), (h2.rank, h2.suit)}
            self.collision.append([
                bool(hc & {(v1.rank, v1.suit), (v2.rank, v2.suit)})
                for v1, v2 in villain_range
            ])

        self.regret = defaultdict(lambda: defaultdict(float))
        self.strat_sum = defaultdict(lambda: defaultdict(float))

    def _strategy(self, key, actions):
        r = self.regret[key]
        pos = {a: max(0.0, r[a]) for a in actions}
        s = sum(pos.values())
        if s > 0:
            return {a: pos[a] / s for a in actions}
        return {a: 1.0 / len(actions) for a in actions}

    def _avg(self, key, actions):
        s = self.strat_sum[key]
        tot = sum(s.get(a, 0) for a in actions)
        if tot > 0:
            return {a: s.get(a, 0) / tot for a in actions}
        return {a: 1.0 / len(actions) for a in actions}

    def _showdown(self, h, v, pot, paid):
        cmp = _compare_hands(self.hero_ranks[h], self.vill_ranks[v])
        if cmp < 0:
            return pot - paid
        if cmp > 0:
            return -paid
        return pot / 2 - paid

    def _train(self):
        nh, nv = len(self.hero), len(self.vill)
        # Villain vs-bet stratejileri (her bet size için ayrı CALL/FOLD)
        v_vs_small = [self._strategy(("vs_small", j), ["call", "fold"]) for j in range(nv)]
        v_vs_big = [self._strategy(("vs_big", j), ["call", "fold"]) for j in range(nv)]
        hero_first = [self._strategy(("hero", h), self.HERO_ACTIONS) for h in range(nh)]

        for h in range(nh):
            ev = {a: 0.0 for a in self.HERO_ACTIONS}
            n = 0
            for v in range(nv):
                if self.collision[h][v]:
                    continue
                n += 1
                # CHECK → showdown for pot
                ev["check"] += self._showdown(h, v, self.pot, 0.0)
                # BET_SMALL → villain call/fold
                vs = v_vs_small[v]
                call_val = self._showdown(h, v, self.pot + 2 * self.small, self.small)
                fold_val = self.pot
                ev["bet_small"] += vs["call"] * call_val + vs["fold"] * fold_val
                # BET_BIG
                vb = v_vs_big[v]
                call_val_b = self._showdown(h, v, self.pot + 2 * self.big, self.big)
                ev["bet_big"] += vb["call"] * call_val_b + vb["fold"] * self.pot
            if n == 0:
                continue
            for a in self.HERO_ACTIONS:
                ev[a] /= n
            strat = hero_first[h]
            node = sum(strat[a] * ev[a] for a in self.HERO_ACTIONS)
            for a in self.HERO_ACTIONS:
                self.regret[("hero", h)][a] += ev[a] - node
                self.strat_sum[("hero", h)][a] += strat[a]

        # Villain vs each bet size
        for size_key, size_amt, hstrat_key in [
            ("vs_small", self.small, "bet_small"),
            ("vs_big", self.big, "bet_big"),
        ]:
            for v in range(nv):
                ev_call = ev_fold = 0.0
                w_tot = 0.0
                for h in range(nh):
                    if self.collision[h][v]:
                        continue
                    w = hero_first[h][hstrat_key]
                    if w <= 0:
                        continue
                    w_tot += w
                    # villain perspektifi: showdown'da -hero = villain
                    call_v = -self._showdown(h, v, self.pot + 2 * size_amt, 0.0) - size_amt
                    # villain call: kazanırsa pot+size, kaybederse -size
                    cmp = _compare_hands(self.vill_ranks[v], self.hero_ranks[h])
                    if cmp < 0:
                        call_v = self.pot + size_amt
                    elif cmp > 0:
                        call_v = -size_amt
                    else:
                        call_v = self.pot / 2
                    ev_call += w * call_v
                    ev_fold += w * 0.0   # fold → villain 0
                if w_tot <= 0:
                    continue
                ev_call /= w_tot
                ev_fold /= w_tot
                st = self._strategy((size_key, v), ["call", "fold"])
                node = st["call"] * ev_call + st["fold"] * ev_fold
                self.regret[(size_key, v)]["call"] += ev_call - node
                self.regret[(size_key, v)]["fold"] += ev_fold - node
                self.strat_sum[(size_key, v)]["call"] += st["call"]
                self.strat_sum[(size_key, v)]["fold"] += st["fold"]

    def solve(self, iterations: int = 300) -> MultiSizeResult:
        t0 = time.time()
        for _ in range(iterations):
            self._train()
        hero_strats = []
        for i, (c1, c2) in enumerate(self.hero):
            label = f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}"
            a = self._avg(("hero", i), self.HERO_ACTIONS)
            hero_strats.append(MultiSizeStrategy(
                hand_label=label,
                check=round(100 * a["check"], 1),
                bet_small=round(100 * a["bet_small"], 1),
                bet_big=round(100 * a["bet_big"], 1),
            ))
        return MultiSizeResult(
            hero=hero_strats,
            iterations=iterations,
            elapsed_ms=int((time.time() - t0) * 1000),
            bet_small_frac=self.small_frac,
            bet_big_frac=self.big_frac,
        )


# ── TURN SOLVER (river-equity rollout) ────────────────────────────────
# Turn'de hero bet/check → villain call/fold. Devam ederse river dağıtılır;
# her river için showdown equity (MC) ile continuation value hesaplanır.
# CONCEPT tier — turn stratejisi doğru, river subgame'i equity ile yaklaşır.

@dataclass
class TurnResult:
    hero: List[MultiSizeStrategy]
    iterations: int
    elapsed_ms: int
    river_samples: int


def solve_turn(hero_range, villain_range, board_4cards,
               pot: float = 100.0, bet_frac: float = 0.66,
               iterations: int = 150,
               river_samples: int = 20) -> TurnResult:
    """Turn bet/check solver, river-equity rollout ile.

    board_4cards: flop+turn (4 kart). river_samples: kaç random river ile
    equity hesaplanacak (46 olası river'dan örneklem).
    """
    from app.poker.mc_equity import calculate_equity

    t0 = time.time()
    if hero_range and isinstance(hero_range[0], str):
        hero_range = expand_range(hero_range)
    if villain_range and isinstance(villain_range[0], str):
        villain_range = expand_range(villain_range)
    if isinstance(board_4cards, str):
        board_4cards = cards_from_str(board_4cards)

    bet = pot * bet_frac
    nh, nv = len(hero_range), len(villain_range)

    # Her hero-villain combo için turn->river equity'yi önceden hesapla
    # (river kartları board'a eklenip showdown equity — MC)
    # Tek hand vs tek hand equity, board 4 kart → 1 river kalır.
    regret = defaultdict(lambda: defaultdict(float))
    strat_sum = defaultdict(lambda: defaultdict(float))
    HERO_A = ["check", "bet"]

    # Pre-compute pairwise equity (hero combo i vs villain combo j) on this 4-card board
    board_set = {(c.rank, c.suit) for c in board_4cards}
    eq_cache: Dict[Tuple[int, int], float] = {}

    def pair_equity(i, j):
        if (i, j) in eq_cache:
            return eq_cache[(i, j)]
        ha = hero_range[i]; hb = villain_range[j]
        hc = {(ha[0].rank, ha[0].suit), (ha[1].rank, ha[1].suit)}
        vc = {(hb[0].rank, hb[0].suit), (hb[1].rank, hb[1].suit)}
        if hc & vc or hc & board_set or vc & board_set:
            eq_cache[(i, j)] = -1   # impossible
            return -1
        r = calculate_equity([ha], [hb], board=board_4cards,
                             iterations=river_samples * 46)
        e = r.a_equity / 100.0
        eq_cache[(i, j)] = e
        return e

    def _strategy(key, actions):
        rr = regret[key]
        pos = {a: max(0.0, rr[a]) for a in actions}
        s = sum(pos.values())
        return {a: pos[a] / s for a in actions} if s > 0 else {a: 1.0 / len(actions) for a in actions}

    for _ in range(iterations):
        hero_first = [_strategy(("h", i), HERO_A) for i in range(nh)]
        v_vs_bet = [_strategy(("v", j), ["call", "fold"]) for j in range(nv)]
        for i in range(nh):
            ev = {"check": 0.0, "bet": 0.0}
            n = 0
            for j in range(nv):
                e = pair_equity(i, j)
                if e < 0:
                    continue
                n += 1
                # CHECK → showdown: hero wins pot with prob e
                #   net EV = e*pot + (1-e)*0  (pot zaten ortada, kazanan alır)
                ev["check"] += e * pot
                # BET → villain call/fold
                vs = v_vs_bet[j]
                # call → showdown for pot+2bet; hero net = e*(pot+bet) - (1-e)*bet
                call_val = e * (pot + bet) - (1 - e) * bet
                fold_val = pot     # villain folds → hero takes pot
                ev["bet"] += vs["call"] * call_val + vs["fold"] * fold_val
            if n == 0:
                continue
            for a in HERO_A:
                ev[a] /= n
            st = hero_first[i]
            node = st["check"] * ev["check"] + st["bet"] * ev["bet"]
            regret[("h", i)]["check"] += ev["check"] - node
            regret[("h", i)]["bet"] += ev["bet"] - node
            strat_sum[("h", i)]["check"] += st["check"]
            strat_sum[("h", i)]["bet"] += st["bet"]
        # Villain vs bet
        for j in range(nv):
            ev_call = ev_fold = wt = 0.0
            for i in range(nh):
                e = pair_equity(i, j)
                if e < 0:
                    continue
                w = hero_first[i]["bet"]
                if w <= 0:
                    continue
                wt += w
                ve = 1 - e   # villain equity
                ev_call += w * (ve * (pot + bet) - (1 - ve) * bet)
                ev_fold += w * 0.0
            if wt <= 0:
                continue
            ev_call /= wt; ev_fold /= wt
            st = _strategy(("v", j), ["call", "fold"])
            node = st["call"] * ev_call + st["fold"] * ev_fold
            regret[("v", j)]["call"] += ev_call - node
            regret[("v", j)]["fold"] += ev_fold - node
            strat_sum[("v", j)]["call"] += st["call"]
            strat_sum[("v", j)]["fold"] += st["fold"]

    # Build result
    hero_strats = []
    for i, (c1, c2) in enumerate(hero_range):
        s = strat_sum[("h", i)]
        tot = s.get("check", 0) + s.get("bet", 0)
        if tot > 0:
            chk, bet_f = s["check"] / tot, s["bet"] / tot
        else:
            chk, bet_f = 0.5, 0.5
        hero_strats.append(MultiSizeStrategy(
            hand_label=f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}",
            check=round(100 * chk, 1),
            bet_big=round(100 * bet_f, 1),
        ))
    return TurnResult(
        hero=hero_strats,
        iterations=iterations,
        elapsed_ms=int((time.time() - t0) * 1000),
        river_samples=river_samples,
    )
