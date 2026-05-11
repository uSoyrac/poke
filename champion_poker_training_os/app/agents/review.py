"""ReviewAgent — tag every decision in a played hand with GTO evaluation."""
from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentResult
from app.solver.mock_solver import compare_action


class ReviewAgent(Agent):
    name = "ReviewAgent"

    def run(self, *, decisions: list[dict] | None = None, **kwargs) -> AgentResult:
        decisions = decisions or []
        reviewed: list[dict[str, Any]] = []
        total_ev_loss = 0.0
        mistakes      = 0

        for d in decisions:
            spot   = d.get("spot") or d
            action = d.get("hero_action") or d.get("action") or "fold"
            try:
                cmp_ = compare_action(spot, action)
            except Exception:
                continue
            entry = {
                "street":      spot.get("street", "?"),
                "position":    spot.get("position", "?"),
                "hero_action": action,
                "gto_action":  cmp_["best_action"],
                "ev_loss":     cmp_["ev_loss"],
                "is_correct":  cmp_["is_correct"],
                "freq":        cmp_["best_frequency"],
            }
            reviewed.append(entry)
            total_ev_loss += cmp_["ev_loss"]
            if not cmp_["is_correct"]:
                mistakes += 1

        return AgentResult(
            agent   = self.name,
            success = True,
            summary = (
                f"Reviewed {len(reviewed)} decisions · "
                f"{mistakes} mistake{'s' if mistakes != 1 else ''} · "
                f"total EV lost {total_ev_loss:.2f}bb"
            ),
            data    = {
                "reviewed":      reviewed,
                "total_ev_loss": round(total_ev_loss, 2),
                "mistake_count": mistakes,
                "accuracy":      round(100 * (len(reviewed) - mistakes) / max(len(reviewed), 1), 1),
            },
        )
