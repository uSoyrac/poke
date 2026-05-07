from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.engine.hand_state import (
    ActionType, Card, HandState, PlayerSeat, Street, RANK_VALUES,
)


@dataclass
class BotProfile:
    """Bot archetype with tunable frequencies."""
    name: str
    vpip: float        # Voluntarily put $ in pot (0-100)
    pfr: float         # Preflop raise frequency
    three_bet: float   # 3bet frequency
    fold_to_cbet: float
    aggression: float  # Postflop aggression (0-5 scale)
    river_bluff: float
    call_down: float   # Tendency to call down light
    overbet_freq: float = 0.05

    @property
    def tightness(self) -> float:
        """0=very loose, 1=very tight."""
        return max(0, min(1, 1 - self.vpip / 100))


# Pre-built bot archetypes
BOT_ARCHETYPES = {
    "TAG": BotProfile("TAG", 22, 18, 8, 55, 2.5, 0.25, 0.35),
    "LAG": BotProfile("LAG", 32, 26, 12, 40, 3.5, 0.40, 0.45),
    "Nit": BotProfile("Nit", 14, 12, 5, 70, 1.5, 0.10, 0.20),
    "Calling Station": BotProfile("Calling Station", 40, 8, 3, 20, 0.8, 0.08, 0.75),
    "Maniac": BotProfile("Maniac", 50, 35, 18, 25, 4.5, 0.55, 0.50),
    "Reg": BotProfile("Reg", 24, 20, 9, 50, 2.8, 0.30, 0.38),
    "Fish": BotProfile("Fish", 45, 10, 4, 30, 1.2, 0.15, 0.60),
    "Shark": BotProfile("Shark", 20, 17, 10, 58, 3.0, 0.35, 0.30),
    "Rock": BotProfile("Rock", 12, 10, 4, 75, 1.0, 0.05, 0.15),
    "Aggro Fish": BotProfile("Aggro Fish", 48, 30, 8, 28, 3.8, 0.45, 0.55),
    "Tight Passive": BotProfile("Tight Passive", 18, 8, 3, 65, 0.7, 0.05, 0.40),
    "Balanced Reg": BotProfile("Balanced Reg", 25, 21, 10, 48, 2.7, 0.28, 0.35),
}


