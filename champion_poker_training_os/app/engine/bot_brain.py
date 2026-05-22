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

    # ── PUBLIC API ─────────────────────────────────────────────────

    def decide(self, state: HandState, player_idx: int) -> Tuple[ActionType, float]:
        valid = state.get_valid_actions(player_idx)
        if not valid:
            return ActionType.CHECK, 0.0

        player = state.players[player_idx]
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

        # Archetype tightness scaler
        loose = (self.profile.vpip - 22) / 22.0  # -1 (nit) to +1.5 (maniac)
        loose = max(-1.0, min(1.5, loose))

        # Determine effective open range
        base = OPEN_RANGES.get(pos, OPEN_RANGES["BTN"])

        if is_unopened:
            # UNOPENED POT — RFI decision
            in_range = hk in base
            # Loosen/tighten by archetype
            if not in_range and loose > 0.5 and (hk in MEDIUM or hk in SPECULATIVE or hk in TRASH_PLAYABLE_VS_LIMP):
                in_range = random.random() < (loose - 0.3)
            if in_range and loose < -0.3 and hk not in PREMIUM | STRONG:
                in_range = random.random() < (1 + loose * 0.7)

            if in_range and ActionType.RAISE in valid_types:
                # Open raise sizing: 2.5x preflop standard, 2.2x in CO/BTN, 3x in early
                if pos in ("UTG", "UTG+1"):
                    open_to = 3.0 * bb
                elif pos in ("SB", "SB/BTN"):
                    open_to = 3.0 * bb
                else:
                    open_to = 2.3 * bb
                amount = max(open_to - player.current_bet, bb)
                amount = min(amount, player.stack)
                return ActionType.RAISE, amount
            if in_range and ActionType.BET in valid_types:
                # BB option vs limp
                return ActionType.BET, max(bb * 3, bb)
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
        three_bet_pool = THREE_BET_RANGES["vs_late"] if pos in ("BTN", "CO", "BB", "SB") else THREE_BET_RANGES["vs_early"]
        call_pool = base  # We can call with what we'd open
        in_3bet = hk in three_bet_pool
        in_call = hk in call_pool

        # Archetype tweaks
        if self.profile.aggression > 3.5 and hk in {"76s", "65s", "54s", "A5s", "A4s"}:
            in_3bet = True
        if self.profile.aggression < 1.5 and hk not in PREMIUM:
            in_3bet = False
        if self.profile.call_down > 0.6:
            in_call = in_call or hk in MEDIUM

        # 3-bet
        if in_3bet and ActionType.RAISE in valid_types and random.random() < (0.35 + self.profile.three_bet / 60):
            # 3-bet sizing: 3x the raise if IP, 4x if OOP
            ip = pos in ("BTN", "CO")
            three_bet_to = (3.0 if ip else 3.5) * state.current_bet
            amount = three_bet_to - player.current_bet
            amount = max(amount, state.min_raise)
            amount = min(amount, player.stack)
            return ActionType.RAISE, amount

        # Call
        if in_call and ActionType.CALL in valid_types:
            # Pot odds check
            pot_odds = to_call / (state.pot + to_call) if (state.pot + to_call) > 0 else 1
            implied_threshold = 0.30 + (0.05 if hk in PREMIUM | STRONG else 0)
            if pot_odds < implied_threshold + (self.profile.call_down * 0.15):
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
            # Required equity vs bet
            need_equity = pot_odds

            # Strong made hands → raise or call
            if adj_strength >= 0.78:  # Two pair or better
                if ActionType.RAISE in valid_types and random.random() < (agg / 5):
                    return self._raise_size(state, valid, polarized=adj_strength > 0.85)
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                return ActionType.ALL_IN, player.stack

            # Medium hands (top pair, overpairs) → call mostly
            if adj_strength >= 0.55:
                # If villain bet is overbet (> pot), need to be more selective
                bet_size_pot = to_call / pot
                if bet_size_pot > 1.2 and adj_strength < 0.70:
                    if random.random() < self.profile.call_down * 0.8 and ActionType.CALL in valid_types:
                        return ActionType.CALL, to_call
                    return ActionType.FOLD, 0.0
                if ActionType.CALL in valid_types:
                    return ActionType.CALL, to_call
                return ActionType.FOLD, 0.0

            # Draws — semi-bluff raise or call
            if draws > 0:
                draw_equity = draws  # 0-1 estimated
                if draw_equity > need_equity:
                    if random.random() < (agg / 8) and ActionType.RAISE in valid_types and state.street != Street.RIVER:
                        return self._raise_size(state, valid, polarized=False)
                    if ActionType.CALL in valid_types:
                        return ActionType.CALL, to_call

            # Bluff catchers — use MDF logic
            mdf = 1 - (to_call / (pot + to_call))
            should_defend = random.random() < (mdf * 0.85 + self.profile.call_down * 0.15)
            if adj_strength > 0.30 and should_defend and ActionType.CALL in valid_types:
                # Don't bluffcatch huge overbets without blockers
                if to_call / pot > 1.5 and adj_strength < 0.45:
                    return ActionType.FOLD, 0.0
                return ActionType.CALL, to_call

            # Otherwise fold
            return ActionType.FOLD, 0.0 if ActionType.FOLD in valid_types else (ActionType.CHECK, 0.0)

        # ── NO BET — CHECK OR BET ──
        # C-bet decision (aggressor on flop)
        if state.street == Street.FLOP and is_aggressor:
            # C-bet frequency: depends on board texture, range advantage, archetype
            cbet_freq = 0.55  # baseline
            if board_features["high_card"] >= 12:  # A or K high
                cbet_freq += 0.15
            if board_features["paired"]:
                cbet_freq += 0.20  # Range advantage on paired boards
            if board_features["monotone"]:
                cbet_freq -= 0.20
            if board_features["wet"] and adj_strength < 0.5:
                cbet_freq -= 0.10
            cbet_freq = max(0.15, min(0.95, cbet_freq + (agg - 2.5) * 0.08))

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

        # Strong made hand — bet for value
        if adj_strength >= 0.72:
            if ActionType.BET in valid_types and random.random() < (0.6 + agg / 10):
                size_pct = 0.66 if adj_strength < 0.85 else 0.85
                if random.random() < self.profile.overbet_freq:
                    size_pct = 1.5
                amt = self._bet_amount(pot, size_pct, valid)
                if amt:
                    return ActionType.BET, amt
            return ActionType.CHECK, 0.0

        # Medium hand — check / thin value
        if adj_strength >= 0.50:
            if state.street == Street.RIVER and random.random() < 0.30:
                amt = self._bet_amount(pot, 0.40, valid)
                if amt:
                    return ActionType.BET, amt
            return ActionType.CHECK, 0.0

        # Weak — bluff sometimes
        if state.street == Street.RIVER:
            if random.random() < self.profile.bluff_river:
                amt = self._bet_amount(pot, 0.66, valid)
                if amt:
                    return ActionType.BET, amt
        elif draws > 0 and random.random() < (agg / 10):
            # Semi-bluff with draws
            amt = self._bet_amount(pot, 0.50, valid)
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
                    polarized: bool) -> Tuple[ActionType, float]:
        raise_info = next((v for v in valid if v[0] == ActionType.RAISE), None)
        if not raise_info:
            allin = next((v for v in valid if v[0] == ActionType.ALL_IN), None)
            if allin:
                return ActionType.ALL_IN, allin[1]
            return ActionType.CALL, state.current_bet
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
        # Open-ended draw
        if not has_straight:
            for i in range(len(unique_ranks) - 3):
                if unique_ranks[i + 3] - unique_ranks[i] == 3 and (high in unique_ranks[i:i + 4] or low in unique_ranks[i:i + 4]):
                    straight_outs = 8
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
            strength = 0.68; label = "two pair"
        elif is_overpair:
            strength = 0.62; label = "overpair"
        elif pair_with_board_high:
            # Top pair / mid pair
            top_board = max(board_ranks)
            paired_rank = max(c1.value, c2.value) if (c1.value in board_ranks or c2.value in board_ranks) else 0
            if paired_rank == top_board:
                kicker = min(c1.value, c2.value) if c1.value == top_board or c2.value == top_board else 0
                strength = 0.50 + (high / 13) * 0.10
                label = "top pair"
            else:
                strength = 0.35
                label = "middle pair"
        elif is_pair:
            strength = 0.30
            label = "underpair"

        # Draw equity (rough outs / runners)
        draws = 0.0
        if max_suit_count == 4 and hero_suits_in_max:
            # Flush draw: ~9 outs ~ 36% turn+river, ~18% one-card
            draws = 0.35 if len(board) <= 3 else 0.18
        if straight_outs == 8:
            draws = max(draws, 0.32 if len(board) <= 3 else 0.18)

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
