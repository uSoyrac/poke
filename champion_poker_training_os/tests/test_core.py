from __future__ import annotations

import math

from app.ai.safety_filters import is_live_strategy_request
from app.db.seed_data import bot_profiles, generate_math_drills, generate_spot_drills, leaks
from app.poker.alpha_mdf import alpha, mdf
from app.poker.combinations import combo_count
from app.poker.pot_odds import pot_odds
from app.solver.mock_solver import compare_action, solve_spot


def test_seed_data_counts_are_mvp_sized() -> None:
    assert len(generate_spot_drills(120)) == 120
    assert len(generate_math_drills(30)) == 30
    assert len(bot_profiles()) >= 8
    assert len(leaks()) >= 5


def test_poker_math_formulas() -> None:
    assert math.isclose(pot_odds(5, 10), 0.25)
    assert math.isclose(alpha(5, 10), 1 / 3)
    assert math.isclose(mdf(5, 10), 2 / 3)
    assert combo_count("AA") == 6
    assert combo_count("AKs") == 4
    assert combo_count("AKo") == 12


def test_mock_solver_returns_feedback() -> None:
    spot = generate_spot_drills(1)[0]
    solution = solve_spot(spot)
    assert solution.best_action in spot["options"]
    feedback = compare_action(spot, spot["options"][0])
    assert "ev_loss" in feedback
    assert feedback["solver"]["source_confidence"]


def test_rta_live_prompt_filter() -> None:
    assert is_live_strategy_request("Şu an elimde AK var ne yapayım?")
    assert not is_live_strategy_request("Geçmiş elde AK ile yaptığım call iyi miydi?")

