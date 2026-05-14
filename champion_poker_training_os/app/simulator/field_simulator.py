"""Background field simulator for MTT — statistical model of the other tables.

Hero plays REAL hands at his table (PokerGame + BotBrain). The rest of the field
(say, 199 other players spread across ~22 other tables) is simulated as a fast
statistical random-walk on chip stacks, weighted by per-player skill, with bust
detection.

Why not simulate all 199 players for real?  ~30 hands/min × 199 players = 6000
bot decisions/min. Too slow, too much state, and not what actually matters for
hero's experience — what matters is: how many left, what's avg stack, when does
hero hit the money, what's hero's projected finish.

Model:
  • Each virtual player has a `skill` value 0..1 (from archetype mapping).
  • Each "round" (=~ 10 hands), every still-alive player's stack does a
    multiplicative random walk: stack *= exp(drift + noise).
    Drift is +ve for skill>0.5, -ve below. Noise is Gaussian.
  • Players with stack < 1 BB bust at end of round.
  • Bust order is the inverse of hero's finish projection: last to bust at the
    final hand = the winner.

Caller is expected to call `advance_round(hero_stack, big_blind)` after every
~10 hands played at hero's table. The simulator returns the list of newly-
busted virtual player ids so the UI can announce them in the mistake log.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Optional


# Archetype → skill rating (0..1). Bigger = better, survives longer.
_ARCH_SKILL = {
    "Nit":             0.42,
    "Rock":            0.40,
    "Tight Passive":   0.38,
    "Calling Station": 0.30,
    "Fish":            0.32,
    "Aggro Fish":      0.42,
    "Maniac":          0.45,
    "TAG":             0.62,
    "LAG":             0.66,
    "Reg":             0.60,
    "Balanced Reg":    0.65,
    "Shark":           0.74,
}


@dataclass
class VirtualPlayer:
    id:        int
    name:      str
    archetype: str
    skill:     float
    stack:     float
    bust_hand: int = 0      # hand number at which this player busted, 0 if alive

    @property
    def alive(self) -> bool:
        return self.bust_hand == 0


def _name_pool() -> list[str]:
    first = ["Anderson", "Clarissa", "Veronica", "Chris", "Johnnie", "Maxwell",
             "Jade", "Marc", "Craig", "Robert", "Felix", "Lena", "Daria",
             "Owen", "Priya", "Sam", "Rachel", "Logan", "Jason", "Kaleb",
             "Elise", "Mateo", "Yara", "Holden", "Karim", "Tessa", "Ronan",
             "Quincy", "Astrid", "Bilal", "Cosmo", "Doruk", "Esmé", "Farah",
             "Gizem", "Halil", "Ines", "Jonas", "Khan", "Liana"]
    last  = ["Maddox", "Hale", "Reese", "Barker", "Waller", "Page", "Walls",
             "Watts", "Tanner", "Holmes", "Reyes", "Spears", "Pratt", "Aguirre",
             "Hovath", "Armstrong", "Terrell", "Weinbrecht", "Cameron", "Voss",
             "Demir", "Çelik", "Aydın", "Yıldız", "Soyrac", "Akar", "Pehlivan"]
    pairs = []
    for f in first:
        for l in last:
            pairs.append(f"{f} {l}")
    return pairs


class FieldSimulator:
    """Statistical model of the other-tables field."""

    def __init__(
        self,
        field_size:      int,
        starting_stack:  int,
        skill_style:     str = "Human-Like",
        skill_level:     str = "Medium",
        hero_name:       str = "uygar",
        seed:            Optional[int] = None,
    ):
        self.field_size     = field_size
        self.starting_stack = starting_stack
        self.skill_style    = skill_style
        self.skill_level    = skill_level
        self.hero_name      = hero_name
        self.rng = random.Random(seed)
        self._hand_no = 0

        # Build virtual players (hero is id=0 but lives elsewhere — here we
        # only model the other (field_size - 1) virtual seats)
        from app.simulator.skill_pools import pool_for
        archetypes = pool_for(skill_style, skill_level)
        names = _name_pool()
        self.rng.shuffle(names)

        self.players: list[VirtualPlayer] = []
        for i in range(field_size - 1):       # all-but-hero are virtual
            arch = archetypes[i % len(archetypes)]
            self.players.append(VirtualPlayer(
                id=i + 1,
                name=names[i % len(names)],
                archetype=arch,
                skill=_ARCH_SKILL.get(arch, 0.5),
                stack=float(starting_stack),
            ))
        # Hero is tracked separately so a single source-of-truth stack
        self.hero_stack = float(starting_stack)
        self.hero_bust_hand: int = 0   # 0 = alive

    # ── public API ────────────────────────────────────────────────────

    @property
    def alive_players(self) -> list[VirtualPlayer]:
        return [p for p in self.players if p.alive]

    @property
    def players_left(self) -> int:
        # +1 if hero still alive
        return len(self.alive_players) + (1 if self.hero_bust_hand == 0 else 0)

    @property
    def chips_in_play(self) -> float:
        return sum(p.stack for p in self.alive_players) + (
            self.hero_stack if self.hero_bust_hand == 0 else 0
        )

    @property
    def avg_stack(self) -> float:
        n = self.players_left
        return self.chips_in_play / n if n else 0.0

    @property
    def chip_leader(self) -> tuple[str, float]:
        """(name, stack) of the largest stack still alive (or hero if biggest)."""
        contenders: list[tuple[str, float]] = [(p.name, p.stack) for p in self.alive_players]
        if self.hero_bust_hand == 0:
            contenders.append((self.hero_name, self.hero_stack))
        if not contenders:
            return ("—", 0.0)
        return max(contenders, key=lambda t: t[1])

    def hero_rank_now(self) -> int:
        """If hero busted now, what finish would they get?"""
        if self.hero_bust_hand:
            # Already busted — return the recorded finish
            return self._hero_finish or self.players_left + 1
        # Hero is alive: count how many players have MORE chips than hero
        ahead = sum(1 for p in self.alive_players if p.stack > self.hero_stack)
        return ahead + 1

    def update_hero_stack(self, new_stack: float) -> None:
        self.hero_stack = max(0.0, float(new_stack))
        if self.hero_stack < 1.0 and self.hero_bust_hand == 0:
            self.hero_bust_hand = self._hand_no
            self._hero_finish = self.players_left + 1   # +1 because hero is busting

    _hero_finish: Optional[int] = None

    def hero_busted_at(self, hand_no: int) -> None:
        """Mark hero as busted explicitly (e.g. via lost all-in)."""
        if self.hero_bust_hand == 0:
            self.hero_bust_hand = hand_no
            self._hero_finish = self.players_left
            self.hero_stack = 0.0

    @property
    def hero_finish(self) -> Optional[int]:
        return self._hero_finish

    @property
    def icm_zone(self) -> str:
        """Where we are in tournament life: 'early' / 'middle' / 'bubble' / 'itm' / 'final'."""
        n = self.players_left
        total = self.field_size
        paid = max(2, int(total * 0.15))
        if n <= 9:                    return "final"
        if n <= paid:                 return "itm"
        if n <= int(paid * 1.20):     return "bubble"
        if n <= int(total * 0.50):    return "middle"
        return "early"

    def advance_round(
        self,
        big_blind: float,
        hands_in_round: int = 10,
    ) -> list[VirtualPlayer]:
        """Roll the field forward by ~hands_in_round hands. Returns busted players.

        Models:
          • Skill drift (better players accumulate chips slowly).
          • Variance scaled by stack depth (short stacks gamble more).
          • Blind/ante bleed (deterministic decay).
          • ICM-zone bubble effect — near the money, short stacks bust slower
            (everyone tightens up) and avg stacks decay faster than expected
            (chip leaders pressure).
        """
        self._hand_no += hands_in_round
        # Pressure: as blinds grow vs starting stack, weaker stacks shed chips
        pressure = max(0.0, math.log(
            max(big_blind, 1) / max(self.starting_stack / 200, 1)
        ))
        zone = self.icm_zone
        # Bubble dynamics — short stacks survive longer near the money
        bubble_protect = 1.0
        if zone == "bubble":
            bubble_protect = 0.55   # 45% less variance for short stacks
        elif zone == "itm":
            bubble_protect = 0.8

        for p in self.alive_players:
            # Drift: skill above 0.5 grows stack; below 0.5 shrinks
            drift_per_hand = (p.skill - 0.5) * 0.012 - 0.001 * pressure
            # Variance — bigger for short stacks (they're forced to gamble)
            stack_ratio = p.stack / max(self.starting_stack, 1)
            sigma = max(0.05, 0.15 / math.sqrt(max(stack_ratio, 0.05)))
            # Short stacks tighten near bubble
            if stack_ratio < 0.5:
                sigma *= bubble_protect
            drift = drift_per_hand * hands_in_round
            noise = self.rng.gauss(0, sigma) * math.sqrt(hands_in_round)
            p.stack = p.stack * math.exp(drift + noise)

            # Bleed antes/blinds — flat cost per round
            ante_cost = big_blind * 0.5 * hands_in_round
            p.stack = max(0.0, p.stack - ante_cost)

        # Bust everyone with < 1 BB
        newly_busted: list[VirtualPlayer] = []
        for p in self.alive_players:
            if p.stack < big_blind:
                p.bust_hand = self._hand_no
                newly_busted.append(p)
        return newly_busted

    def crown_winner(self) -> Optional[VirtualPlayer]:
        """If only one virtual player + hero left, the higher stack 'wins' the rest.
        Returns the winner (None if hero is sole survivor)."""
        alive = self.alive_players
        if not alive and self.hero_bust_hand == 0:
            return None  # hero is the winner
        if len(alive) == 1 and self.hero_bust_hand == 0:
            return alive[0] if alive[0].stack > self.hero_stack else None
        return None

    def finish_for_hero(self) -> int:
        """How many players survived past hero. 1 = winner."""
        if self._hero_finish:
            return self._hero_finish
        # Hero still alive → live rank
        return self.hero_rank_now()
