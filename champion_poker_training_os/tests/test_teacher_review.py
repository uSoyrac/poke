"""Tests for the teacher_review() coach output.

The teacher review is what the user sees after every wrong (or right)
decision in the trainer. It must contain:

  • Per-option breakdown with frequency % for every available action
  • A thinking-framework block (pot, stack, position, range, ICM)
  • A "why GTO X" justification
  • BB-based math (no pure pot-% sizings without BB equivalents)
  • ICM context when the spot is flagged ICM
  • The breakdown row for the GTO best action highlighted
"""
from __future__ import annotations

import pytest

from app.ai.coach_engine import teacher_review, explain_spot
from app.solver.mock_solver import _sizing_label


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def cash_spot() -> dict:
    return {
        "id": "btn_open_aks_25bb",
        "position": "BTN",
        "stack_bb": 25,
        "pot_bb": 1.5,
        "pot_type": "SRP",
        "street": "preflop",
        "hero_cards": "AhKs",
        "board": "",
        "options": ["fold", "call", "raise"],
    }


@pytest.fixture
def icm_spot() -> dict:
    return {
        "id": "ft_bubble_aq_12bb",
        "position": "BB",
        "stack_bb": 12,
        "pot_bb": 3.0,
        "pot_type": "SRP",
        "street": "preflop",
        "hero_cards": "AhQc",
        "is_icm": True,
        "payouts": [25000, 18000, 12000],
        "options": ["fold", "call", "jam"],
    }


# ── Structural assertions ───────────────────────────────────────────────


def test_teacher_review_contains_all_required_sections(cash_spot):
    out = teacher_review(cash_spot, "call")
    # Every section header must be present
    for header in (
        "VERDIKT",
        "KARAR DAĞILIMI",
        "BU SPOTTA NE DÜŞÜNMELİYDİN",
        "NEDEN GTO",
        "MATEMATİK",
        "RANGE & BLOCKER",
        "AKILDA KALSIN",
        "SONRAKI ADIM",
    ):
        assert header in out, f"Missing section: {header}\n---\n{out}"


def test_breakdown_contains_frequency_for_every_option(cash_spot):
    """Every option in the spot must appear in the karar-dağılımı table."""
    out = teacher_review(cash_spot, "call")
    for opt in ("FOLD", "CALL", "RAISE"):
        assert opt in out, f"Option {opt} missing from breakdown:\n{out}"
    # At least 3 percentage values shown (one per option)
    pct_count = out.count("%")
    assert pct_count >= 3


def test_breakdown_marks_gto_best_action(cash_spot):
    out = teacher_review(cash_spot, "call")
    # The GTO marker line should exist somewhere
    assert "GTO" in out
    # The "▶" or "← GTO" tag should appear on the best-action row
    assert "← GTO" in out or "✓ GTO + sen" in out or "▶" in out


def test_breakdown_marks_hero_action(cash_spot):
    out = teacher_review(cash_spot, "call")
    assert "← sen" in out or "✓ GTO + sen" in out


# ── BB-based math ───────────────────────────────────────────────────────


def test_math_block_uses_bb_units(cash_spot):
    out = teacher_review(cash_spot, "call")
    # "bb" must appear in the math block (pot odds, sizing, etc.)
    assert "bb" in out
    # SPR is BB-derived ratio — must be present
    assert "SPR" in out


def test_sizing_label_leads_with_bb():
    """_sizing_label must put BB units first, pot% in parentheses."""
    spot = {"pot_bb": 6.0, "stack_bb": 30, "big_blind": 1.0, "street": "turn"}
    for action in ("bet small", "bet medium", "bet large"):
        label = _sizing_label(action, spot)
        # BB must come before "(...% pot)"
        bb_idx = label.find("bb")
        pct_idx = label.find("% pot")
        assert bb_idx >= 0, f"Missing BB unit in '{label}'"
        if pct_idx > -1:
            assert bb_idx < pct_idx, (
                f"Pot% must come AFTER BB units in '{label}'"
            )


def test_preflop_open_sizing_is_bb_native():
    spot = {"pot_bb": 1.5, "stack_bb": 25, "street": "preflop"}
    assert "bb" in _sizing_label("raise", spot)
    # Jam label is BB-native (all-in stack)
    assert "bb" in _sizing_label("jam", spot)


# ── ICM context ─────────────────────────────────────────────────────────


def test_icm_spot_mentions_icm_pressure(icm_spot):
    out = teacher_review(icm_spot, "call")
    assert "ICM" in out
    # The header line should show the ICM badge
    assert "🏆" in out or "ICM" in out
    # Risk premium / ladder logic must be discussed
    assert ("risk premium" in out.lower()
            or "merdiven" in out.lower()
            or "ladder" in out.lower())


def test_cash_spot_does_not_falsely_invoke_icm(cash_spot):
    out = teacher_review(cash_spot, "call")
    # Cash spots should NOT advertise ICM pressure
    assert "🏆 ICM" not in out
    # Chip-EV note should appear instead
    assert "Chip-EV" in out or "chip = $" in out


# ── Verdikt tier ────────────────────────────────────────────────────────


def test_correct_action_gets_green_verdict(cash_spot):
    # On a chart-backed spot, picking the actual best should be flagged correct
    from app.solver.mock_solver import solve_spot
    best = solve_spot(cash_spot).best_action
    out = teacher_review(cash_spot, best)
    assert "✅" in out
    assert "doğru" in out.lower() or "uyumlu" in out.lower()


def test_wrong_action_gets_warning_verdict(cash_spot):
    # Pick the WORST option deliberately (whichever isn't best)
    from app.solver.mock_solver import solve_spot
    best = solve_spot(cash_spot).best_action
    wrong = "fold" if best != "fold" else "raise"
    out = teacher_review(cash_spot, wrong)
    # Wrong → not the ✅ tier
    assert any(icon in out for icon in ("⚠", "❌", "🔥"))


# ── Integration: explain_spot dispatches to teacher_review ─────────────


def test_explain_spot_dispatches_to_teacher_when_action_given(cash_spot):
    tr_out = teacher_review(cash_spot, "call")
    es_out = explain_spot(cash_spot, "call")
    # Same key sections appear
    for header in ("KARAR DAĞILIMI", "NEDEN GTO", "MATEMATİK"):
        assert header in es_out


def test_explain_spot_brief_path_without_action(cash_spot):
    # No hero action → lighter brief — should still be valid string output
    out = explain_spot(cash_spot)
    assert isinstance(out, str)
    assert len(out) > 50
