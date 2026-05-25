"""Bot archetype fidelity simulation.

Runs N hands per archetype with that archetype filling every non-hero seat
(hero just folds preflop). Measures the *realized* VPIP/PFR/AF/F-cbet and
compares against the BotProfile's *target* values. A profile is flagged if
the observed value deviates by more than the tolerance.

Run directly:

    .venv/bin/python3 tests/test_bot_archetype_fidelity.py

The script prints a table of target vs. observed per archetype.
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType, Street


HANDS_PER_ARCHETYPE = 400
SEATS = 6  # hero + 5 bots of the same archetype
HERO_SEAT = 0


def _simulate(archetype: str, n_hands: int) -> dict:
    """Run n_hands and aggregate stats across every bot seat."""
    game = PokerGame(
        num_players=SEATS,
        starting_stack=100.0,
        small_blind=0.5,
        big_blind=1.0,
        hero_seat=HERO_SEAT,
        bot_archetypes=[archetype] * (SEATS - 1),
        paced_bots=False,   # auto-run bots
    )

    # Aggregate counters across all bot seats
    bot_indices = [i for i in range(SEATS) if i != HERO_SEAT]
    hands_seen = defaultdict(int)
    vpip_n = defaultdict(int)
    pfr_n = defaultdict(int)
    threebet_opp = defaultdict(int)
    threebet_did = defaultdict(int)
    cbet_faced = defaultdict(int)
    cbet_folded = defaultdict(int)
    aggr_acts = defaultdict(int)
    call_acts = defaultdict(int)

    for h in range(n_hands):
        # Reset stacks so blinds don't drain bots over time
        for p in game.players:
            p.stack = 100.0
            p.is_eliminated = False
        game.start_hand()
        # Hero folds immediately when it's hero's turn (we want to see bots play)
        guard = 0
        while game.current_hand and not game.current_hand.is_complete and guard < 200:
            if game.is_waiting_for_hero:
                game.hero_act(ActionType.FOLD, 0)
            else:
                game.step_action()
            guard += 1

        hand = game.current_hand
        if not hand:
            continue
        actions = hand.actions

        for idx in bot_indices:
            if game.players[idx].is_eliminated:
                continue
            hands_seen[idx] += 1
            pf_actions = [a for a in actions
                          if a.player_idx == idx and a.street == Street.PREFLOP]
            if any(a.action_type in (ActionType.CALL, ActionType.RAISE,
                                      ActionType.BET, ActionType.ALL_IN)
                   for a in pf_actions):
                vpip_n[idx] += 1
            if any(a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN)
                   for a in pf_actions):
                pfr_n[idx] += 1

            # 3-bet: this player faced a preflop raise then re-raised
            prior_raises_when_acting = False
            saw_raise_before_me = False
            for a in actions:
                if a.street != Street.PREFLOP:
                    break
                if a.player_idx == idx:
                    if saw_raise_before_me:
                        threebet_opp[idx] += 1
                        if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
                            threebet_did[idx] += 1
                        break
                elif a.action_type in (ActionType.RAISE, ActionType.BET):
                    saw_raise_before_me = True

            # Fold to flop cbet
            flop_bets_by_others = [a for a in actions
                                   if a.street == Street.FLOP
                                   and a.player_idx != idx
                                   and a.action_type in (ActionType.BET, ActionType.RAISE)]
            my_flop = [a for a in actions
                       if a.street == Street.FLOP and a.player_idx == idx]
            if flop_bets_by_others and my_flop:
                # Was the first opponent action a bet/raise BEFORE my first flop action?
                first_my_flop_idx = next((i for i, a in enumerate(actions)
                                          if a.street == Street.FLOP and a.player_idx == idx), None)
                if first_my_flop_idx is not None:
                    prior_flop = [a for a in actions[:first_my_flop_idx]
                                  if a.street == Street.FLOP and a.player_idx != idx
                                  and a.action_type in (ActionType.BET, ActionType.RAISE)]
                    if prior_flop:
                        cbet_faced[idx] += 1
                        first_action = actions[first_my_flop_idx].action_type
                        if first_action == ActionType.FOLD:
                            cbet_folded[idx] += 1

            # Postflop aggression
            for a in actions:
                if a.player_idx != idx or a.street == Street.PREFLOP:
                    continue
                if a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
                    aggr_acts[idx] += 1
                elif a.action_type == ActionType.CALL:
                    call_acts[idx] += 1

    # Average across bot seats
    def avg(d):
        vals = [d[i] / max(hands_seen[i], 1) for i in bot_indices if hands_seen[i] > 0]
        return 100 * sum(vals) / len(vals) if vals else 0.0

    def avg_pct(numer, denom):
        vals = []
        for i in bot_indices:
            if denom[i] > 0:
                vals.append(numer[i] / denom[i])
        return 100 * sum(vals) / len(vals) if vals else 0.0

    af_vals = [aggr_acts[i] / max(call_acts[i], 1)
               for i in bot_indices if (aggr_acts[i] + call_acts[i]) > 0]
    af_avg = sum(af_vals) / len(af_vals) if af_vals else 0.0

    return {
        "hands_total": sum(hands_seen[i] for i in bot_indices),
        "vpip": avg(vpip_n),
        "pfr": avg(pfr_n),
        "three_bet": avg_pct(threebet_did, threebet_opp),
        "fold_to_cbet": avg_pct(cbet_folded, cbet_faced),
        "af": af_avg,
    }


def main() -> int:
    print(f"\n{'='*94}")
    print(f"BOT ARCHETYPE FIDELITY SIMULATION  ·  {HANDS_PER_ARCHETYPE} hands × {SEATS-1} bots per archetype")
    print(f"{'='*94}")
    print(f"{'ARCHETYPE':<18} | {'TARGET':>33} | {'OBSERVED':>34} | {'STATUS'}")
    print(f"{'':<18} | {'VPIP   PFR   3B   F-CB   AF':>33} | {'VPIP   PFR   3B   F-CB   AF':>34} |")
    print("-" * 94)

    # Tolerances — preflop should be tight, postflop has more variance
    TOL = {"vpip": 6, "pfr": 6, "three_bet": 5, "fold_to_cbet": 12, "af": 1.2}

    issues: list[str] = []
    skip = {"Karma (Mixed)"}  # mixed isn't a single archetype to measure

    t0 = time.time()
    for name, prof in BOT_ARCHETYPES.items():
        if name in skip:
            continue
        obs = _simulate(name, HANDS_PER_ARCHETYPE)
        target = (prof.vpip, prof.pfr, prof.three_bet, prof.fold_to_cbet, prof.aggression)
        observed = (obs["vpip"], obs["pfr"], obs["three_bet"], obs["fold_to_cbet"], obs["af"])

        flags = []
        if abs(obs["vpip"] - prof.vpip) > TOL["vpip"]: flags.append("VPIP")
        if abs(obs["pfr"] - prof.pfr) > TOL["pfr"]: flags.append("PFR")
        if abs(obs["three_bet"] - prof.three_bet) > TOL["three_bet"]: flags.append("3B")
        if abs(obs["fold_to_cbet"] - prof.fold_to_cbet) > TOL["fold_to_cbet"]: flags.append("FCB")
        if abs(obs["af"] - prof.aggression) > TOL["af"]: flags.append("AF")

        status = "OK" if not flags else "DEV: " + ",".join(flags)
        if flags:
            issues.append(f"{name}: {','.join(flags)} (target vs observed: {target} vs {tuple(round(x,1) for x in observed)})")

        print(f"{name:<18} | "
              f"{prof.vpip:>5.0f}  {prof.pfr:>4.0f}  {prof.three_bet:>3.0f}  "
              f"{prof.fold_to_cbet:>4.0f}  {prof.aggression:>4.1f} | "
              f"{obs['vpip']:>5.1f}  {obs['pfr']:>4.1f}  {obs['three_bet']:>3.0f}  "
              f"{obs['fold_to_cbet']:>4.0f}  {obs['af']:>4.1f} | "
              f"{status}")

    dt = time.time() - t0
    print("-" * 94)
    print(f"DONE in {dt:.1f}s — {len(issues)} archetype(s) need tuning.")
    if issues:
        print()
        for line in issues:
            print(f"  ✗ {line}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
