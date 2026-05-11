"""CoachAgent — structured GTO + exploit advice for a single spot."""
from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentResult
from app.poker.alpha_mdf import alpha, mdf
from app.poker.pot_odds import required_equity
from app.solver.mock_solver import compare_action, solve_spot


class CoachAgent(Agent):
    name = "CoachAgent"

    def run(self, *, spot: dict, hero_action: str | None = None, **kwargs) -> AgentResult:
        if not spot:
            return AgentResult(agent=self.name, success=False, summary="No spot provided.")

        solver = solve_spot(spot)
        analysis: dict[str, Any] = {
            "best_action":     solver.best_action,
            "actions":         [{"action": a.action, "frequency": a.frequency, "ev": a.ev} for a in solver.actions],
            "source":          solver.source_confidence,
            "range_advantage": solver.range_advantage,
            "nut_advantage":   solver.nut_advantage,
        }

        # Math context
        pot  = float(spot.get("pot_bb", 10.0))
        risk = max(1.0, pot * 0.66)
        analysis["math"] = {
            "pot_bb":          pot,
            "required_equity": round(required_equity(risk, pot), 3),
            "alpha":           round(alpha(risk, pot), 3),
            "mdf":              round(mdf(risk, pot), 3),
        }

        # If hero made a decision, compare it
        if hero_action:
            cmp_ = compare_action(spot, hero_action)
            analysis["compare"]  = {
                "hero_action":   cmp_["hero_action"],
                "hero_ev":       cmp_["hero_ev"],
                "best_ev":       cmp_["best_ev"],
                "ev_loss":       cmp_["ev_loss"],
                "is_correct":    cmp_["is_correct"],
                "best_frequency":cmp_["best_frequency"],
            }
            verdict = "✅ Doğru karar" if cmp_["is_correct"] else (
                f"❌ Hatalı — GTO {cmp_['best_action']} ({cmp_['best_frequency']*100:.0f}%), "
                f"EV kayıp {cmp_['ev_loss']:.2f}bb"
            )
        else:
            verdict = f"GTO en iyisi: {solver.best_action}"

        summary = (
            f"{spot.get('name', spot.get('id', '?'))}: {verdict}.  "
            f"Required equity {analysis['math']['required_equity']*100:.0f}%, "
            f"MDF {analysis['math']['mdf']*100:.0f}%."
        )

        return AgentResult(
            agent   = self.name,
            success = True,
            summary = summary,
            data    = analysis,
            actions = [a["action"] for a in analysis["actions"]],
        )
