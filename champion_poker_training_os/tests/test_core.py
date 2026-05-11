from __future__ import annotations

import math

from app.ai.safety_filters import is_live_strategy_request
from app.db.seed_data import bot_profiles, generate_math_drills, generate_spot_drills, leaks
from app.poker.alpha_mdf import alpha, mdf
from app.poker.combinations import combo_count
from app.poker.pot_odds import pot_odds
from app.poker.icm import (
    malmuth_harville,
    risk_premium,
    bounty_ev,
    bubble_factor,
    push_fold_range_width,
    chip_ev_vs_dollar_ev,
)
from app.poker.equity import estimate_preflop_equity, HAND_STRENGTH_HINTS
from app.solver.mock_solver import compare_action, solve_spot


def test_seed_data_counts_are_mvp_sized() -> None:
    # generate_spot_drills now returns the comprehensive 300+ catalog
    assert len(generate_spot_drills(120)) >= 120
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


# ===== NEW TESTS =====


def test_icm_malmuth_harville_basic() -> None:
    """Test ICM equity calculation with simple symmetric case."""
    stacks = [100.0, 100.0]
    payouts = [70.0, 30.0]
    equities = malmuth_harville(stacks, payouts)
    assert len(equities) == 2
    # Symmetric stacks should yield equal equity
    assert math.isclose(equities[0], equities[1], abs_tol=0.01)
    # Total equity should equal total payouts
    assert math.isclose(sum(equities), sum(payouts), abs_tol=0.01)


def test_icm_malmuth_harville_asymmetric() -> None:
    """Bigger stack should have more ICM equity."""
    stacks = [300.0, 100.0]
    payouts = [70.0, 30.0]
    equities = malmuth_harville(stacks, payouts)
    assert equities[0] > equities[1]


def test_icm_risk_premium_increases_on_bubble() -> None:
    rp_chip = risk_premium(25, 30, "chipEV")
    rp_bubble = risk_premium(25, 30, "bubble")
    rp_ft = risk_premium(25, 30, "final table")
    assert rp_bubble > rp_chip
    assert rp_ft > rp_bubble


def test_bounty_ev_calculation() -> None:
    ev = bounty_ev(bounty_chips=500, win_probability=0.6, call_cost=200)
    # 0.6 * 500 - 0.4 * 200 = 300 - 80 = 220
    assert math.isclose(ev, 220.0)


def test_push_fold_range_width() -> None:
    """Short stacks should have wider push ranges."""
    wide = push_fold_range_width(5)
    narrow = push_fold_range_width(30)
    assert wide > narrow

    # ICM should tighten range
    chip_width = push_fold_range_width(10, "chipEV")
    bubble_width = push_fold_range_width(10, "bubble")
    assert bubble_width < chip_width


def test_chip_ev_vs_dollar_ev() -> None:
    """Basic chipEV vs $EV comparison."""
    result = chip_ev_vs_dollar_ev(
        hero_stack=100, villain_stack=80,
        other_stacks=[60, 50], payouts=[50, 30, 15, 5],
        win_equity=0.55, call_amount=80,
    )
    assert "chip_ev" in result
    assert "dollar_ev_call" in result
    assert "dollar_ev_fold" in result
    assert result["decision"] in ("call", "fold")


def test_equity_lookup_table_coverage() -> None:
    """Ensure key hands have equity estimates."""
    for hand in ["AA", "KK", "QQ", "AKs", "AKo", "JTs", "72o"]:
        assert hand in HAND_STRENGTH_HINTS
        eq = estimate_preflop_equity(hand)
        assert 0.05 <= eq <= 0.95


def test_equity_multiway_penalty() -> None:
    """More players should reduce preflop equity."""
    eq2 = estimate_preflop_equity("AKs", players=2)
    eq6 = estimate_preflop_equity("AKs", players=6)
    assert eq2 > eq6


def test_spot_drills_have_required_fields() -> None:
    """Every drill must have the fields needed by trainers."""
    required = {"id", "title", "format", "table", "street", "position", "stack_bb",
                "pot_bb", "hero_cards", "board", "board_texture", "pot_type",
                "action_history", "options", "best_action", "icm", "source_confidence"}
    for drill in generate_spot_drills(20):
        missing = required - set(drill.keys())
        assert not missing, f"Drill {drill['id']} missing keys: {missing}"


def test_bot_profiles_have_required_stats() -> None:
    """Each bot must have the expected stat fields."""
    required = {"name", "vpip", "pfr", "three_bet", "fold_to_cbet", "aggression",
                "river_bluff", "call_down", "icm_risk_tolerance", "adjustment"}
    for bot in bot_profiles():
        missing = required - set(bot.keys())
        assert not missing, f"Bot {bot['name']} missing keys: {missing}"


def test_mock_solver_ev_loss_non_negative() -> None:
    """EV loss should never be negative."""
    for spot in generate_spot_drills(10):
        for action in spot["options"]:
            result = compare_action(spot, action)
            assert result["ev_loss"] >= 0, f"Negative EV loss for {spot['id']} {action}"


# ===== SKILL TREE TESTS =====


def test_skill_tree_xp_and_level_up() -> None:
    """Adding XP should eventually trigger a level-up."""
    from app.training.mastery_model import SkillTree
    tree = SkillTree()
    node = tree.nodes["preflop"]
    assert node.level == 1
    result = tree.grant_xp("preflop", 500)
    assert result["leveled_up"]
    assert node.level > 1


def test_skill_tree_achievement_unlock() -> None:
    """Achievements should unlock when conditions are met."""
    from app.training.mastery_model import SkillTree
    tree = SkillTree()
    stats = {"drills": 150, "streak": 8, "preflop_accuracy": 90}
    unlocked = tree.check_achievements(stats)
    ids = {a.id for a in unlocked}
    assert "drills_100" in ids
    assert "streak_7" in ids
    assert "preflop_85" in ids


def test_demo_skill_tree_consistency() -> None:
    """Demo skill tree should have valid state."""
    from app.training.mastery_model import demo_skill_tree
    tree = demo_skill_tree()
    summary = tree.get_summary()
    assert summary["overall_level"] >= 1
    assert len(summary["categories"]) == 12
    assert summary["achievements_total"] == 15
    assert summary["total_xp"] > 0
