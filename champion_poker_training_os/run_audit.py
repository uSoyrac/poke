#!/usr/bin/env python3
"""Run the full end-to-end audit (logic + UI) and print a markdown report.

Usage:
    python3 run_audit.py
    python3 run_audit.py > AUDIT_REPORT.md

This is the "master poker user assistant" the project asks for — it boots
every screen, exercises every interaction, and reports what a real user
would notice.  Run it before every release.
"""
from __future__ import annotations

import sys


def main() -> int:
    print("═" * 72)
    print("  CHAMPION POKER TRAINING OS — Master Audit")
    print("═" * 72)
    print()

    # 1) Logic-level audit (no Qt needed)
    print("─── 1/2  Logic Audit (MasterAuditorAgent) ───")
    from app.agents import MasterAuditorAgent
    logic = MasterAuditorAgent().run()
    print(logic.data["markdown"])
    print()

    # 2) UI-level audit (PySide6 required, falls back to clear error)
    print("─── 2/2  UI Simulation (UISimulationAgent) ───")
    from app.agents import UISimulationAgent
    ui = UISimulationAgent().run_full_audit()
    print(ui.to_markdown())
    print()

    # Final verdict
    logic_ok = logic.data["report"].all_green
    ui_ok    = ui.all_green
    print("═" * 72)
    if logic_ok and ui_ok:
        print("  ✅  ALL AUDITS GREEN — system is in a release-ready state.")
    else:
        print(f"  ⚠️  Issues found: logic={logic.data['report'].failed} blockers"
              f" / ui={len(ui.blockers)} blockers")
    print("═" * 72)
    return 0 if (logic_ok and ui_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
