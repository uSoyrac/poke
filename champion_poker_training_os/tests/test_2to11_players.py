"""Verify 2-11 player support across the engine + position assignment."""
from __future__ import annotations

import pytest

from app.engine.game_loop import PokerGame
from app.engine.hand_state import positions_for


@pytest.mark.parametrize("n", list(range(2, 12)))
def test_position_list_size_matches_player_count(n: int):
    positions = positions_for(n)
    assert len(positions) == n, f"Expected {n} positions, got {len(positions)}"
    # SB and BB always present (except heads-up which is SB+BB only)
    assert "SB" in positions
    assert "BB" in positions


@pytest.mark.parametrize("n", list(range(2, 12)))
def test_game_supports_n_players(n: int):
    game = PokerGame(num_players=n, starting_stack=100.0)
    assert game.num_players == n
    assert len(game.players) == n
    game.start_hand()
    assert game.current_hand is not None
    # Every player got a position
    assigned = [p.position for p in game.players]
    assert all(p for p in assigned), f"Some players missing positions: {assigned}"
    # All positions unique
    assert len(set(assigned)) == n


def test_clamps_below_minimum():
    game = PokerGame(num_players=1, starting_stack=100.0)
    assert game.num_players == 2  # clamped up


def test_clamps_above_maximum():
    game = PokerGame(num_players=15, starting_stack=100.0)
    assert game.num_players == 11  # clamped down


def test_heads_up_has_sb_bb():
    g = PokerGame(num_players=2, starting_stack=100.0)
    g.start_hand()
    positions = {p.position for p in g.players}
    assert positions == {"SB", "BB"}


def test_eleven_max_includes_btn_and_co():
    g = PokerGame(num_players=11, starting_stack=100.0)
    g.start_hand()
    positions = [p.position for p in g.players]
    assert "BTN" in positions
    assert "CO" in positions
    assert "HJ" in positions


def test_game_can_play_a_hand_with_eight_players():
    """Smoke test that the engine actually completes a hand at non-trivial size."""
    g = PokerGame(num_players=8, starting_stack=100.0)
    g.start_hand()
    # Should reach a state where hero is waiting OR hand completed
    assert g.current_hand is not None
    # Auto-fold hero through to completion to confirm engine doesn't crash
    safety = 200
    from app.engine.hand_state import ActionType
    while not g.current_hand.is_complete and safety > 0:
        if g.is_waiting_for_hero:
            g.hero_act(ActionType.FOLD, 0)
        safety -= 1
    assert g.current_hand.is_complete
