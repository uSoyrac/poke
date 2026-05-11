from __future__ import annotations

import hashlib
from dataclasses import asdict

from app.solver.csv_importer import get_solver_library
from app.solver.preflop_charts import (
    aggregate_strategy,
    chart_for_spot,
    hand_169_from_cards,
    strategy_for_hand,
)
from app.solver.solver_schema import SolverAction, SolverResult


BASE_ACTIONS = ("fold", "check", "call", "bet small", "bet medium", "bet large", "raise", "jam")


def _stable_number(text: str, modulo: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def solve_spot(spot: dict) -> SolverResult:
    """Return the GTO strategy for this spot.

    Priority:
      1. Imported PIO/GTO Wizard CSV (per-spot_id override)
      2. Pre-solved preflop chart database (per position × stack × vs)
      3. Heuristic fallback (_mock_solve_spot)
    """
    # 1) CSV override
    spot_id = spot.get("id")
    if spot_id:
        library = get_solver_library()
        imported = library.get(str(spot_id))
        if imported is not None:
            return imported

    # 2) Pre-solved chart (only for preflop spots — postflop falls through)
    street = (spot.get("street") or "preflop").lower()
    if street == "preflop":
        chart = chart_for_spot(spot)
        if chart:
            return _chart_to_solver_result(spot, chart)

    # 3) Heuristic fallback
    return _mock_solve_spot(spot)


def _chart_to_solver_result(spot: dict, chart: dict) -> SolverResult:
    """Convert a 169-cell chart into a SolverResult.

    If hero cards are known → use exact strategy for that hand.
    Otherwise → aggregate strategy over the whole chart (avg frequencies).
    """
    hand_169 = hand_169_from_cards(spot.get("hero_cards", ""))
    if hand_169:
        strat = strategy_for_hand(chart, hand_169)
        if not strat:
            strat = aggregate_strategy(chart)
    else:
        strat = aggregate_strategy(chart)

    # Build SolverAction list ordered as in spot options (if provided)
    options = spot.get("options") or tuple(strat.keys())
    base_ev = float(spot.get("base_ev", 1.0))
    actions: list[SolverAction] = []

    # Action group mapping — different chart labels map to the same option button
    # so e.g. "3bet" / "4bet" / "raise" all match option "raise" or "3bet".
    AGGRO   = {"raise", "3bet", "4bet", "5bet", "bet"}
    SHOVE   = {"jam", "all_in", "all-in", "allin"}
    PASSIVE = {"call", "check"}
    PASS    = {"fold"}

    def _group(a: str) -> str:
        a = a.lower().replace("-", "_").replace(" ", "_")
        if a in PASS:    return "fold"
        if a in PASSIVE: return a  # keep call / check distinct
        if a in SHOVE:   return "jam"
        if a in AGGRO:   return "raise"
        if "bet" in a:   return "raise"
        return a

    def _best_freq_for_option(opt: str) -> float:
        """Sum chart frequencies of all chart-keys that map to opt's group."""
        target = _group(opt)
        total = 0.0
        for ck, cf in strat.items():
            if _group(ck) == target:
                total += cf
            # Special: "3bet" in BB defense maps to BOTH "raise" and "3bet" option labels
            elif target == "3bet" and ck.lower() in ("3bet", "4bet", "raise"):
                total += cf
        # If option is "raise" and chart had a "3bet" → also count it
        if target == "raise":
            for ck, cf in strat.items():
                if ck.lower() in ("3bet", "4bet") and _group(ck) != "raise":
                    total += cf
        return min(1.0, total)

    for opt in options:
        freq = _best_freq_for_option(opt)
        # Convert freq to EV: higher freq → closer to base_ev; 0 freq → -ev cost
        if freq >= 0.9:    ev = base_ev
        elif freq >= 0.4:  ev = base_ev * 0.7
        elif freq >= 0.05: ev = base_ev * 0.3
        else:              ev = -abs(base_ev) * 0.5
        actions.append(SolverAction(
            action=opt, frequency=round(freq, 4),
            ev=round(ev, 2), sizing=_sizing_label(opt, spot),
        ))

    # Best action = highest frequency
    if actions:
        best = max(actions, key=lambda a: a.frequency)
    else:
        best = SolverAction(action="fold", frequency=1.0, ev=0.0, sizing="")
        actions = [best]

    # Normalise — sum to 1.0 across listed options when possible
    total = sum(a.frequency for a in actions)
    if total > 0:
        actions = [
            SolverAction(
                a.action,
                round(a.frequency / total, 4) if total > 1.0 else round(a.frequency, 4),
                a.ev, a.sizing,
            )
            for a in actions
        ]

    explanation = (
        f"GTO chart match for {spot.get('position', '?')} "
        f"{spot.get('stack_bb', '?')}bb {street if (street := spot.get('street', 'preflop')) else 'preflop'}. "
        f"Hand {hand_169 or 'unknown'} → best {best.action} ({best.frequency*100:.0f}%)."
    )
    return SolverResult(
        spot_id=spot.get("id", "demo"),
        best_action=best.action,
        actions=tuple(actions),
        source_confidence="Pre-solved chart",
        range_advantage=spot.get("range_advantage", ""),
        nut_advantage=spot.get("nut_advantage", ""),
        explanation=explanation,
    )


def _mock_solve_spot(spot: dict) -> SolverResult:
    options = tuple(spot.get("options") or BASE_ACTIONS[:5])
    best = spot.get("best_action") or options[_stable_number(spot.get("id", "spot"), len(options))]
    # Defensive: if best_action isn't in options, pick a middle option
    if best not in options:
        best = options[len(options) // 2] if options else "fold"
    source = spot.get("source_confidence", "Mock/demo solver")
    base_ev = float(spot.get("base_ev", 1.35))
    actions: list[SolverAction] = []
    for idx, action in enumerate(options):
        distance = 0 if action == best else abs(idx - options.index(best)) + 1
        frequency = max(0.04, 0.62 - distance * 0.16)
        ev = round(base_ev - distance * (0.18 + _stable_number(action + spot.get("id", ""), 8) / 100), 2)
        if action == best:
            frequency = max(frequency, 0.58)
            ev = round(base_ev, 2)
        actions.append(SolverAction(action=action, frequency=round(frequency, 2), ev=ev, sizing=_sizing_label(action, spot)))

    total = sum(a.frequency for a in actions)
    normalized = tuple(
        SolverAction(a.action, round(a.frequency / total, 2), a.ev, a.sizing)
        for a in actions
    )
    return SolverResult(
        spot_id=spot.get("id", "demo"),
        best_action=best,
        actions=normalized,
        source_confidence=source,
        range_advantage=spot.get("range_advantage", "Hero has slight range advantage"),
        nut_advantage=spot.get("nut_advantage", "Villain retains more nut combos"),
        explanation=_explanation(spot, best),
    )


def compare_action(spot: dict, hero_action: str) -> dict:
    result = solve_spot(spot)
    best = result.action_by_name(result.best_action)
    hero = result.action_by_name(hero_action)
    best_ev = best.ev if best else 0.0
    hero_ev = hero.ev if hero else best_ev - 0.75
    ev_loss = round(max(best_ev - hero_ev, 0.0), 2)
    best_freq = best.frequency if best else 0.0
    hero_freq = hero.frequency if hero else 0.0
    return {
        "solver": asdict(result),
        "hero_action": hero_action,
        "best_action": result.best_action,
        "hero_ev": round(hero_ev, 2),
        "best_ev": round(best_ev, 2),
        "ev_loss": ev_loss,
        "solver_frequency": round(hero_freq, 2),
        "best_frequency": round(best_freq, 2),
        "is_correct": hero_action == result.best_action or ev_loss <= 0.10,
        "sizing_feedback": _sizing_feedback(hero_action, result.best_action),
    }


def _sizing_label(action: str, spot: dict) -> str:
    pot = float(spot.get("pot_bb", 10.0))
    if "small" in action:
        return f"{pot * 0.33:.1f}bb / 33% pot"
    if "medium" in action:
        return f"{pot * 0.66:.1f}bb / 66% pot"
    if "large" in action:
        return f"{pot * 1.10:.1f}bb / 110% pot"
    if action == "jam":
        return f"{spot.get('stack_bb', 25)}bb all-in"
    if action == "raise":
        return f"{pot * 2.4:.1f}bb raise"
    return ""


def _sizing_feedback(hero_action: str, best_action: str) -> str:
    if hero_action == best_action:
        return "Sizing aligned with the solver baseline."
    if "small" in best_action:
        return "Solver prefers lower risk, high-frequency pressure."
    if "large" in best_action or best_action == "jam":
        return "Solver wants polar pressure; small sizing leaves EV behind."
    return "Main error is action class/frequency, not only sizing."


def _explanation(spot: dict, best: str) -> str:
    texture = spot.get("board_texture", "dynamic")
    position = spot.get("position", "BTN")
    return (
        f"{position} spot on a {texture} texture: baseline prefers {best}. "
        "This is demo solver data, so treat it as training guidance rather than exact GTO."
    )

