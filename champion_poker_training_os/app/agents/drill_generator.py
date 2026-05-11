"""DrillGeneratorAgent — builds personalised drill packs from detected leaks."""
from __future__ import annotations

from typing import Any

from app.agents.base import Agent, AgentResult
from app.db.drill_catalog import build_full_catalog


class DrillGeneratorAgent(Agent):
    name = "DrillGeneratorAgent"

    def run(self, *, leaks: list[dict] | None = None, pack_size: int = 10, **kwargs) -> AgentResult:
        leaks = leaks or []
        catalog = build_full_catalog()
        chosen: list[dict] = []

        # For each leak, pick matching drills
        for leak in leaks:
            pos    = leak.get("position", "")
            street = leak.get("street", "")
            pot_t  = leak.get("pot_type", "")
            for d in catalog:
                if d in chosen:
                    continue
                if (d.get("position") == pos
                        and d.get("street") == street
                        and pot_t.lower() in (d.get("pot_type", "") or "").lower()):
                    chosen.append(d)
                    if len(chosen) >= pack_size:
                        break
            if len(chosen) >= pack_size:
                break

        # If we don't have enough, fill with top-priority general drills (high EV swing)
        if len(chosen) < pack_size:
            fillers = [d for d in catalog if d not in chosen][: pack_size - len(chosen)]
            chosen.extend(fillers)

        return AgentResult(
            agent   = self.name,
            success = bool(chosen),
            summary = f"Generated drill pack with {len(chosen)} spots from {len(leaks)} leaks",
            data    = {
                "drills":  chosen,
                "spot_ids":[d["id"] for d in chosen],
            },
            actions = [d["id"] for d in chosen],
        )
