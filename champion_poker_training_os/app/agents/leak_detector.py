"""LeakDetectionAgent — finds systemic mistakes in played hand history."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.agents.base import Agent, AgentResult


class LeakDetectionAgent(Agent):
    name = "LeakDetectionAgent"

    def run(self, *, hands: list[dict] | None = None, min_sample: int = 3, **kwargs) -> AgentResult:
        hands = hands or []
        if not hands:
            return AgentResult(agent=self.name, success=False, summary="No hands to analyse.")

        # Group by (position, pot_type, street) and aggregate ev_loss
        groups: dict[tuple, list[float]] = defaultdict(list)
        for h in hands:
            key = (
                h.get("position", "?"),
                h.get("pot_type", "?"),
                h.get("street", "?"),
            )
            ev_loss = float(h.get("ev_loss", 0.0))
            groups[key].append(ev_loss)

        leaks: list[dict[str, Any]] = []
        for (pos, pot_type, street), losses in groups.items():
            if len(losses) < min_sample:
                continue
            total = sum(losses)
            avg   = total / len(losses)
            if total < 1.0:  # not worth flagging
                continue
            severity = (
                "Critical" if total >= 15
                else "High"  if total >= 7
                else "Medium"
            )
            leaks.append({
                "position":     pos,
                "pot_type":     pot_type,
                "street":       street,
                "sample":       len(losses),
                "total_ev_loss":round(total, 2),
                "avg_ev_loss":  round(avg, 2),
                "severity":     severity,
                "name":         f"{pos} {pot_type} {street} leak",
            })

        leaks.sort(key=lambda l: -l["total_ev_loss"])
        summary = (f"Detected {len(leaks)} leak{'s' if len(leaks) != 1 else ''}; "
                   f"total {sum(l['total_ev_loss'] for l in leaks):.1f}bb lost")
        return AgentResult(
            agent   = self.name,
            success = True,
            summary = summary,
            data    = {"leaks": leaks, "total_hands": len(hands)},
            actions = [l["name"] for l in leaks],
        )