class BotBrain:
    """Decision engine for bot players."""

    def __init__(self, profile: BotProfile):
        self.profile = profile

    def decide(
        self,
        state: HandState,
        player_idx: int,
    ) -> Tuple[ActionType, float]:
        """Return (action_type, amount) for the bot's decision."""
        valid = state.get_valid_actions(player_idx)
        if not valid:
            return ActionType.CHECK, 0

        player = state.players[player_idx]
        hand_strength = self._estimate_strength(player, state)

        if state.street == Street.PREFLOP:
            return self._preflop_decision(state, player_idx, player, hand_strength, valid)
        else:
            return self._postflop_decision(state, player_idx, player, hand_strength, valid)

    def _estimate_strength(self, player: PlayerSeat, state: HandState) -> float:
        """Estimate hand strength 0-1 based on hole cards and board."""
        if not player.hole_cards:
            return 0.3

        c1, c2 = player.hole_cards[0], player.hole_cards[1]
        v1, v2 = c1.value, c2.value
        high, low = max(v1, v2), min(v1, v2)
        suited = c1.suit == c2.suit

        # Base preflop strength
        if v1 == v2:  # Pocket pair
            strength = 0.50 + high * 0.038
        else:
            strength = 0.25 + high * 0.028 + low * 0.012
            if suited:
                strength += 0.04
            gap = high - low
            strength -= gap * 0.008

        # Board connection bonus
        if state.community:
            board_values = [c.value for c in state.community]
            board_suits = [c.suit for c in state.community]

            # Pair with board
            if high in board_values:
                strength += 0.20
            if low in board_values:
                strength += 0.12

            # Two pair or better bonus
            if high in board_values and low in board_values:
                strength += 0.15

            # Flush draw
            hero_suits = [c1.suit, c2.suit]
            for s in set(hero_suits):
                flush_count = sum(1 for bs in board_suits if bs == s) + sum(1 for hs in hero_suits if hs == s)
                if flush_count >= 4:
                    strength += 0.12
                elif flush_count >= 3:
                    strength += 0.05

            # Straight connectivity
            all_vals = sorted(set([high, low] + board_values))
            for i in range(len(all_vals) - 3):
                if all_vals[i+3] - all_vals[i] <= 4:
                    strength += 0.08
                    break

            # Overpair
            if v1 == v2 and v1 > max(board_values):
                strength += 0.18

        return max(0.02, min(0.98, strength))

    def _preflop_decision(
        self, state: HandState, player_idx: int, player: PlayerSeat,
        strength: float, valid: List[Tuple[ActionType, float, float]],
    ) -> Tuple[ActionType, float]:
        """Preflop strategy based on profile."""
        valid_types = {v[0] for v in valid}
        to_call = state.current_bet - player.current_bet

        # Threshold for entering the pot
        enter_threshold = 1.0 - (self.profile.vpip / 100)
        raise_threshold = 1.0 - (self.profile.pfr / 100)

        # Add randomness
        noise = random.gauss(0, 0.06)
        adj_strength = strength + noise

        if adj_strength < enter_threshold:
            if ActionType.CHECK in valid_types:
                return ActionType.CHECK, 0
            return ActionType.FOLD, 0

        # Decide between call and raise
        if adj_strength >= raise_threshold:
            # Raise
            if ActionType.RAISE in valid_types:
                raise_info = next(v for v in valid if v[0] == ActionType.RAISE)
                min_raise, max_raise = raise_info[1], raise_info[2]
                sizing = self._pick_raise_sizing(min_raise, max_raise, strength, state)
                return ActionType.RAISE, sizing
            elif ActionType.BET in valid_types:
                bet_info = next(v for v in valid if v[0] == ActionType.BET)
                sizing = self._pick_bet_sizing(bet_info[1], bet_info[2], strength, state)
                return ActionType.BET, sizing

        # Call
        if ActionType.CALL in valid_types:
            call_info = next(v for v in valid if v[0] == ActionType.CALL)
            return ActionType.CALL, call_info[1]

        if ActionType.CHECK in valid_types:
            return ActionType.CHECK, 0
        return ActionType.FOLD, 0

    def _postflop_decision(
        self, state: HandState, player_idx: int, player: PlayerSeat,
        strength: float, valid: List[Tuple[ActionType, float, float]],
    ) -> Tuple[ActionType, float]:
        """Postflop strategy using hand strength + pot odds + aggression."""
        valid_types = {v[0] for v in valid}
        to_call = state.current_bet - player.current_bet
        pot = state.pot

        # Pot odds check for calling
        if to_call > 0:
            pot_odds = to_call / (pot + to_call) if (pot + to_call) > 0 else 1
        else:
            pot_odds = 0

        noise = random.gauss(0, 0.08)
        adj_strength = strength + noise

        # Strong hand — bet or raise
        if adj_strength > 0.65:
            agg_roll = random.random()
            if agg_roll < self.profile.aggression / 5.0:
                if ActionType.RAISE in valid_types:
                    info = next(v for v in valid if v[0] == ActionType.RAISE)
                    sizing = self._pick_raise_sizing(info[1], info[2], strength, state)
                    return ActionType.RAISE, sizing
                if ActionType.BET in valid_types:
                    info = next(v for v in valid if v[0] == ActionType.BET)
                    sizing = self._pick_bet_sizing(info[1], info[2], strength, state)
                    return ActionType.BET, sizing
            if ActionType.CALL in valid_types:
                info = next(v for v in valid if v[0] == ActionType.CALL)
                return ActionType.CALL, info[1]
            return ActionType.CHECK, 0

        # Medium hand — call or check
        if adj_strength > 0.40:
            if to_call > 0 and adj_strength > pot_odds:
                # Call if have equity
                call_chance = self.profile.call_down + (adj_strength - 0.40)
                if random.random() < call_chance:
                    if ActionType.CALL in valid_types:
                        info = next(v for v in valid if v[0] == ActionType.CALL)
                        return ActionType.CALL, info[1]

            # Sometimes bet as semi-bluff
            if to_call == 0 and random.random() < self.profile.aggression / 8.0:
                if ActionType.BET in valid_types:
                    info = next(v for v in valid if v[0] == ActionType.BET)
                    sizing = self._pick_bet_sizing(info[1], info[2], 0.4, state)
                    return ActionType.BET, sizing

            if ActionType.CHECK in valid_types:
                return ActionType.CHECK, 0
            return ActionType.FOLD, 0

        # Weak hand — bluff sometimes or fold
        if to_call == 0:
            # Bluff opportunity
            bluff_chance = self.profile.river_bluff if state.street == Street.RIVER else self.profile.aggression / 10.0
            if random.random() < bluff_chance:
                if ActionType.BET in valid_types:
                    info = next(v for v in valid if v[0] == ActionType.BET)
                    sizing = self._pick_bet_sizing(info[1], info[2], 0.3, state)
                    return ActionType.BET, sizing
            return ActionType.CHECK, 0

        if ActionType.FOLD in valid_types:
            return ActionType.FOLD, 0
        return ActionType.CHECK, 0

    def _pick_bet_sizing(self, min_bet: float, max_bet: float, strength: float, state: HandState) -> float:
        """Choose bet sizing based on strength and profile."""
        pot = max(state.pot, 1)
        options = [
            pot * 0.33,  # Small
            pot * 0.50,  # Half pot
            pot * 0.66,  # Two-thirds
            pot * 0.75,  # Three-quarters
            pot * 1.00,  # Full pot
        ]
        if random.random() < self.profile.overbet_freq:
            options.append(pot * 1.50)

        # Stronger hands bet bigger (polarized)
        if strength > 0.75:
            preferred = random.choice(options[2:])
        elif strength > 0.50:
            preferred = random.choice(options[1:4])
        else:
            preferred = random.choice(options[:3])

        return max(min_bet, min(max_bet, round(preferred, 1)))

    def _pick_raise_sizing(self, min_raise: float, max_raise: float, strength: float, state: HandState) -> float:
        """Choose raise sizing."""
        pot = max(state.pot, 1)
        base = state.current_bet

        if state.street == Street.PREFLOP:
            # Standard raises
            options = [base * 2.5, base * 3.0, base * 3.5]
        else:
            options = [base + pot * 0.5, base + pot * 0.75, base + pot * 1.0]

        if strength > 0.80 and random.random() < 0.15:
            return max_raise  # All-in

        preferred = random.choice(options)
        return max(min_raise, min(max_raise, round(preferred, 1)))
