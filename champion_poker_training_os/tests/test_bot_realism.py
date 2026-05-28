"""Regression: bots must not make unrealistic all-ins.

Root cause that this guards against (fixed 2026-05-29): postflop bet/raise
sizes were chosen as a pot fraction with NO SPR awareness. At low SPR a
"normal" half-pot c-bet or river bluff equals the whole stack, so the engine
coerced it to ALL-IN — i.e. the bot shoved 7-high / a small underpair as a
"bluff" or "thin value bet". An SPR-aware commitment gate in BotBrain now
refuses to commit the stack without genuine value or a real semi-bluff draw.

A "voluntary trash jam" = the bot BETS or RAISES all-in (to_call < stack) with
a weak, draw-less hand while still holding a meaningful stack (>6bb). Calling
an all-in for pot odds is NOT counted (calling 8bb into an 80bb pot is correct).
"""
from __future__ import annotations
import random

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from app.engine.bot_brain import hand_key


def _collect_allins(n_hands: int, stack_bb: float, seed: int):
    random.seed(seed)
    gl = PokerGame(
        num_players=8, starting_stack=stack_bb,
        small_blind=0.5, big_blind=1.0, ante=0.1,
        hero_seat=0, bot_archetype="Karma (Mixed)", paced_bots=True,
    )
    logged = []
    orig_apply = gl._apply_action

    def logging_apply(player_idx, action_type, amount):
        if action_type == ActionType.ALL_IN and player_idx in gl.bots:
            hand = gl.current_hand
            p = hand.players[player_idx]
            bot = gl.bots[player_idx]
            strength, draws, _ = bot._hand_strength(p.hole_cards, hand.community)
            logged.append({
                "strength": strength,
                "draws": draws,
                "stack_bb": p.stack,
                "to_call_bb": hand.to_call(player_idx),
                "arch": bot.profile.name,
            })
        return orig_apply(player_idx, action_type, amount)

    gl._apply_action = logging_apply

    for _ in range(n_hands):
        gl.start_hand()
        guard = 0
        while guard < 400:
            guard += 1
            if gl.current_hand and gl.current_hand.is_complete:
                break
            progressed = gl.step_action()
            if gl.is_waiting_for_hero:
                h = gl.current_hand
                tc = h.to_call(h.hero_idx)
                gl.hero_act(ActionType.FOLD if tc > 0 else ActionType.CHECK, 0.0)
            elif not progressed:
                break
        for p in gl.players:
            p.reset_for_hand(stack_bb)
    return logged


def test_no_voluntary_trash_jams():
    """Bots never BET/RAISE all-in with a weak, draw-less hand while deep."""
    allins = _collect_allins(n_hands=1500, stack_bb=25.0, seed=7)
    assert allins, "expected some all-ins to occur in 1500 hands"

    trash_jams = [
        r for r in allins
        if r["strength"] < 0.45            # weak (worse than middle pair)
        and r["draws"] < 0.25              # no real draw
        and r["stack_bb"] > 6.0            # still meaningfully deep
        and r["to_call_bb"] < r["stack_bb"] - 0.05   # BETTING/RAISING, not calling
    ]
    assert not trash_jams, (
        f"{len(trash_jams)} voluntary trash jams found (should be 0). "
        f"Sample: {trash_jams[:5]}"
    )


def test_value_and_draw_allins_still_happen():
    """The gate must not over-suppress legitimate commitment — strong hands
    and real semi-bluffs should still be able to get all-in."""
    allins = _collect_allins(n_hands=1500, stack_bb=25.0, seed=7)
    legit = [r for r in allins if r["strength"] >= 0.60 or r["draws"] >= 0.30
             or r["to_call_bb"] >= r["stack_bb"] - 0.05]
    assert legit, "expected legitimate value/draw/odds all-ins to remain"
