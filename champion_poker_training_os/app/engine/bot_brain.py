"""Realistic poker bot brain.

Combines:
- Position-aware preflop ranges (Janda/Little inspired, +open ~22% BTN, 14% UTG)
- Range vs board interaction (Nut Asymmetry, paired board, monotone)
- GTO baseline c-bet frequencies with polarized vs merged sizing
- Archetype overlays (TAG, LAG, Nit, Station, Maniac, etc.) that DEVIATE from baseline
- Mixed-frequency raise/fold decisions in marginal spots (indifference principle)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.engine.hand_state import (
    ActionType, Card, HandState, PlayerSeat, Street, RANK_VALUES,
)


@dataclass
class BotProfile:
    name: str
    vpip: float
    pfr: float
    three_bet: float
    fold_to_cbet: float
    aggression: float       # 0-5 postflop aggression
    river_bluff: float      # 0-1
    call_down: float        # 0-1
    overbet_freq: float = 0.05
    # Exploitative tendencies
    bluff_river: float = 0.25      # 0-1 chance to bluff with air on river
    call_3bet: float = 0.30        # 0-1 chance to call vs 3bet light
    notes: str = ""


BOT_ARCHETYPES = {
    "TAG":             BotProfile("TAG", 22, 18, 8, 55, 2.8, 0.28, 0.32, 0.05, 0.25, 0.28,
                                   notes="Tight Aggressive — folds to aggression unless strong."),
    "LAG":             BotProfile("LAG", 32, 26, 12, 38, 3.6, 0.42, 0.46, 0.08, 0.40, 0.42,
                                   notes="Loose Aggressive — barrels frequently, light 3-bets."),
    "Nit":             BotProfile("Nit", 14, 12, 5, 72, 1.5, 0.08, 0.18, 0.02, 0.10, 0.15,
                                   notes="Ultra-tight — only premiums. Overfolds vs aggression."),
    "Calling Station": BotProfile("Calling Station", 42, 6, 2, 18, 0.8, 0.05, 0.78, 0.02, 0.05, 0.70,
                                   notes="Sticky — calls down light, rarely raises/bluffs."),
    "Maniac":          BotProfile("Maniac", 55, 38, 22, 22, 4.6, 0.62, 0.52, 0.18, 0.55, 0.50,
                                   notes="Wild — overbets, bluffs everywhere, hard to fold."),
    "Reg":             BotProfile("Reg", 24, 20, 9, 50, 2.7, 0.30, 0.36, 0.05, 0.28, 0.30,
                                   notes="Solid regular — balanced ranges."),
    "Fish":            BotProfile("Fish", 46, 8, 3, 28, 1.4, 0.10, 0.62, 0.03, 0.08, 0.55,
                                   notes="Recreational — calls too wide preflop, gives up postflop."),
    "Shark":           BotProfile("Shark", 22, 19, 11, 56, 3.2, 0.36, 0.30, 0.07, 0.35, 0.30,
                                   notes="Strong reg — tight balanced ranges, exploits leaks."),
    "Rock":            BotProfile("Rock", 12, 10, 4, 78, 1.0, 0.04, 0.15, 0.01, 0.05, 0.10,
                                   notes="OMC archetype — almost never bluffs."),
    "Aggro Fish":      BotProfile("Aggro Fish", 48, 32, 9, 26, 3.9, 0.48, 0.56, 0.10, 0.45, 0.50,
                                   notes="Spew tank — fires too often without thinking."),
    "Tight Passive":   BotProfile("Tight Passive", 18, 8, 3, 65, 0.7, 0.04, 0.42, 0.02, 0.04, 0.35,
                                   notes="Tight but doesn't pressure — checks/calls."),
    "Balanced Reg":    BotProfile("Balanced Reg", 25, 21, 10, 48, 2.7, 0.28, 0.35, 0.05, 0.28, 0.32,
                                   notes="Default opponent — solver-ish baseline."),
    "Solver Bot":      BotProfile("Solver Bot", 23, 21, 11, 52, 3.0, 0.32, 0.30, 0.06, 0.30, 0.30,
                                   notes="Approximates GTO baseline frequencies."),
    "Bubble Nit":      BotProfile("Bubble Nit", 11, 9, 3, 80, 1.2, 0.06, 0.22, 0.01, 0.06, 0.18,
                                   notes="ICM-pressured — overfolds vs aggression on bubble."),
    "GTO Expert":      BotProfile("GTO Expert", 24, 22, 12, 50, 3.1, 0.32, 0.32, 0.08, 0.32, 0.34,
                                   notes="High-skill solver — balanced ranges, polarized sizings, "
                                         "rarely exploitable. Tougher than Solver Bot."),
    "Karma (Mixed)":   BotProfile("Karma (Mixed)", 28, 22, 10, 48, 3.0, 0.32, 0.40, 0.07, 0.34, 0.38,
                                   notes="Randomised — switches mood every hand, hard to read."),
}


# A roster used when the user picks "Karma (Mixed)" — game_loop spreads these
# across seats (one archetype per opponent) for a varied, realistic field.
KARMA_MIX = [
    "TAG", "LAG", "Fish", "Calling Station",
    "Reg", "Maniac", "Tight Passive", "Aggro Fish",
    "Shark", "Nit",
]


# ─── PREFLOP HAND CATEGORIES ──────────────────────────────────────

PREMIUM = {"AA", "KK", "QQ", "JJ", "AKs", "AKo"}
STRONG = {"TT", "99", "AQs", "AQo", "AJs", "ATs", "KQs", "KJs"}
MEDIUM = {"88", "77", "66", "AJo", "ATo", "KQo", "QJs", "JTs", "T9s", "98s",
          "KTs", "QTs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s"}
SPECULATIVE = {"55", "44", "33", "22", "87s", "76s", "65s", "54s",
               "K9s", "Q9s", "J9s", "K9o", "Q9o", "J9o", "T8s", "97s",
               "KJo", "KTo", "QJo", "JTo"}
TRASH_PLAYABLE_VS_LIMP = {"K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
                          "Q8s", "Q7s", "J8s", "T7s", "96s",
                          "T9o", "98o", "87o"}


def hand_key(c1: Card, c2: Card) -> str:
    """Convert two cards to canonical hand label e.g. 'AKs', 'QJo', '77'."""
    r1, r2 = c1.rank, c2.rank
    if r1 == r2:
        return f"{r1}{r2}"
    high, low = (r1, r2) if RANK_VALUES[r1] > RANK_VALUES[r2] else (r2, r1)
    suited = c1.suit == c2.suit
    return f"{high}{low}{'s' if suited else 'o'}"


# ─── HAND STRENGTH RANKING (for archetype-fidelity VPIP/PFR/3-bet control) ─
# Goal: each profile's realized VPIP matches its declared target. We do this
# by ranking all 169 hand types by approximate equity and picking the top
# X% by combo frequency for each archetype's open range. Suited/connector/
# pair bonuses are empirical, not solver-output, but sequence the hands in
# a defensibly correct order (AA > AKs > KQs > etc.).

def _hand_strength_score(hk: str) -> float:
    """0-1 strength score used to rank hands for archetype range building."""
    r1, r2 = hk[0], hk[1]
    v1, v2 = RANK_VALUES[r1], RANK_VALUES[r2]
    is_pair = (r1 == r2)
    is_suited = len(hk) >= 3 and hk[2] == "s"
    if is_pair:
        # Pairs jumped above unpaired hands of similar high-card —
        # 22 ≈ AJo, AA = top.
        return 0.55 + (v1 - 2) / 12 * 0.45   # 22 → 0.55, AA → 1.00
    high, low = max(v1, v2), min(v1, v2)
    gap = high - low - 1
    score = (high - 2) * 0.040 + (low - 2) * 0.024   # ~0.0 .. 0.81
    if is_suited:
        score += 0.06
    if gap == 0:
        score += 0.025
    elif gap == 1:
        score += 0.012
    return min(0.94, score)


def _all_hand_keys() -> List[str]:
    ranks = "23456789TJQKA"
    keys: List[str] = []
    for i, r1 in enumerate(ranks):
        for j, r2 in enumerate(ranks):
            if i == j:
                keys.append(f"{r1}{r2}")
            elif i > j:
                keys.append(f"{r1}{r2}s")
                keys.append(f"{r1}{r2}o")
    return keys


def _hand_combo_count(hk: str) -> int:
    """Combos out of 1326 — pair=6, suited=4, offsuit=12."""
    if len(hk) == 2:
        return 6
    return 4 if hk[2] == "s" else 12


_HAND_KEYS: List[str] = _all_hand_keys()
_HAND_STRENGTH: dict = {hk: _hand_strength_score(hk) for hk in _HAND_KEYS}
_HAND_FREQ: dict = {hk: _hand_combo_count(hk) for hk in _HAND_KEYS}
_SORTED_BY_STRENGTH: List[str] = sorted(
    _HAND_KEYS, key=lambda hk: (-_HAND_STRENGTH[hk], hk)
)
_TOTAL_COMBOS = 1326   # 52 choose 2


def hands_in_top_pct(pct: float) -> set:
    """Frequency-aware top-N% range — returns hand keys that fill `pct` of all 1326 combos."""
    target = max(0.0, pct) / 100.0 * _TOTAL_COMBOS
    out: set = set()
    acc = 0
    for hk in _SORTED_BY_STRENGTH:
        if acc >= target:
            break
        out.add(hk)
        acc += _HAND_FREQ[hk]
    return out


# Per-position VPIP multiplier — UTG opens tighter than BTN even with the
# same archetype. Multiplies the profile's target VPIP to get a position-
# adjusted range size (clamped to [0, 85]).
_POS_VPIP_MULT = {
    "UTG":   0.65,
    "UTG+1": 0.75,
    "MP":    0.85,
    "LJ":    0.95,
    "HJ":    1.05,
    "CO":    1.20,
    "BTN":   1.45,
    "SB":    0.90,
    "BB":    1.05,        # only acts when checked to or facing limp
    "SB/BTN": 1.45,
}


# Open ranges by position (simplified GTO baseline %)
OPEN_RANGES = {
    "UTG":   PREMIUM | STRONG | {"77", "66", "55", "AJo", "ATs", "KQs", "QJs", "JTs"},
    "UTG+1": PREMIUM | STRONG | {"77", "66", "55", "44", "AJo", "ATs", "KQs", "KJs", "QJs", "JTs", "T9s"},
    "MP":    PREMIUM | STRONG | MEDIUM - {"ATo", "KQo"} | {"77", "66", "55", "44", "33"},
    "LJ":    PREMIUM | STRONG | MEDIUM | {"33", "22", "98s", "T9s"} - {"KQo"},
    "HJ":    PREMIUM | STRONG | MEDIUM | SPECULATIVE - {"K9o", "Q9o", "J9o", "JTo", "KTo", "QJo"},
    "CO":    PREMIUM | STRONG | MEDIUM | SPECULATIVE | {"K9o", "QJo", "JTo"},
    "BTN":   PREMIUM | STRONG | MEDIUM | SPECULATIVE | TRASH_PLAYABLE_VS_LIMP | {"K9o", "Q9o", "QJo", "JTo", "T9o", "KTo", "KJo"},
    "SB":    PREMIUM | STRONG | MEDIUM | {"55", "44", "33", "22", "98s", "T9s"} | {"KJo", "QJo", "KQo", "AJo", "ATo"},
    "BB":    PREMIUM | STRONG | MEDIUM | SPECULATIVE | TRASH_PLAYABLE_VS_LIMP,
    "SB/BTN": PREMIUM | STRONG | MEDIUM | SPECULATIVE | TRASH_PLAYABLE_VS_LIMP | {"K9o", "Q9o", "QJo", "JTo", "T9o"},
}


# 3-bet ranges (against single open)
THREE_BET_RANGES = {
    "vs_early":  {"AA", "KK", "QQ", "JJ", "AKs", "AKo", "A5s", "A4s", "KQs"},  # Tight 3bet vs UTG
    "vs_late":   PREMIUM | {"TT", "99", "AQs", "AQo", "AJs", "KQs", "A5s", "A4s", "A3s", "A2s", "76s", "65s"},
    "vs_blinds": PREMIUM | STRONG | {"A5s", "A4s", "A3s", "76s", "65s", "54s"},
}


class BotBrain:
    """Decision engine combining GTO baseline + archetype exploits."""

    def __init__(self, profile: BotProfile):
        self.profile = profile
        # Precomputed per-position open ranges sized to hit profile.vpip.
        # Cached at construction so per-hand decisions are O(1) lookups.
        self._pos_open_ranges: dict = {}
        for pos, mult in _POS_VPIP_MULT.items():
            pct = max(0.0, min(85.0, profile.vpip * mult))
            self._pos_open_ranges[pos] = hands_in_top_pct(pct)
        # 3-bet pool — top three_bet% of all hands (slightly wider for IP
        # spots so realized 3-bet% lands close to the declared target after
        # accounting for opp-position frequency).
        self._3bet_pool_ip = hands_in_top_pct(min(40.0, profile.three_bet * 1.25))
        self._3bet_pool_oop = hands_in_top_pct(min(35.0, profile.three_bet * 0.95))
        # Defensive call pool — what we call (not 3-bet) facing a single open
        self._call_pool = hands_in_top_pct(min(50.0, profile.vpip * 1.05))

    # ── PUBLIC API ─────────────────────────────────────────────────

    def decide(self, state: HandState, player_idx: int) -> Tuple[ActionType, float]:
        valid = state.get_valid_actions(player_idx)
        if not valid:
            return ActionType.CHECK, 0.0

        player = state.players[player_idx]

        # ── UNIVERSAL COMMITMENT GUARD ────────────────────────────────
        # Applied before archetype logic so no bot ever folds when pot-committed.
        # "Committed" means ≥ 65% of the stack held at the start of this street
        # has already been wagered — folding for the remaining chips is then
        # almost never correct (pot odds are overwhelmingly in favour of calling).
        #
        # Also guards the forced all-in edge case: if the only non-fold
        # option is going all-in for < 35% of the pot, the call is mandatory.
        valid_types = {v[0] for v in valid}
        to_call = state.to_call(player_idx)
        if to_call > 0:
            invested = player.current_bet           # wagered THIS street
            start_of_street = player.stack + invested
            commitment = invested / max(start_of_street, 0.01)
            if commitment >= 0.65:
                # Already committed ≥ 65% of street starting stack → never fold
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                if ActionType.ALL_IN in valid_types:
                    return ActionType.ALL_IN, player.stack
            # Forced all-in (CALL not available, only ALL_IN or FOLD):
            # call if it costs < 35% of the total pot after calling.
            if (ActionType.ALL_IN in valid_types
                    and ActionType.CALL not in valid_types):
                allin_pot_frac = player.stack / max(state.pot + player.stack, 0.01)
                if allin_pot_frac < 0.35:
                    return ActionType.ALL_IN, player.stack

        if state.street == Street.PREFLOP:
            return self._preflop(state, player_idx, player, valid)
        return self._postflop(state, player_idx, player, valid)

    # ── PREFLOP ────────────────────────────────────────────────────

    def _preflop(self, state: HandState, idx: int, player: PlayerSeat,
                 valid: List[Tuple[ActionType, float, float]]) -> Tuple[ActionType, float]:
        valid_types = {v[0] for v in valid}
        if not player.hole_cards or len(player.hole_cards) < 2:
            return self._fallback(valid_types, valid)
        hk = hand_key(player.hole_cards[0], player.hole_cards[1])
        pos = player.position or "BTN"

        to_call = state.to_call(idx)
        bb = state.big_blind
        # How many bets have been made?
        # If current_bet > bb, someone has raised. If > 3*bb, possible 3-bet.
        is_unopened = state.current_bet <= bb + 0.01
        is_facing_raise = state.current_bet > bb + 0.01

        # Archetype tightness scaler (kept for postflop / aggression hooks)
        loose = (self.profile.vpip - 22) / 22.0
        loose = max(-1.0, min(1.5, loose))

        # Per-archetype per-position open range — precomputed in __init__.
        # Profile.vpip == realized VPIP because the range is sized by combo
        # frequency, not pool membership.
        pos_range = self._pos_open_ranges.get(pos, self._pos_open_ranges["BTN"])

        if is_unopened:
            in_range = hk in pos_range
            # Loose archetypes — recreational players LIMP some weak hands
            # instead of folding. Toggle limp via BET (or CALL when limping
            # behind) on a small extra slice. Capped so realized VPIP doesn't
            # overshoot the target.
            if (not in_range and self.profile.pfr < self.profile.vpip - 8
                    and hk in TRASH_PLAYABLE_VS_LIMP):
                limp_chance = (self.profile.vpip - self.profile.pfr) / 80.0
                if random.random() < limp_chance:
                    if ActionType.CALL in valid_types:
                        return ActionType.CALL, to_call
                    if ActionType.CHECK in valid_types:
                        return ActionType.CHECK, 0.0

            if in_range:
                # PFR vs limp/call split — passive archetypes call more, raise less
                pfr_share = (self.profile.pfr / max(self.profile.vpip, 1e-6))
                pfr_share = max(0.0, min(1.0, pfr_share))
                if random.random() < pfr_share and ActionType.RAISE in valid_types:
                    if pos in ("UTG", "UTG+1"):
                        open_to = 3.0 * bb
                    elif pos in ("SB", "SB/BTN"):
                        open_to = 3.0 * bb
                    else:
                        open_to = 2.3 * bb
                    amount = max(open_to - player.current_bet, bb)
                    amount = min(amount, player.stack)
                    return ActionType.RAISE, amount
                if random.random() < pfr_share and ActionType.BET in valid_types:
                    return ActionType.BET, max(bb * 3, bb)
                # Else — limp / call
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                if ActionType.CHECK in valid_types:
                    return ActionType.CHECK, 0.0

            if ActionType.CHECK in valid_types:
                return ActionType.CHECK, 0.0
            return ActionType.FOLD, 0.0

        # FACING A RAISE
        # Determine raiser's position class (proxy: bet size relative to BB)
        if state.current_bet >= bb * 8:
            # 4-bet or higher facing us — very tight
            three_bet_pool = THREE_BET_RANGES["vs_early"]
            premium_only = {"AA", "KK", "QQ", "AKs", "AKo"}
            if hk in premium_only:
                # 5-bet shove or call
                if random.random() < 0.6 and ActionType.RAISE in valid_types:
                    # Jam
                    return ActionType.ALL_IN, player.stack
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
            if hk in {"JJ", "TT", "AKo", "AQs"} and self.profile.call_3bet > 0.25:
                if ActionType.CALL in valid_types and random.random() < 0.5:
                    return ActionType.CALL, to_call
            return ActionType.FOLD, 0.0 if ActionType.FOLD in valid_types else (ActionType.CHECK, 0.0)

        # Single raise — choose call / 3-bet / fold
        ip = pos in ("BTN", "CO")
        three_bet_pool = self._3bet_pool_ip if ip else self._3bet_pool_oop
        call_pool = self._call_pool
        in_3bet = hk in three_bet_pool
        in_call = hk in call_pool

        # Archetype overlays — passive players never 3-bet light, maniacs
        # 3-bet with extra suited bluffs.
        if self.profile.aggression < 1.2 and hk not in PREMIUM:
            in_3bet = False
        if self.profile.aggression > 3.8 and hk in {"76s", "65s", "54s", "A5s", "A4s"}:
            in_3bet = True

        # 3-bet decision — fire if hand is in our 3-bet range
        if in_3bet and ActionType.RAISE in valid_types:
            three_bet_to = (3.0 if ip else 3.5) * state.current_bet
            amount = three_bet_to - player.current_bet
            amount = max(amount, state.min_raise)
            amount = min(amount, player.stack)
            return ActionType.RAISE, amount

        # Call — Stations / loose-passive call WAY wider, nits tight
        if in_call and ActionType.CALL in valid_types:
            pot_odds = to_call / (state.pot + to_call) if (state.pot + to_call) > 0 else 1.0
            implied_threshold = 0.32 + (0.06 if hk in PREMIUM | STRONG else 0)
            if pot_odds < implied_threshold + (self.profile.call_down * 0.20):
                return ActionType.CALL, to_call

        # Premium pairs always continue
        if hk in {"AA", "KK", "QQ", "JJ"} and ActionType.CALL in valid_types:
            return ActionType.CALL, to_call

        if ActionType.FOLD in valid_types:
            return ActionType.FOLD, 0.0
        if ActionType.CHECK in valid_types:
            return ActionType.CHECK, 0.0
        return self._fallback(valid_types, valid)

    # ── POSTFLOP ───────────────────────────────────────────────────

    def _postflop(self, state: HandState, idx: int, player: PlayerSeat,
                  valid: List[Tuple[ActionType, float, float]]) -> Tuple[ActionType, float]:
        valid_types = {v[0] for v in valid}
        strength, draws, made_hand = self._hand_strength(player.hole_cards, state.community)
        to_call = state.to_call(idx)
        pot = max(state.pot, 0.01)
        spr = player.stack / pot

        # Was this player the preflop aggressor?
        is_aggressor = self._is_preflop_aggressor(state, idx)

        # Board texture features
        board_features = self._board_features(state.community)
        # In-position?
        in_position = self._in_position(state, idx)

        agg = self.profile.aggression
        random_noise = random.gauss(0, 0.05)
        adj_strength = max(0.0, min(1.0, strength + random_noise))

        # ── FACING A BET ──
        if to_call > 0:
            pot_odds = to_call / (pot + to_call)
            need_equity = pot_odds
            # Profile fold tendency — drives realised fold-to-cbet directly
            fold_freq = self.profile.fold_to_cbet / 100.0   # 0..1
            call_down_boost = self.profile.call_down * 0.30  # stations call light

            # ── STRONG MADE HANDS (≥ 0.78) ─────────────────────────────────────
            # Raise frequently (scale with aggression). Never fold.
            # Aggression factor (bets+raises)/calls is driven by `agg`:
            #   - Nit (1.5) raises ~27% of strong hands → mostly calls
            #   - Maniac (4.6) raises ~84% → almost always raises
            if adj_strength >= 0.78:
                raise_freq = max(0.05, min(0.92, agg / 5.5))
                if ActionType.RAISE in valid_types and random.random() < raise_freq:
                    return self._raise_size(state, valid, polarized=adj_strength > 0.85,
                                            strength=adj_strength)
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                return ActionType.ALL_IN, player.stack

            # ── MEDIUM MADE HANDS (0.48–0.78): top pair / overpair / high underpair ──
            # Threshold lowered to 0.48 so high underpairs (KK/QQ/JJ, now ~0.50-0.58)
            # reach this path rather than folding at the full marginal-fold rate.
            # Tight archetypes fold some medium hands; aggressive archetypes raise thin value.
            if adj_strength >= 0.48:
                bet_size_pot = to_call / pot
                # strength_norm: 0 at the bottom of medium band (0.48), 1 at 0.78
                strength_norm = min(1.0, (adj_strength - 0.48) / 0.30)

                if bet_size_pot > 1.0 and adj_strength < 0.72:
                    # Big overbet (>1x pot) — blend call_down willingness with fold_freq.
                    # Fish (call_down=0.62): call_prob=0.649 → ~35% fold ✓
                    # Reg  (call_down=0.36): call_prob=0.432 → ~57% fold ✓
                    # Rock (call_down=0.15): call_prob=0.321 → ~68% fold ✓
                    call_prob = (self.profile.call_down * 0.70
                                 + (1.0 - fold_freq) * 0.30)
                    call_prob = max(0.05, min(0.92, call_prob))
                    if random.random() > call_prob and ActionType.FOLD in valid_types:
                        return ActionType.FOLD, 0.0
                else:
                    # Normal-sized bet — fold scales with archetype tightness and
                    # inversely with strength inside the medium band.
                    # Coefficient 1.20 (reduced from 1.50) keeps FCB in range
                    # for mid-tight archetypes (TAG fold_freq=0.55, Solver 0.52).
                    medium_fold = fold_freq * 1.20 * (1.0 - strength_norm)
                    medium_fold = max(0.0, min(0.88, medium_fold))
                    if random.random() < medium_fold and ActionType.FOLD in valid_types:
                        return ActionType.FOLD, 0.0

                # All archetypes raise some medium hands (thin value / float raise).
                # Rate scales with aggression: Rock (1.0) → 0%, Reg (2.7) → 15%,
                # LAG (3.6) → 36%, Maniac (4.6) → 58%.
                medium_raise_chance = max(0.0, (agg - 2.0) * 0.22)
                if (ActionType.RAISE in valid_types
                        and state.street != Street.RIVER
                        and random.random() < medium_raise_chance):
                    return self._raise_size(state, valid, polarized=False,
                                            strength=adj_strength)
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                return ActionType.FOLD, 0.0

            # ── DRAWS — semi-bluff raise (low freq) or call (getting odds) ─────
            if draws > 0 and draws > need_equity - 0.05:
                if (state.street != Street.RIVER
                        and ActionType.RAISE in valid_types
                        and random.random() < (agg / 10)):
                    return self._raise_size(state, valid, polarized=False,
                                            strength=adj_strength)
                if ActionType.CALL in valid_types and random.random() < (1 - fold_freq * 0.5):
                    return ActionType.CALL, to_call

            # ── MARGINAL / WEAK HANDS ────────────────────────────────────────────
            # fold_to_cbet is the primary driver.
            # Multiplier 1.50 gives tight bots (Rock/Nit/Bubble Nit) a high
            # marginal-fold rate that, combined with medium-hand folds, produces
            # an overall FCB close to their declared target.
            # Cap at 0.97 (not 1.0) so there's always a tiny call/raise chance.
            marginal_fold = (fold_freq * 1.50
                             - adj_strength * 0.20
                             - self.profile.call_down * 0.12)
            marginal_fold = max(0.04, min(0.97, marginal_fold))
            if random.random() < marginal_fold:
                if ActionType.FOLD in valid_types:
                    return ActionType.FOLD, 0.0
                return ActionType.CHECK, 0.0
            # High-aggression bots bluff-raise some marginal hands (Maniac / LAG AF).
            # Increased multiplier (0.28 vs old 0.18) and lowered threshold (2.8 vs 3.2)
            # so the raise rate is: LAG(3.6)→22%, AggFish(3.9)→30%, Maniac(4.6)→50%.
            if (agg > 2.8 and ActionType.RAISE in valid_types
                    and state.street != Street.RIVER
                    and random.random() < (agg - 2.8) * 0.28):
                return self._raise_size(state, valid, polarized=False,
                                        strength=adj_strength)
            if ActionType.CALL in valid_types:
                # Don't call massive overbets without showdown value
                if to_call / pot > 1.6 and adj_strength < 0.40:
                    return ActionType.FOLD, 0.0
                return ActionType.CALL, to_call
            if ActionType.FOLD in valid_types:
                return ActionType.FOLD, 0.0
            return ActionType.CHECK, 0.0

        # ── NO BET — CHECK OR BET ──
        # C-bet decision (aggressor on flop)
        if state.street == Street.FLOP and is_aggressor:
            # C-bet frequency scales with archetype aggression as the primary driver.
            # Passive bots (Rock agg=1.0) c-bet ~25% so they protect their
            # checking range; Maniac (agg=4.6) fires ~80%+ on most boards.
            agg_scale = max(0.20, min(1.20, agg / 2.5))
            cbet_freq = 0.50 * agg_scale
            if board_features["high_card"] >= 12:  # A or K high → PF-raiser range advantage
                cbet_freq += 0.13
            if board_features["paired"]:            # Paired board → raise range advantage
                cbet_freq += 0.18
            if board_features["monotone"]:
                cbet_freq -= 0.18
            if board_features["wet"] and adj_strength < 0.5:
                cbet_freq -= 0.10
            # Passive archetypes (agg ≤ 1.5): almost never c-bet bluff —
            # they need a real hand to fire, protecting their checking range.
            if agg <= 1.5 and adj_strength < 0.55:
                cbet_freq *= 0.28
            cbet_freq = max(0.08, min(0.95, cbet_freq))

            if random.random() < cbet_freq:
                # Sizing: small on dry boards, big on wet/polarized
                if board_features["paired"] or board_features["dry"]:
                    size = self._bet_amount(pot, 0.33, valid)
                elif adj_strength > 0.75 or adj_strength < 0.30:
                    # Polarized big bet
                    size = self._bet_amount(pot, 0.75, valid)
                else:
                    size = self._bet_amount(pot, 0.50, valid)
                if size:
                    return ActionType.BET, size

            return ActionType.CHECK, 0.0

        # Strong made hand — bet for value (frequency scales with aggression).
        # Removed the 0.20 floor: Rock (agg=1.0) → 15%, Maniac (4.6) → 70%.
        # Previously the floor caused Rock/Nit to bet 43%+ even as passive bots.
        if adj_strength >= 0.72:
            value_bet_freq = min(0.95, max(0.05, agg / 5.0 * 0.76))
            if ActionType.BET in valid_types and random.random() < value_bet_freq:
                size_pct = 0.66 if adj_strength < 0.85 else 0.85
                if random.random() < self.profile.overbet_freq:
                    size_pct = 1.5
                amt = self._bet_amount(pot, size_pct, valid)
                if amt:
                    return ActionType.BET, amt
            return ActionType.CHECK, 0.0

        # Medium hand — thin value bet on later streets, scales with aggression
        if adj_strength >= 0.50:
            thin_value_freq = max(0.02, (agg - 1.0) * 0.12)
            if (ActionType.BET in valid_types
                    and state.street != Street.FLOP
                    and random.random() < thin_value_freq):
                amt = self._bet_amount(pot, 0.45, valid)
                if amt:
                    return ActionType.BET, amt
            return ActionType.CHECK, 0.0

        # Weak — bluff: river uses profile.bluff_river; flop/turn uses
        # aggression-scaled freq so Maniacs barrel and Nits give up.
        if state.street == Street.RIVER:
            if ActionType.BET in valid_types and random.random() < self.profile.bluff_river:
                amt = self._bet_amount(pot, 0.66, valid)
                if amt:
                    return ActionType.BET, amt
        else:
            # Pure-bluff frequency scales steeply with aggression so high-AF
            # archetypes (Maniac 4.6, Aggro Fish 3.9, LAG 3.6) barrel a lot.
            bluff_freq = max(0.0, (agg - 1.5) * 0.18) + (draws * 0.30 if draws else 0)
            if ActionType.BET in valid_types and bluff_freq > 0 and random.random() < bluff_freq:
                amt = self._bet_amount(pot, 0.55, valid)
                if amt:
                    return ActionType.BET, amt

        return ActionType.CHECK, 0.0 if ActionType.CHECK in valid_types else (ActionType.FOLD, 0.0)

    # ── HELPERS ────────────────────────────────────────────────────

    def _bet_amount(self, pot: float, pct: float, valid: List[Tuple[ActionType, float, float]]) -> float:
        bet_info = next((v for v in valid if v[0] == ActionType.BET), None)
        if not bet_info:
            return 0.0
        target = pot * pct
        return round(max(bet_info[1], min(bet_info[2], target)), 2)

    def _raise_size(self, state: HandState, valid: List[Tuple[ActionType, float, float]],
                    polarized: bool, strength: float = 0.5) -> Tuple[ActionType, float]:
        """Return the best raise/bet action.

        If RAISE is not in the valid set (e.g. we already face a re-raise and
        only CALL / ALL_IN / FOLD remain), we shove ONLY when:
          - hand is strong (strength ≥ 0.72), OR
          - stack-to-pot is tiny (< 1.0) so calling is nearly the same as jamming.
        Otherwise we prefer CALL — the bot must never go all-in with 76s just
        because the raise button is unavailable.
        """
        raise_info = next((v for v in valid if v[0] == ActionType.RAISE), None)
        if not raise_info:
            allin = next((v for v in valid if v[0] == ActionType.ALL_IN), None)
            if allin:
                spr = allin[1] / max(state.pot, 0.01)
                if strength >= 0.72 or spr < 1.0:
                    return ActionType.ALL_IN, allin[1]
            # Prefer call over a reckless all-in
            call_info = next((v for v in valid if v[0] == ActionType.CALL), None)
            if call_info:
                return ActionType.CALL, call_info[1]
            return ActionType.CHECK, 0.0
        # Raise amount = min_raise * factor (polarized = bigger)
        factor = 1.6 if polarized else 1.25
        amount = max(raise_info[1], min(raise_info[2], round(raise_info[1] * factor, 2)))
        return ActionType.RAISE, amount

    def _hand_strength(self, hole: List[Card], board: List[Card]) -> Tuple[float, float, str]:
        """Return (strength 0-1, draw_equity 0-1, label)."""
        if not hole:
            return 0.0, 0.0, "—"

        c1, c2 = hole[0], hole[1]
        v1, v2 = c1.value, c2.value
        high, low = max(v1, v2), min(v1, v2)
        suited = c1.suit == c2.suit
        is_pair = v1 == v2

        if not board:
            # Preflop strength
            if is_pair:
                strength = 0.50 + high * 0.038
            else:
                strength = 0.25 + high * 0.028 + low * 0.012
                if suited:
                    strength += 0.04
                strength -= (high - low) * 0.008
            return max(0.05, min(0.95, strength)), 0.0, "preflop"

        # Postflop — analyze hand
        all_ranks = [c1.value, c2.value] + [c.value for c in board]
        all_suits = [c1.suit, c2.suit] + [c.suit for c in board]
        board_ranks = [c.value for c in board]
        board_suits = [c.suit for c in board]

        # Count rank occurrences
        rank_counts = {r: all_ranks.count(r) for r in set(all_ranks)}
        max_rank_count = max(rank_counts.values())

        # Pair detection
        pair_with_board_high = c1.value in board_ranks or c2.value in board_ranks
        is_overpair = is_pair and v1 > max(board_ranks, default=0)

        # Suited connections / flush
        suit_counts = {s: all_suits.count(s) for s in set(all_suits)}
        max_suit_count = max(suit_counts.values()) if suit_counts else 0
        hero_suits_in_max = sum(1 for s in (c1.suit, c2.suit) if all_suits.count(s) >= 4)

        # Straight check (rough)
        unique_ranks = sorted(set(all_ranks))
        straight_outs = 0
        has_straight = False
        # Check for 5 consecutive
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i + 4] - unique_ranks[i] == 4:
                has_straight = True
                break
        # Open-ended draw (8 outs) + Gutshot (4 outs)
        if not has_straight:
            # OESD: 4 consecutive in unique_ranks (range diff == 3)
            for i in range(len(unique_ranks) - 3):
                if (unique_ranks[i + 3] - unique_ranks[i] == 3
                        and (high in unique_ranks[i:i + 4]
                             or low in unique_ranks[i:i + 4])):
                    straight_outs = 8
                    break
            # Gutshot: 4 consecutive with 1 gap (5 cards spanning 4 unique values,
            # one value missing inside the span). 4 outs.
            if straight_outs == 0:
                for i in range(len(unique_ranks) - 3):
                    span = unique_ranks[i + 3] - unique_ranks[i]
                    if span == 4 and (high in unique_ranks[i:i + 4]
                                       or low in unique_ranks[i:i + 4]):
                        straight_outs = 4
                        break

        # Score
        label = "high card"
        strength = 0.12
        if max_rank_count >= 4:
            strength = 0.98; label = "quads"
        elif max_rank_count == 3 and any(v == 2 for v in rank_counts.values()):
            strength = 0.96; label = "full house"
        elif max_suit_count >= 5 and hero_suits_in_max:
            strength = 0.92; label = "flush"
        elif has_straight:
            strength = 0.85; label = "straight"
        elif max_rank_count == 3:
            if is_pair:
                strength = 0.88; label = "set"
            else:
                strength = 0.74; label = "trips"
        elif sum(1 for c in rank_counts.values() if c == 2) >= 2:
            # Two pair — distinguish "top two" (both hole cards paired top/2nd)
            # from "weaker two pair" (e.g. bottom pair + middle).
            sorted_board = sorted(board_ranks, reverse=True)
            top_board = sorted_board[0] if sorted_board else 0
            second_board = sorted_board[1] if len(sorted_board) > 1 else 0
            hole_vals = {c1.value, c2.value}
            # Top two: both hole cards match top + second board
            if top_board in hole_vals and second_board in hole_vals and v1 != v2:
                strength = 0.78; label = "top two pair"
            else:
                strength = 0.66; label = "two pair"
        elif is_overpair:
            strength = 0.62; label = "overpair"
        elif pair_with_board_high:
            # Top pair / mid pair — use matching hole card + kicker for accurate strength.
            # Old code only used max(hole), which gave AK and A2 the same value
            # on A-high boards. Now AK = 0.69, A2 = 0.55 (kicker matters).
            matching = [v for v in (c1.value, c2.value) if v in board_ranks]
            paired_rank = max(matching) if matching else 0
            kicker_vals = [v for v in (c1.value, c2.value) if v not in board_ranks]
            kicker = max(kicker_vals) if kicker_vals else 0
            top_board = max(board_ranks)
            if paired_rank == top_board:
                # Top pair: base 0.50 + 0.10 for top board + 0.08 for kicker
                # AK on K72: 0.50 + 1.0*0.10 + 14/13*0.08 = 0.686
                # A2 on A72: 0.50 + 1.0*0.10 + 2/13*0.08 = 0.612
                strength = (0.50
                            + (paired_rank / 13) * 0.10
                            + (kicker / 13) * 0.08)
                label = "top pair"
            else:
                # Middle/bottom pair — scales with paired rank + kicker
                # K9 on Q93: 0.35 + 9/13*0.10 + 13/13*0.06 = 0.479
                # 22 on 962: 0.35 + 2/13*0.10 + 9/13*0.06 = 0.407
                strength = (0.35
                            + (paired_rank / 13) * 0.10
                            + (kicker / 13) * 0.06)
                label = "middle pair"
        elif is_pair:
            # Scale underpair strength by pair rank so KK on A-high doesn't fold like 22.
            # 22 → 0.30, TT → 0.50, KK → 0.58 (approaches medium-hand zone)
            pair_val = v1  # v1 == v2 for a pair
            strength = 0.30 + (pair_val - 2) / 11 * 0.28
            label = "underpair"

        # Draw equity (rough outs / runners)
        draws = 0.0
        if max_suit_count == 4 and hero_suits_in_max:
            # Flush draw: ~9 outs ~ 36% turn+river, ~18% one-card to come
            draws = 0.35 if len(board) <= 3 else 0.18
        if straight_outs == 8:           # OESD ~32% / 18%
            draws = max(draws, 0.32 if len(board) <= 3 else 0.18)
        elif straight_outs == 4:         # Gutshot ~16% / 9%
            draws = max(draws, 0.16 if len(board) <= 3 else 0.09)
        # Backdoor flush (3 of one suit on flop, need 2 more) — small bump
        if len(board) == 3 and max_suit_count == 3 and hero_suits_in_max:
            draws = max(draws, 0.04)
        # Combo draw bonus: pair + draw → significantly stronger semi-bluff
        # (e.g. middle pair + flush draw on turn ≈ 50% equity vs random)
        if draws > 0.20 and strength >= 0.35:
            # Boost strength slightly to reflect the made-hand+draw combo
            strength = min(0.78, strength + 0.05)

        return strength, draws, label

    def _board_features(self, board: List[Card]) -> dict:
        if not board:
            return {"paired": False, "monotone": False, "wet": False, "dry": True, "high_card": 0}
        ranks = [c.value for c in board]
        suits = [c.suit for c in board]
        suit_counts = {s: suits.count(s) for s in set(suits)}
        rank_counts = {r: ranks.count(r) for r in set(ranks)}
        paired = max(rank_counts.values()) >= 2
        monotone = max(suit_counts.values()) >= 3
        two_tone = max(suit_counts.values()) == 2
        max_rank = max(ranks)
        # Wet = connected + draws possible
        sorted_r = sorted(set(ranks))
        connectedness = 0
        for i in range(len(sorted_r) - 1):
            if sorted_r[i + 1] - sorted_r[i] <= 2:
                connectedness += 1
        wet = connectedness >= 2 or two_tone
        dry = not wet and not paired
        return {
            "paired": paired,
            "monotone": monotone,
            "two_tone": two_tone,
            "wet": wet,
            "dry": dry,
            "high_card": max_rank,
            "connectedness": connectedness,
        }

    def _is_preflop_aggressor(self, state: HandState, idx: int) -> bool:
        last_raiser = None
        for a in state.actions:
            if a.street == Street.PREFLOP and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                last_raiser = a.player_idx
        return last_raiser == idx

    def _in_position(self, state: HandState, idx: int) -> bool:
        # If we're the last to act on this street (excluding all-in), we're IP
        n = len(state.players)
        actives = [i for i, p in enumerate(state.players) if p.is_active]
        if not actives:
            return False
        return actives[-1] == idx

    def _fallback(self, valid_types: set, valid: List[Tuple[ActionType, float, float]]) -> Tuple[ActionType, float]:
        if ActionType.CHECK in valid_types:
            return ActionType.CHECK, 0.0
        if ActionType.FOLD in valid_types:
            return ActionType.FOLD, 0.0
        info = valid[0]
        return info[0], info[1]
