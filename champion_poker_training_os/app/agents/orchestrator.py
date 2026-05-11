"""AgentOrchestrator — coordinates multiple agents for high-level workflows."""
from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentResult
from app.agents.coach import CoachAgent
from app.agents.drill_generator import DrillGeneratorAgent
from app.agents.leak_detector import LeakDetectionAgent
from app.agents.poker_player import PokerPlayingAgent
from app.agents.review import ReviewAgent


class AgentOrchestrator:
    """High-level coordinator that chains agents together."""

    def __init__(self):
        self.coach           = CoachAgent()
        self.review          = ReviewAgent()
        self.leak_detector   = LeakDetectionAgent()
        self.drill_generator = DrillGeneratorAgent()
        self.poker_player    = PokerPlayingAgent()

    # ── coaching workflow: spot → analysis → drill suggestions ──────────
    def coach_workflow(self, *, spot: dict, hero_action: str | None = None) -> dict[str, Any]:
        coach_res = self.coach.run(spot=spot, hero_action=hero_action)
        result    = {"coach": coach_res}
        if hero_action and not coach_res.data.get("compare", {}).get("is_correct", True):
            # Wrong → produce drill suggestions for this spot type
            fake_leak = [{
                "position": spot.get("position", "?"),
                "street":   spot.get("street", "?"),
                "pot_type": spot.get("pot_type", "SRP"),
            }]
            drill_res = self.drill_generator.run(leaks=fake_leak, pack_size=5)
            result["drills"] = drill_res
        return result

    # ── session review workflow ─────────────────────────────────────────
    def review_session(self, *, decisions: list[dict]) -> dict[str, Any]:
        review_res = self.review.run(decisions=decisions)
        # Build hand-style entries for leak detection
        hands = []
        for d in (review_res.data.get("reviewed") or []):
            hands.append({
                "position": d.get("position", "?"),
                "pot_type": "SRP",
                "street":   d.get("street", "?"),
                "ev_loss":  d.get("ev_loss", 0.0),
            })
        leak_res  = self.leak_detector.run(hands=hands)
        drill_res = self.drill_generator.run(leaks=leak_res.data.get("leaks", []), pack_size=10)
        return {"review": review_res, "leaks": leak_res, "drills": drill_res}

    # ── self-play workflow ──────────────────────────────────────────────
    def self_play(self, *, num_players: int = 6, hands: int = 10) -> dict[str, Any]:
        play_res = self.poker_player.run(num_players=num_players, hands=hands)
        return {"play": play_res}

    # ── unified run() interface ─────────────────────────────────────────
    def run(self, workflow: str = "coach", **kwargs) -> dict[str, Any]:
        if workflow == "coach":      return self.coach_workflow(**kwargs)
        if workflow == "review":     return self.review_session(**kwargs)
        if workflow == "self_play":  return self.self_play(**kwargs)
        raise ValueError(f"Unknown workflow: {workflow}")
