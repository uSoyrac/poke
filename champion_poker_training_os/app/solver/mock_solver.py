from __future__ import annotations

import hashlib
from dataclasses import asdict

from app.solver.solver_schema import SolverAction, SolverResult


BASE_ACTIONS = ("fold", "check", "call", "bet small", "bet medium", "bet large", "raise", "jam")


def _stable_number(text: str, modulo: int) -> int:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def solve_spot(spot: dict) -> SolverResult:
    options = tuple(spot.get("options") or BASE_ACTIONS[:5])
    best = spot.get("best_action") or options[_stable_number(spot.get("id", "spot"), len(options))]
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

