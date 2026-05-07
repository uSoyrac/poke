from __future__ import annotations


def leak_report_summary(leaks: list[dict]) -> str:
    total_ev = sum(leak.get("ev_lost", 0) for leak in leaks)
    return f"{len(leaks)} leaks detected, {total_ev:.1f}bb estimated EV lost."

