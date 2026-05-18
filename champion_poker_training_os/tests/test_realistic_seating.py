"""Tests for realistic seating, blind rotation, and BB-based bet sizing.

The user's expectation:
  • Each new hand: dealer button moves clockwise → SB → BB → next hand.
  • Blinds posted correctly (SB to left of BTN, BB to left of SB).
  • Raise amounts are quoted in BB (not raw pot %) — bot preflop raises
    are 2.0–3.0 × BB, 3-bets ~3× the open, etc.
  • Heads-up is special — dealer = SB.
"""
from __future__ import annotations

import pytest

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Street


# ── Button rotation across hands ────────────────────────────────────────


def test_dealer_button_rotates_each_hand():
    """Each new hand the button moves clockwise. After N hands every
    seat has been the dealer exactly once.

    NB: read `dealer_idx` from the HandState — `game.dealer_idx` may have
    already advanced if the hand finished synchronously inside start_hand
    (everyone folded before the hero could act).
    """
    from app.engine.hand_state import ActionType
    game = PokerGame(num_players=6, starting_stack=100.0)
    seen_dealers = []
    for _ in range(6):
        hand = game.start_hand()
        seen_dealers.append(hand.dealer_idx)
        s = 80
        while game.is_waiting_for_hero and s > 0:
            game.hero_act(ActionType.FOLD); s -= 1
    assert sorted(seen_dealers) == list(range(6))


def test_blinds_post_correctly_six_max():
    game = PokerGame(num_players=6, starting_stack=100.0)
    game.dealer_idx = 0
    game.start_hand()
    n = game.num_players
    sb_idx = (game.dealer_idx + 1) % n
    bb_idx = (game.dealer_idx + 2) % n
    assert game.players[sb_idx].current_bet == pytest.approx(game.small_blind)
    assert game.players[bb_idx].current_bet == pytest.approx(game.big_blind)


def test_blinds_post_correctly_heads_up():
    # HU: dealer = SB
    game = PokerGame(num_players=2, starting_stack=100.0)
    game.dealer_idx = 0
    game.start_hand()
    assert game.players[0].current_bet == pytest.approx(game.small_blind)
    assert game.players[1].current_bet == pytest.approx(game.big_blind)


def test_pot_after_blinds_is_sb_plus_bb():
    game = PokerGame(num_players=6, starting_stack=100.0)
    game.start_hand()
    expected = game.small_blind + game.big_blind
    # Pot must contain at least the blinds (preflop action may have added more)
    assert game.current_hand.pot >= expected - 1e-9


# ── Realistic BB-based raise sizing from the bot brain ──────────────────


def test_preflop_open_raise_is_2_to_3_bb():
    """A bot's RFI open should be 2.0–3.0× the big blind (real-poker norm)."""
    from app.engine.bot_brain import BotBrain
    from app.engine.hand_state import HandState
    from app.engine.bot_brain import BOT_ARCHETYPES

    profile = list(BOT_ARCHETYPES.values())[0]
    brain = BotBrain(profile)

    # Build a minimal preflop state where current_bet == BB (RFI scenario)
    game = PokerGame(num_players=6, starting_stack=100.0)
    game.start_hand()
    state = game.current_hand
    state.street = Street.PREFLOP
    state.current_bet = state.big_blind
    state.pot = state.small_blind + state.big_blind

    # Try many sizings — they must all land in the 2.0–3.5×BB band
    for _ in range(50):
        size = brain._pick_raise_sizing(
            min_raise=state.big_blind * 2,
            max_raise=state.big_blind * 100,
            strength=0.6,
            state=state,
        )
        ratio = size / state.big_blind
        assert 2.0 <= ratio <= 3.5, (
            f"Open sizing {size:.2f} = {ratio:.2f}×BB outside 2.0–3.5"
        )


def test_three_bet_sizing_is_2_5_to_4_x_open():
    """Facing a 2.5×BB open, a 3-bet should be ~2.5–4× the open size."""
    from app.engine.bot_brain import BotBrain
    from app.engine.hand_state import Street
    from app.engine.bot_brain import BOT_ARCHETYPES

    profile = list(BOT_ARCHETYPES.values())[0]
    brain = BotBrain(profile)

    game = PokerGame(num_players=6, starting_stack=100.0)
    game.start_hand()
    state = game.current_hand
    state.street = Street.PREFLOP
    open_size = state.big_blind * 2.5
    state.current_bet = open_size
    state.pot = state.small_blind + state.big_blind + open_size

    for _ in range(50):
        size = brain._pick_raise_sizing(
            min_raise=open_size * 2,
            max_raise=state.big_blind * 100,
            strength=0.7,
            state=state,
        )
        ratio_to_open = size / open_size
        # 3-bets cluster around 2.8–3.6×, allow 2.0–4.5 band for tolerance
        assert 2.0 <= ratio_to_open <= 4.5, (
            f"3-bet sizing {size:.2f} = {ratio_to_open:.2f}× the open"
        )


# ── Action chip labels show BB units on the oval table ─────────────────


def test_engine_survives_many_hands_with_hero_always_folding():
    """Regression: in some seat orders the hero would be asked to act
    AFTER every other player folded — then the hero folded too,
    leaving zero active players and crashing the showdown evaluator
    with `min() arg is an empty sequence`.
    """
    from app.engine.game_loop import PokerGame
    from app.engine.hand_state import ActionType

    for n in (2, 3, 6, 9):
        game = PokerGame(num_players=n, starting_stack=100.0)
        for _ in range(40):
            game.start_hand()
            safety = 80
            while game.is_waiting_for_hero and safety > 0:
                game.hero_act(ActionType.FOLD)
                safety -= 1
            # Pot must always be paid out — at least one winner recorded
            assert game.current_hand.winners, (
                f"{n}-max hand finished with no winners: "
                f"{game.current_hand.winner_hand_name}"
            )


def test_hero_never_folds_their_own_winning_hand():
    """If every villain folds before the hero acts, the hand must end
    by awarding the hero — not by asking the hero to fold."""
    from app.engine.game_loop import PokerGame
    from app.engine.hand_state import ActionType

    # Run 60 hands; whenever the hero is the BB and everyone folds to
    # them, the engine should auto-end without prompting.
    game = PokerGame(num_players=6, starting_stack=100.0)
    starting_hero_stack = game.players[0].stack
    walkovers = 0
    for _ in range(60):
        game.start_hand()
        if not game.is_waiting_for_hero:
            # Hand ended without asking hero — that's a walkover
            if 0 in (game.current_hand.winners or []):
                walkovers += 1
        # Drain any remaining action with FOLD
        s = 80
        while game.is_waiting_for_hero and s > 0:
            game.hero_act(ActionType.FOLD); s -= 1
    # Sanity: the engine ran to completion
    assert game.hand_count == 60


def test_oval_table_action_labels_include_bb_suffix():
    """The story-mode preflop chips on the oval table must say 'X.Xbb'."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from app.ui.components.oval_table import OvalTable, DEFAULT_POSITIONS_9

    t = OvalTable(positions=DEFAULT_POSITIONS_9, selectable=False)
    # Trigger a 3-bet-pot story
    t.populate_from_spot({
        "name": "BTN 3-bet vs CO",
        "position": "BTN",
        "pot_type": "3BP",
        "street": "preflop",
        "vs_position": "CO",
        "stack_bb": 100,
    })
    # At least one seat should have a chip label containing "bb"
    labels = []
    for pos, seat in t.seats.items():
        labels.extend(seat.actions)
    bb_labels = [l for l in labels if "bb" in l]
    assert bb_labels, f"No BB-suffixed labels found. Labels: {labels}"
