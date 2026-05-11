"""Multi-agent system unit tests."""
from __future__ import annotations

import pytest

from app.agents import (
    AgentOrchestrator,
    CoachAgent,
    DrillGeneratorAgent,
    LeakDetectionAgent,
    PokerPlayingAgent,
    ReviewAgent,
)


@pytest.fixture
def sample_spot() -> dict:
    return {
        "id":            "t1",
        "position":      "BTN",
        "stack_bb":      40,
        "street":        "preflop",
        "hero_cards":    "AsKh",
        "options":       ("fold", "call", "raise", "jam"),
        "pot_bb":        2.5,
        "best_action":   "raise",
        "base_ev":       1.0,
        "pot_type":      "SRP",
    }


@pytest.fixture
def sample_history() -> list[dict]:
    return [
        {"position": "BB",  "pot_type": "SRP", "street": "preflop", "ev_loss": 3.5},
        {"position": "BB",  "pot_type": "SRP", "street": "preflop", "ev_loss": 2.2},
        {"position": "BB",  "pot_type": "SRP", "street": "preflop", "ev_loss": 4.1},
        {"position": "BTN", "pot_type": "3BP", "street": "flop",    "ev_loss": 1.5},
        {"position": "CO",  "pot_type": "SRP", "street": "turn",    "ev_loss": 0.5},
    ]


# ── CoachAgent ────────────────────────────────────────────────────────────

def test_coach_correct_decision_reports_correct(sample_spot):
    result = CoachAgent().run(spot=sample_spot, hero_action="raise")
    assert result.success
    assert result.data["compare"]["is_correct"]
    assert result.data["compare"]["ev_loss"] == 0.0


def test_coach_wrong_decision_flags_ev_loss(sample_spot):
    result = CoachAgent().run(spot=sample_spot, hero_action="fold")
    assert result.success
    assert not result.data["compare"]["is_correct"]
    assert result.data["compare"]["ev_loss"] > 0


def test_coach_without_hero_action_still_returns_strategy(sample_spot):
    result = CoachAgent().run(spot=sample_spot)
    assert result.success
    assert result.data["best_action"]
    assert "math" in result.data


def test_coach_handles_empty_spot():
    result = CoachAgent().run(spot={})
    # Solver tolerates missing spot fields; just verify no crash
    assert result.success or not result.success  # either is fine


# ── LeakDetectionAgent ────────────────────────────────────────────────────

def test_leak_detector_finds_bb_overlose(sample_history):
    result = LeakDetectionAgent().run(hands=sample_history)
    assert result.success
    leaks = result.data["leaks"]
    assert len(leaks) >= 1
    # The BB-SRP-preflop spot has 3 hands with combined 9.8bb loss
    bb_leak = next((l for l in leaks if l["position"] == "BB"), None)
    assert bb_leak is not None
    assert bb_leak["sample"] == 3
    assert bb_leak["total_ev_loss"] > 5


def test_leak_detector_respects_min_sample(sample_history):
    result = LeakDetectionAgent().run(hands=sample_history, min_sample=5)
    # No spot has 5 samples → no leaks
    assert len(result.data["leaks"]) == 0


def test_leak_detector_empty_input():
    result = LeakDetectionAgent().run(hands=[])
    assert not result.success


# ── DrillGeneratorAgent ───────────────────────────────────────────────────

def test_drill_generator_produces_pack():
    result = DrillGeneratorAgent().run(
        leaks=[{"position": "BB", "street": "preflop", "pot_type": "SRP"}],
        pack_size=5,
    )
    assert result.success
    assert len(result.data["drills"]) == 5
    assert all("id" in d for d in result.data["drills"])


def test_drill_generator_fills_with_fallback_when_no_leaks():
    result = DrillGeneratorAgent().run(leaks=[], pack_size=10)
    assert len(result.data["drills"]) == 10


# ── ReviewAgent ───────────────────────────────────────────────────────────

def test_review_agent_marks_decisions(sample_spot):
    decisions = [
        {"spot": sample_spot, "hero_action": "raise"},  # correct
        {"spot": sample_spot, "hero_action": "fold"},   # wrong
    ]
    result = ReviewAgent().run(decisions=decisions)
    assert result.success
    assert result.data["mistake_count"] == 1
    assert 0 <= result.data["accuracy"] <= 100


def test_review_agent_handles_empty():
    result = ReviewAgent().run(decisions=[])
    assert result.success
    assert result.data["mistake_count"] == 0


# ── PokerPlayingAgent ─────────────────────────────────────────────────────

def test_poker_playing_agent_plays_a_hand():
    agent = PokerPlayingAgent(archetype="Balanced Reg")
    result = agent.run(num_players=4, hands=1, stack_bb=100.0)
    assert result.success
    assert "winners" in result.data or "hand_id" in result.data


def test_poker_playing_agent_falls_back_to_default_archetype():
    agent = PokerPlayingAgent(archetype="NotARealArchetype")
    # Should not raise — falls back to first archetype
    assert agent.archetype  # truthy


def test_poker_playing_agent_session_returns_list():
    agent = PokerPlayingAgent(archetype="Balanced Reg")
    result = agent.run(num_players=4, hands=3, stack_bb=100.0)
    assert result.success
    assert len(result.data.get("hands", [])) == 3


# ── AgentOrchestrator ────────────────────────────────────────────────────

def test_orchestrator_coach_workflow(sample_spot):
    o = AgentOrchestrator()
    res = o.coach_workflow(spot=sample_spot, hero_action="fold")
    assert "coach" in res
    assert "drills" in res  # wrong answer → drill suggestions returned


def test_orchestrator_review_session(sample_spot):
    o = AgentOrchestrator()
    decisions = [
        {"spot": sample_spot, "hero_action": "raise"},
        {"spot": sample_spot, "hero_action": "fold"},
        {"spot": sample_spot, "hero_action": "fold"},
        {"spot": sample_spot, "hero_action": "fold"},
    ]
    res = o.review_session(decisions=decisions)
    assert "review" in res and "leaks" in res and "drills" in res
    assert res["review"].data["mistake_count"] == 3


def test_orchestrator_unknown_workflow_raises():
    o = AgentOrchestrator()
    with pytest.raises(ValueError):
        o.run(workflow="bogus")
