"""PokerPlayingAgent — autonomously plays poker hands using BotBrain.

Use cases:
  • Self-play simulation (generate hand histories)
  • Headless bot-vs-bot benchmarks
  • Generate analysis data without UI

Public API:
  • play_hand(num_players, archetypes, stack) → result dict with hand history
  • play_session(hands=10, ...)                 → list of hand results
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from app.agents.base import Agent, AgentResult
from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType


class PokerPlayingAgent(Agent):
    """Plays poker hands programmatically."""

    name = "PokerPlayingAgent"

    def __init__(self, archetype: str = "Balanced Reg"):
        # Resolve archetype safely — fall back to first available if missing
        if archetype not in BOT_ARCHETYPES:
            archetype = next(iter(BOT_ARCHETYPES))
        self.archetype = archetype
        self._profile  = BOT_ARCHETYPES[archetype]
        self.brain     = BotBrain(self._profile)

    # ── core: play one hand ───────────────────────────────────────────────
    def play_hand(
        self,
        num_players: int = 6,
        bot_archetypes: Optional[dict[int, str]] = None,
        stack_bb: float = 100.0,
        sb: float = 0.5,
        bb: float = 1.0,
    ) -> dict[str, Any]:
        """Play a single hand bot-vs-bot. Returns a dict describing the result."""
        seats = max(2, min(num_players, 11))
        game = PokerGame(
            num_players=seats,
            starting_stack=stack_bb,
            small_blind=sb,
            big_blind=bb,
            hero_seat=0,
            bot_archetype=self.archetype,
            bot_archetypes=bot_archetypes or {},
        )
        # Hero acts as a bot too (we use the same BotBrain)
        hand = game.start_hand()
        max_iters = 200
        iters = 0
        while game.is_waiting_for_hero and not hand.is_complete and iters < max_iters:
            action = self._choose_action(hand)
            hand = game.hero_act(action[0], action[1])
            iters += 1

        return {
            "hand_id":    hand.hand_id,
            "winners":    list(hand.winners),
            "winner_hand":hand.winner_hand_name,
            "pot":        hand.pot,
            "street":     hand.street.name,
            "complete":   hand.is_complete,
            "board":      hand.community_display,
            "actions":    [self._action_summary(a) for a in hand.actions],
            "players":    [self._player_summary(p) for p in hand.players],
        }

    def play_session(self, hands: int = 10, **kwargs) -> list[dict[str, Any]]:
        results = []
        for _ in range(hands):
            try:
                results.append(self.play_hand(**kwargs))
            except Exception as e:
                results.append({"error": str(e)})
        return results

    # ── Agent protocol ────────────────────────────────────────────────────
    def run(self, **kwargs) -> AgentResult:
        hands  = kwargs.pop("hands", 1)
        if hands <= 1:
            data = self.play_hand(**kwargs)
            return AgentResult(
                agent   = self.name,
                success = data.get("complete", False),
                summary = f"Played 1 hand · pot {data.get('pot', 0):.1f}bb · winners={data.get('winners')}",
                data    = data,
                actions = data.get("actions", []),
            )
        results = self.play_session(hands=hands, **kwargs)
        won = sum(1 for r in results if 0 in (r.get("winners") or []))
        return AgentResult(
            agent   = self.name,
            success = len(results) == hands,
            summary = f"Played {len(results)} hands · hero won {won}",
            data    = {"hands": results, "win_count": won},
        )

    # ── helpers ──────────────────────────────────────────────────────────
    def _choose_action(self, hand) -> tuple[ActionType, float]:
        """Use BotBrain to decide the next action for the seat-to-act."""
        idx = hand.hero_idx
        decision = self.brain.decide(hand, idx)
        # decision returns (ActionType, amount) — handle either tuple or single value
        if isinstance(decision, tuple):
            return decision
        return (decision, 0.0)

    @staticmethod
    def _action_summary(a) -> str:
        try:
            who = f"P{a.player_idx}"
            amt = f" {a.amount:.1f}" if getattr(a, "amount", 0) else ""
            return f"{who} {a.action_type.value}{amt}"
        except Exception:
            return str(a)

    @staticmethod
    def _player_summary(p) -> dict:
        return {
            "name":     p.name,
            "position": p.position,
            "stack":    round(p.stack, 2),
            "folded":   p.is_folded,
            "all_in":   p.is_all_in,
            "is_hero":  p.is_hero,
        }
