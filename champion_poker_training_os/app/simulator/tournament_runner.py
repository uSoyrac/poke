"""Full playable tournament runner.

Wraps PokerGame with:
- Blind level schedule (chips, not BB)
- Antes after level 5
- Hand persistence to DB
- Hero leak analysis on session end
- ICM-aware bot mix (more nits late, more LAGs early)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.engine.game_loop import PokerGame, HandResult
from app.engine.hand_state import ActionType, Street


@dataclass
class BlindLevel:
    level: int
    sb: int
    bb: int
    ante: int = 0
    duration_min: int = 10  # purely informational


def regular_structure(starting_bb: int = 100) -> List[BlindLevel]:
    """Standard MTT — slow rise."""
    return [
        BlindLevel(1, 10, 20, 0, 12),
        BlindLevel(2, 15, 30, 0, 12),
        BlindLevel(3, 25, 50, 0, 12),
        BlindLevel(4, 50, 100, 0, 12),
        BlindLevel(5, 75, 150, 0, 12),
        BlindLevel(6, 100, 200, 25, 12),
        BlindLevel(7, 150, 300, 35, 12),
        BlindLevel(8, 200, 400, 50, 12),
        BlindLevel(9, 300, 600, 75, 10),
        BlindLevel(10, 400, 800, 100, 10),
        BlindLevel(11, 500, 1000, 125, 10),
        BlindLevel(12, 750, 1500, 175, 10),
        BlindLevel(13, 1000, 2000, 250, 10),
        BlindLevel(14, 1500, 3000, 350, 10),
        BlindLevel(15, 2000, 4000, 500, 8),
        BlindLevel(16, 3000, 6000, 750, 8),
        BlindLevel(17, 4000, 8000, 1000, 8),
        BlindLevel(18, 5000, 10000, 1250, 8),
        BlindLevel(19, 7500, 15000, 1750, 8),
        BlindLevel(20, 10000, 20000, 2500, 8),
    ]


def turbo_structure() -> List[BlindLevel]:
    """Turbo — faster blind levels, hands per level lower."""
    return [
        BlindLevel(1, 10, 20, 0, 5),
        BlindLevel(2, 25, 50, 0, 5),
        BlindLevel(3, 50, 100, 0, 5),
        BlindLevel(4, 100, 200, 25, 5),
        BlindLevel(5, 150, 300, 50, 5),
        BlindLevel(6, 250, 500, 75, 5),
        BlindLevel(7, 400, 800, 100, 5),
        BlindLevel(8, 600, 1200, 150, 5),
        BlindLevel(9, 1000, 2000, 250, 5),
        BlindLevel(10, 1500, 3000, 400, 5),
        BlindLevel(11, 2500, 5000, 650, 5),
        BlindLevel(12, 4000, 8000, 1000, 5),
        BlindLevel(13, 6000, 12000, 1500, 4),
        BlindLevel(14, 10000, 20000, 2500, 4),
    ]


def hyper_structure() -> List[BlindLevel]:
    return [
        BlindLevel(1, 25, 50, 0, 3),
        BlindLevel(2, 75, 150, 25, 3),
        BlindLevel(3, 150, 300, 50, 3),
        BlindLevel(4, 300, 600, 75, 3),
        BlindLevel(5, 600, 1200, 150, 3),
        BlindLevel(6, 1200, 2400, 300, 3),
        BlindLevel(7, 2500, 5000, 600, 3),
        BlindLevel(8, 5000, 10000, 1200, 3),
    ]


# Default payout structures (% of prize pool)
# 9-max → top 3 paid  (realistic MTT payout)
# 6-max → top 2 paid  (typical SNG / 6-handed)
PAYOUT_STRUCTURES = {
    "9-max": [
        (1, 0.50), (2, 0.30), (3, 0.20),
    ],
    "6-max": [
        (1, 0.65), (2, 0.35),
    ],
    "Heads-Up": [(1, 1.0)],
}


@dataclass
class TournamentConfig:
    name: str = "$22 Bounty Hunter"
    field_size: int = 9
    starting_chips: int = 2000
    structure: str = "regular"  # regular | turbo | hyper
    buyin: float = 22.0
    payout_key: str = "9-max"
    hands_per_level: int = 12  # How many hands before blinds go up
    bot_mix: List[str] = field(default_factory=lambda: [
        "TAG", "Reg", "Fish", "LAG", "Nit", "Aggro Fish", "Tight Passive", "Calling Station"
    ])
    hero_range_filter: str = ""   # "" = all hands; "Premium" / "TAG Range" / etc.

    @property
    def total_chips(self) -> int:
        return self.starting_chips * self.field_size

    @property
    def prize_pool(self) -> float:
        return self.buyin * self.field_size

    @property
    def paid_places(self) -> int:
        return len(PAYOUT_STRUCTURES.get(self.payout_key, []))


@dataclass
class TournamentState:
    config: TournamentConfig
    level_idx: int = 0
    hands_this_level: int = 0
    hands_total: int = 0
    players_left: int = 0
    is_complete: bool = False
    finish_position: Optional[int] = None
    prize_won: float = 0.0
    levels: List[BlindLevel] = field(default_factory=list)
    eliminated_order: List[int] = field(default_factory=list)  # Player indices in order they busted

    @property
    def current_level(self) -> BlindLevel:
        if not self.levels:
            return BlindLevel(1, 10, 20)
        return self.levels[min(self.level_idx, len(self.levels) - 1)]

    @property
    def hands_until_next_level(self) -> int:
        return max(0, self.config.hands_per_level - self.hands_this_level)


class Tournament:
    """Single-table tournament runner. Hero + bots play until 1 left or hero busts."""

    def __init__(self, config: TournamentConfig):
        self.config = config
        if config.structure == "turbo":
            levels = turbo_structure()
        elif config.structure == "hyper":
            levels = hyper_structure()
        else:
            levels = regular_structure()

        self.state = TournamentState(
            config=config,
            levels=levels,
            players_left=config.field_size,
        )

        # Build the game
        level = self.state.current_level
        # Distribute archetypes
        bot_archs = (config.bot_mix * ((config.field_size // len(config.bot_mix)) + 1))[:config.field_size - 1]
        bot_names = [f"villain_{i}" for i in range(1, config.field_size)]
        self.game = PokerGame(
            num_players=config.field_size,
            starting_stack=float(config.starting_chips),
            small_blind=float(level.sb),
            big_blind=float(level.bb),
            ante=float(level.ante),
            hero_seat=0,
            bot_archetypes=bot_archs,
            player_names=bot_names,
            hero_range_filter=config.hero_range_filter,
        )
        self.hand_log: List[HandResult] = []

    # ── PUBLIC API ─────────────────────────────────────────────────

    @property
    def is_complete(self) -> bool:
        return self.state.is_complete

    @property
    def hero_chips(self) -> float:
        return self.game.players[self.game.hero_seat].stack

    @property
    def hero_busted(self) -> bool:
        hero = self.game.players[self.game.hero_seat]
        return hero.is_eliminated or hero.stack <= 0

    @property
    def players_remaining(self) -> int:
        return sum(1 for p in self.game.players if not p.is_eliminated)

    def start_hand(self):
        if self.state.is_complete:
            return None
        # Bump blind level if needed
        if self.state.hands_this_level >= self.config.hands_per_level:
            self.state.level_idx = min(self.state.level_idx + 1, len(self.state.levels) - 1)
            self.state.hands_this_level = 0
            lvl = self.state.current_level
            self.game.set_blinds(float(lvl.sb), float(lvl.bb), float(lvl.ante))

        # Track who is in
        pre_alive = {i for i, p in enumerate(self.game.players) if not p.is_eliminated}
        hand = self.game.start_hand()
        return hand

    def hero_act(self, action_type: ActionType, amount: float = 0.0):
        if self.state.is_complete:
            return None
        hand = self.game.hero_act(action_type, amount)
        self._post_hand_maybe()
        return hand

    def advance_after_hand_complete(self):
        """Call once a hand finishes to record stats & advance the tournament state."""
        self._post_hand_maybe()

    def _post_hand_maybe(self):
        if not self.game.current_hand or not self.game.current_hand.is_complete:
            return
        # Already recorded this hand?
        if self.game.hand_history and (not self.hand_log or self.hand_log[-1].hand_id != self.game.hand_history[-1].hand_id):
            result = self.game.hand_history[-1]
            self.hand_log.append(result)
            self.state.hands_total += 1
            self.state.hands_this_level += 1

            # Detect new eliminations
            for i, p in enumerate(self.game.players):
                if p.stack <= 0 and not p.is_eliminated:
                    p.is_eliminated = True
                if p.is_eliminated and i not in self.state.eliminated_order:
                    self.state.eliminated_order.append(i)

            self.state.players_left = self.players_remaining

            # Hero busted?
            if self.hero_busted:
                # Hero's finishing position = current players_remaining + 1
                finish = self.state.players_left + 1 if self.state.players_left < self.config.field_size else self.config.field_size
                # Actually finish = number of players still in when hero busted + 1
                finish = self.state.players_left + 1
                self.state.finish_position = finish
                self.state.prize_won = self._prize_for(finish)
                self.state.is_complete = True
                return

            # Single survivor → tournament over (hero won)
            if self.state.players_left <= 1:
                self.state.finish_position = 1
                self.state.prize_won = self._prize_for(1)
                self.state.is_complete = True

    def _prize_for(self, position: int) -> float:
        payouts = PAYOUT_STRUCTURES.get(self.config.payout_key, [])
        for pos, pct in payouts:
            if pos == position:
                return round(self.config.prize_pool * pct, 2)
        return 0.0

    # ── ANALYSIS ───────────────────────────────────────────────────

    def leak_report(self) -> dict:
        """Compute hero leaks from the hand log."""
        if not self.hand_log:
            return {
                "summary": "No hands played yet.",
                "stats": {},
                "leaks": [],
            }

        stats = self.game.get_session_stats()
        hero_idx = self.game.hero_seat
        total = len(self.hand_log)

        # Position breakdown
        position_stats: Dict[str, dict] = {}
        for h in self.hand_log:
            pos = h.hero_position or "?"
            ps = position_stats.setdefault(pos, {"hands": 0, "profit": 0.0, "vpip": 0, "pfr": 0})
            ps["hands"] += 1
            ps["profit"] += h.hero_profit
            voluntarily_in = any(
                a.player_idx == hero_idx and a.street == Street.PREFLOP
                and a.action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
            raised_pf = any(
                a.player_idx == hero_idx and a.street == Street.PREFLOP
                and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
            if voluntarily_in:
                ps["vpip"] += 1
            if raised_pf:
                ps["pfr"] += 1

        # Compute % stats per position
        for pos, ps in position_stats.items():
            n = max(ps["hands"], 1)
            ps["vpip_pct"] = round(100 * ps["vpip"] / n, 1)
            ps["pfr_pct"] = round(100 * ps["pfr"] / n, 1)
            ps["bb_per_100"] = round(100 * ps["profit"] / (n * self.game.big_blind), 1) if self.game.big_blind else 0

        # Leaks
        leaks: List[dict] = []
        vpip = stats.get("vpip", 0)
        pfr = stats.get("pfr", 0)
        wtsd = stats.get("wtsd", 0)

        if vpip > 38:
            leaks.append({
                "name": "Too loose preflop",
                "severity": "HIGH",
                "detail": f"VPIP {vpip}% — target 20-28% in tournaments. You're playing trash hands voluntarily.",
                "fix": "Use the position-aware open ranges (UTG: top 14%, BTN: top 40%).",
                "ev_loss": round((vpip - 28) * 0.15, 2),
            })
        elif vpip < 14 and total > 15:
            leaks.append({
                "name": "Too tight preflop",
                "severity": "MEDIUM",
                "detail": f"VPIP {vpip}% — you're missing steal spots from BTN/CO and blind defense.",
                "fix": "Widen ranges in late position and defend BB vs late position opens.",
                "ev_loss": round((22 - vpip) * 0.10, 2),
            })

        gap = vpip - pfr
        if gap > 10 and total > 15:
            leaks.append({
                "name": "Passive preflop (calling station)",
                "severity": "HIGH",
                "detail": f"VPIP-PFR gap = {gap:.1f}% — too many limps/calls, too few raises.",
                "fix": "Open-raise (don't limp) when first in. 3-bet polarized vs late-position opens.",
                "ev_loss": round(gap * 0.12, 2),
            })

        if wtsd > 35 and total > 10:
            leaks.append({
                "name": "Going to showdown too often",
                "severity": "MEDIUM",
                "detail": f"WTSD {wtsd}% — calling too thin on turn/river.",
                "fix": "Use MDF + blocker logic. Fold marginal bluff-catchers vs polarized lines.",
                "ev_loss": round((wtsd - 28) * 0.15, 2),
            })

        # Position-specific
        for pos in ("UTG", "UTG+1"):
            ps = position_stats.get(pos)
            if ps and ps["hands"] >= 3 and ps["vpip_pct"] > 30:
                leaks.append({
                    "name": f"Too loose from {pos}",
                    "severity": "MEDIUM",
                    "detail": f"{pos} VPIP {ps['vpip_pct']}% over {ps['hands']} hands.",
                    "fix": f"From {pos} only play top ~14% (TT+, AQ+, KQs, suited connectors selectively).",
                    "ev_loss": round((ps['vpip_pct'] - 14) * 0.1, 2),
                })

        # Big losing positions
        for pos, ps in position_stats.items():
            if ps["hands"] >= 5 and ps["bb_per_100"] < -50:
                leaks.append({
                    "name": f"Losing badly from {pos}",
                    "severity": "HIGH",
                    "detail": f"{pos}: {ps['bb_per_100']}bb/100 over {ps['hands']} hands.",
                    "fix": f"Review {pos} ranges and post-flop play from this position.",
                    "ev_loss": abs(ps['bb_per_100']) / 100,
                })

        if not leaks:
            leaks.append({
                "name": "No major leaks detected",
                "severity": "INFO",
                "detail": f"Stats look healthy over {total} hands.",
                "fix": "Keep training. Push the edge into wider profitable spots.",
                "ev_loss": 0,
            })

        # Sort by severity then ev_loss
        sev_order = {"HIGH": 0, "MEDIUM": 1, "INFO": 2}
        leaks.sort(key=lambda l: (sev_order.get(l["severity"], 99), -l.get("ev_loss", 0)))

        return {
            "summary": (
                f"Hero played {total} hands · Finish: "
                f"{self.state.finish_position or 'live'} of {self.config.field_size} · "
                f"Prize: ${self.state.prize_won:.0f} / ${self.config.prize_pool:.0f}"
            ),
            "stats": stats,
            "position_stats": position_stats,
            "leaks": leaks,
            "biggest_pot": stats.get("biggest_pot", 0),
            "structure": self.config.structure,
        }
