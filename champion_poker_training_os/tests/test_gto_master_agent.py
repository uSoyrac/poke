"""GTOMasterAgent — pro-coach analysis tests."""
from __future__ import annotations

import pytest

from app.agents import GTOMasterAgent, MasterAnalysis


@pytest.fixture
def btn_open_spot() -> dict:
    return {
        "id":           "T-BTN-RFI-40-AKs",
        "name":         "40bb BTN RFI · AKs",
        "position":     "BTN",
        "stack_bb":     40,
        "street":       "preflop",
        "hero_cards":   "AsKs",
        "options":      ("fold", "call", "raise", "jam"),
        "pot_bb":       1.5,
        "pot_type":     "SRP",
        "base_ev":      1.0,
    }


@pytest.fixture
def bb_defense_spot() -> dict:
    return {
        "id":           "T-BB-DEF-40-vsBTN-72o",
        "name":         "40bb BB vs BTN RFI · 72o",
        "position":     "BB",
        "stack_bb":     40,
        "street":       "preflop",
        "hero_cards":   "7s2d",
        "options":      ("fold", "call", "raise", "jam"),
        "pot_bb":       2.5,
        "pot_type":     "SRP",
        "base_ev":      0.8,
    }


def test_master_returns_structured_analysis(btn_open_spot):
    result = GTOMasterAgent().run(spot=btn_open_spot)
    assert result.success
    analysis = result.data["analysis"]
    assert isinstance(analysis, MasterAnalysis)
    # Every section present
    assert analysis.headline
    assert analysis.range_adv
    assert analysis.nut_adv
    assert analysis.blocker
    assert analysis.texture
    assert analysis.position
    assert analysis.recommended
    assert analysis.leak_warning
    assert analysis.drill


def test_master_includes_math_block(btn_open_spot):
    result = GTOMasterAgent().run(spot=btn_open_spot)
    math = result.data["math"]
    assert "required_equity" in math
    assert "alpha" in math
    assert "mdf" in math
    assert 0 < math["required_equity"] < 1


def test_master_compares_to_hero_action_correct(btn_open_spot):
    result = GTOMasterAgent().run(spot=btn_open_spot, hero_action="raise")
    # AKs from BTN open should be raise → correct
    assert "✅" in result.data["analysis"].recommended or "doğru" in result.data["analysis"].recommended.lower()


def test_master_compares_to_hero_action_wrong(bb_defense_spot):
    # 72o from BB → fold (correct), so call should be flagged wrong
    result = GTOMasterAgent().run(spot=bb_defense_spot, hero_action="call")
    text = result.data["analysis"].recommended
    assert "❌" in text or "Hatalı" in text or "EV kayıp" in text


def test_master_handles_empty_spot():
    result = GTOMasterAgent().run(spot={})
    # Either fails cleanly or returns generic advice — must not crash
    assert isinstance(result.success, bool)


def test_master_markdown_export(btn_open_spot):
    result = GTOMasterAgent().run(spot=btn_open_spot, hero_action="fold")
    md = result.data["markdown"]
    # Must contain key section headers
    for needle in ("Recommended", "Range advantage", "Common leak", "Drill"):
        assert needle in md


def test_master_position_specific_advice(btn_open_spot, bb_defense_spot):
    btn_advice = GTOMasterAgent().run(spot=btn_open_spot).data["analysis"].position
    bb_advice  = GTOMasterAgent().run(spot=bb_defense_spot).data["analysis"].position
    # BTN vs BB should produce different position notes
    assert btn_advice != bb_advice


def test_master_hand_specific_strategy_preflop(btn_open_spot):
    result = GTOMasterAgent().run(spot=btn_open_spot)
    strat = result.data["strategy"]
    # AKs from BTN → raise 100%
    assert strat.get("raise", 0) >= 0.9 or any("raise" in k for k in strat)
