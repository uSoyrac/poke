"""SolverTreeView + tree builder tests."""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def btn_spot() -> dict:
    return {"position": "BTN", "stack_bb": 40, "street": "preflop",
            "hero_cards": "AsKs", "pot_type": "SRP", "pot_bb": 1.5}


# ── Tree builder ─────────────────────────────────────────────────────────

def test_build_tree_returns_root(btn_spot):
    from app.ui.components.solver_tree import build_solver_tree
    root = build_solver_tree(btn_spot)
    assert root is not None
    assert root.actor == "hero"


def test_tree_root_has_hero_options_as_children(btn_spot):
    from app.ui.components.solver_tree import build_solver_tree
    root = build_solver_tree(btn_spot)
    # AKs from BTN → raise 100% → at least one hero-option child
    assert len(root.children) >= 1


def test_aggressive_hero_actions_get_villain_responses(btn_spot):
    """If hero raises, the tree should branch into villain responses."""
    from app.ui.components.solver_tree import build_solver_tree
    root = build_solver_tree(btn_spot)
    raise_branch = next((c for c in root.children if "raise" in c.action.lower()), None)
    assert raise_branch is not None
    # Villain responses present (fold / call / 3bet)
    assert len(raise_branch.children) >= 2
    actors = {c.actor for c in raise_branch.children}
    assert "villain" in actors


def test_villain_call_branches_into_hero_followup(btn_spot):
    """Tree depth: hero → villain call → hero follow-up cbet/check."""
    from app.ui.components.solver_tree import build_solver_tree
    root = build_solver_tree(btn_spot)
    for h1 in root.children:
        for v in h1.children:
            if v.action == "call":
                assert len(v.children) >= 1, "Hero follow-up missing after villain call"
                assert all(c.actor == "hero" for c in v.children)
                return
    pytest.fail("No villain-call branch found to test follow-up")


def test_villain_response_frequencies_sum_close_to_1(btn_spot):
    from app.ui.components.solver_tree import build_solver_tree
    root = build_solver_tree(btn_spot)
    raise_branch = next((c for c in root.children if "raise" in c.action.lower()), None)
    if raise_branch is None:
        pytest.skip("No raise branch in tree")
    total = sum(c.frequency for c in raise_branch.children if c.actor == "villain")
    assert abs(total - 1.0) < 0.05  # within 5%


# ── Widget ─────────────────────────────────────────────────────────────

def test_solver_tree_widget_constructs(qapp):
    from app.ui.components.solver_tree import SolverTreeView
    w = SolverTreeView()
    assert w is not None
    w.close()


def test_set_from_spot_populates_tree(qapp, btn_spot):
    from app.ui.components.solver_tree import SolverTreeView
    w = SolverTreeView()
    w.set_from_spot(btn_spot)
    assert w._root is not None
    w.close()


def test_clear_wipes_tree(qapp, btn_spot):
    from app.ui.components.solver_tree import SolverTreeView
    w = SolverTreeView()
    w.set_from_spot(btn_spot)
    w.clear()
    assert w._root is None
    w.close()
