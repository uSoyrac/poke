"""Multi-agent training system.

Each agent focuses on a single responsibility:
  • PokerPlayingAgent  — Plays a poker hand using a bot archetype (self-play)
  • CoachAgent         — Produces structured advice + math breakdown
  • LeakDetectionAgent — Scans played history for systemic mistakes
  • DrillGeneratorAgent — Builds personalised drill packs from weaknesses
  • ReviewAgent        — Reviews a finished hand and tags decisions
  • AgentOrchestrator  — Coordinates the above for higher-level workflows

Agents communicate via plain dicts so they can be composed and tested
independently. No GUI or Qt dependency in this module.
"""
from app.agents.base import Agent, AgentResult
from app.agents.coach import CoachAgent
from app.agents.drill_generator import DrillGeneratorAgent
from app.agents.leak_detector import LeakDetectionAgent
from app.agents.orchestrator import AgentOrchestrator
from app.agents.poker_player import PokerPlayingAgent
from app.agents.review import ReviewAgent

__all__ = [
    "Agent",
    "AgentResult",
    "PokerPlayingAgent",
    "CoachAgent",
    "LeakDetectionAgent",
    "DrillGeneratorAgent",
    "ReviewAgent",
    "AgentOrchestrator",
]
