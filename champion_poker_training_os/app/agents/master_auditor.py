"""MasterAuditorAgent — drives every other agent through a full coverage sweep.

This is the agent the user asked for: a poker-master assistant that runs the
entire system through realistic scenarios and produces a structured report
the developer (or the user) can act on.

Coverage:
  • Drill catalog integrity      (count, fields, unique ids, options)
  • Per-position chart lookup    (does the right chart load per position?)
  • Solver dynamics              (different spots → different action mixes)
  • Multi-agent pipeline         (Coach + Review + LeakDetector + DrillGen + Master)
  • Self-play sanity             (PokerPlayingAgent finishes hands at 2/6/9-max)
  • Master coach coverage        (every spot category produces non-empty analysis)

Output: AuditReport dataclass with per-section results + an overall verdict.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from app.agents.base import Agent, AgentResult
from app.agents.coach import CoachAgent
from app.agents.drill_generator import DrillGeneratorAgent
from app.agents.gto_master import GTOMasterAgent
from app.agents.leak_detector import LeakDetectionAgent
from app.agents.poker_player import PokerPlayingAgent
from app.agents.review import ReviewAgent
from app.db.drill_catalog import build_full_catalog
from app.solver.mock_solver import solve_spot
from app.solver.preflop_charts import (
    chart_for_spot,
    hand_169_from_cards,
    strategy_for_hand,
)


@dataclass
class CheckResult:
    name:    str
    passed:  bool
    detail:  str
    samples: list[Any] = field(default_factory=list)


@dataclass
class AuditReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def all_green(self) -> bool:
        return self.failed == 0

    def to_markdown(self) -> str:
        lines = [
            f"# Master Audit Report",
            f"**Status:** {'✅ All green' if self.all_green else f'⚠️ {self.failed} failed'}",
            f"**Passed:** {self.passed} / {len(self.checks)}",
            "",
            "## Checks",
        ]
        for c in self.checks:
            icon = "✅" if c.passed else "❌"
            lines.append(f"- {icon} **{c.name}** — {c.detail}")
            if c.samples and not c.passed:
                for s in c.samples[:3]:
                    lines.append(f"    · {s}")
        return "\n".join(lines)


class MasterAuditorAgent(Agent):
    name = "MasterAuditorAgent"

    def __init__(self):
        self.coach   = CoachAgent()
        self.master  = GTOMasterAgent()
        self.review  = ReviewAgent()
        self.leak    = LeakDetectionAgent()
        self.drill   = DrillGeneratorAgent()
        self.player  = PokerPlayingAgent("Balanced Reg")

    def run(self, **kwargs) -> AgentResult:
        report = AuditReport()

        # ── 1) Catalog integrity ────────────────────────────────────
        catalog = build_full_catalog()
        report.checks.append(CheckResult(
            name="Drill catalog ≥ 300 spots",
            passed=len(catalog) >= 300,
            detail=f"{len(catalog)} drills loaded",
        ))

        required_fields = {"id", "position", "stack_bb", "street", "hero_cards",
                           "options", "best_action", "pot_bb", "format", "category"}
        bad = [d["id"] for d in catalog if not required_fields.issubset(set(d.keys()))]
        report.checks.append(CheckResult(
            name="All drills have required fields",
            passed=not bad,
            detail=f"{len(catalog) - len(bad)} ok, {len(bad)} missing fields",
            samples=bad,
        ))

        ids = [d["id"] for d in catalog]
        dupes = [i for i in set(ids) if ids.count(i) > 1]
        report.checks.append(CheckResult(
            name="Drill ids unique",
            passed=not dupes,
            detail=f"{len(set(ids))} unique ids" if not dupes else f"{len(dupes)} duplicates",
            samples=dupes,
        ))

        # ── 2) Chart variety per position ───────────────────────────
        per_pos: dict[str, set] = {}
        for d in catalog:
            if d.get("street") != "preflop":
                continue
            pos = d.get("position", "?")
            chart = chart_for_spot(d)
            sig = tuple(sorted(chart.keys()))[:5]
            per_pos.setdefault(pos, set()).add(hash(sig + tuple(chart.get("AA", {}).items())))
        pos_with_chart = [p for p, s in per_pos.items() if s]
        report.checks.append(CheckResult(
            name="Every position has at least 1 chart",
            passed=len(pos_with_chart) >= 5,
            detail=f"Positions: {sorted(pos_with_chart)}",
        ))

        # ── 3) Hand-specific strategy lookup works ─────────────────
        probes = [
            ("BTN", "AsKs", "raise"),
            ("UTG", "7s2d", "fold"),
            ("CO",  "JsTs", "raise"),
            ("BB",  "5d5c", "call"),
        ]
        probe_failures = []
        for pos, cards, expected in probes:
            spot = {"position": pos, "stack_bb": 40, "street": "preflop",
                    "hero_cards": cards, "pot_type": "SRP"}
            chart = chart_for_spot(spot)
            h169 = hand_169_from_cards(cards)
            strat = strategy_for_hand(chart, h169 or "")
            top = max(strat.items(), key=lambda kv: kv[1])[0] if strat else None
            if not top or expected not in top.lower() and top.lower() not in expected:
                probe_failures.append(f"{pos} {cards} → expected {expected}, got {top}")
        report.checks.append(CheckResult(
            name="Hand-specific GTO lookups match expected baselines",
            passed=not probe_failures,
            detail=f"{len(probes) - len(probe_failures)} / {len(probes)} probes match",
            samples=probe_failures,
        ))

        # ── 4) Solver dynamic — different spots → different mixes ──
        sample_spots = random.sample(catalog, min(8, len(catalog)))
        action_signatures = set()
        for s in sample_spots:
            r = solve_spot(s)
            sig = tuple(round(a.frequency, 2) for a in r.actions)
            action_signatures.add(sig)
        report.checks.append(CheckResult(
            name="Solver produces varied output across spots",
            passed=len(action_signatures) > 1,
            detail=f"{len(action_signatures)} unique action signatures over {len(sample_spots)} samples",
        ))

        # ── 5) Multi-agent pipeline ────────────────────────────────
        try:
            review_decisions = [{"spot": s, "hero_action": random.choice(s["options"])}
                                for s in random.sample(catalog, 8)]
            review_res = self.review.run(decisions=review_decisions)
            leak_hands = [
                {"position": d["position"], "pot_type": "SRP", "street": d["street"],
                 "ev_loss": d.get("ev_loss", 0)}
                for d in review_res.data.get("reviewed", [])
            ]
            leak_res = self.leak.run(hands=leak_hands, min_sample=1)
            drill_res = self.drill.run(leaks=leak_res.data.get("leaks", []), pack_size=5)
            pipeline_ok = (review_res.success and leak_res.success and drill_res.success)
            report.checks.append(CheckResult(
                name="Multi-agent pipeline (review → leaks → drills)",
                passed=pipeline_ok,
                detail=f"reviewed {len(review_res.data.get('reviewed', []))}, "
                       f"leaks {len(leak_res.data.get('leaks', []))}, "
                       f"drill pack {len(drill_res.data.get('drills', []))}",
            ))
        except Exception as e:
            report.checks.append(CheckResult(
                name="Multi-agent pipeline (review → leaks → drills)",
                passed=False, detail=f"Crashed: {e}",
            ))

        # ── 6) Self-play sanity ────────────────────────────────────
        sp_results = []
        for n in (2, 6, 9):
            try:
                r = self.player.run(num_players=n, hands=2, stack_bb=100.0)
                sp_results.append((n, r.success))
            except Exception as e:
                sp_results.append((n, False))
        all_sp_ok = all(ok for _, ok in sp_results)
        report.checks.append(CheckResult(
            name="Self-play sanity (2/6/9-max)",
            passed=all_sp_ok,
            detail=" ".join(f"{n}m:{'✓' if ok else '✗'}" for n, ok in sp_results),
        ))

        # ── 7) GTOMasterAgent coverage ─────────────────────────────
        master_failures = []
        for cat_sample in random.sample(catalog, min(10, len(catalog))):
            try:
                r = self.master.run(spot=cat_sample, hero_action="fold")
                a = r.data.get("analysis")
                if not (r.success and a and a.recommended and a.leak_warning and a.drill):
                    master_failures.append(cat_sample.get("id"))
            except Exception:
                master_failures.append(cat_sample.get("id"))
        report.checks.append(CheckResult(
            name="GTOMasterAgent produces complete analysis on every sample",
            passed=not master_failures,
            detail=f"{10 - len(master_failures)}/10 spots covered",
            samples=master_failures,
        ))

        # ── final report ───────────────────────────────────────────
        return AgentResult(
            agent   = self.name,
            success = report.all_green,
            summary = (
                f"Audit: {report.passed} passed, {report.failed} failed. "
                f"{'All green ✅' if report.all_green else 'Issues found — see report.'}"
            ),
            data    = {"report": report, "markdown": report.to_markdown()},
        )
