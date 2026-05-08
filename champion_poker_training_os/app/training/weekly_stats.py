"""Pure-Python (no Qt) weekly stats collector.

Reads played_hands and adaptive_spots from the SQLite DB and rolls them up
into a 7-day window for dashboard charts and reports.
"""
from __future__ import annotations

import datetime as dt
from typing import Any


def collect_weekly_stats() -> list[dict[str, Any]]:
    """Return one dict per day for the last 7 days.

    Keys: date (datetime.date), label (e.g. 'Mon'), drills, hands, profit_bb, accuracy.
    Falls back to all-zero rows when DB is empty or unreachable.
    """
    today = dt.date.today()
    days: list[dict[str, Any]] = []
    for i in range(6, -1, -1):
        d = today - dt.timedelta(days=i)
        days.append({
            "date": d,
            "label": d.strftime("%a"),
            "drills": 0,
            "hands": 0,
            "profit_bb": 0.0,
            "accuracy": 0.0,
        })

    try:
        from app.db.repository import get_connection
        with get_connection() as conn:
            try:
                hand_rows = conn.execute(
                    "SELECT DATE(created_at) AS d, COUNT(*) AS n, "
                    "COALESCE(SUM(hero_profit), 0) AS p "
                    "FROM played_hands GROUP BY DATE(created_at)"
                ).fetchall()
                for r in hand_rows:
                    rd = r["d"]
                    if not rd:
                        continue
                    try:
                        date = dt.date.fromisoformat(rd[:10])
                    except Exception:
                        continue
                    for day in days:
                        if day["date"] == date:
                            day["hands"] = int(r["n"] or 0)
                            day["profit_bb"] = float(r["p"] or 0)
            except Exception:
                pass
            try:
                drill_rows = conn.execute(
                    "SELECT DATE(updated_at) AS d, "
                    "COUNT(*) AS n, "
                    "SUM(total_correct) AS c, "
                    "SUM(total_attempts) AS t "
                    "FROM adaptive_spots GROUP BY DATE(updated_at)"
                ).fetchall()
                for r in drill_rows:
                    rd = r["d"]
                    if not rd:
                        continue
                    try:
                        date = dt.date.fromisoformat(rd[:10])
                    except Exception:
                        continue
                    for day in days:
                        if day["date"] == date:
                            day["drills"] = int(r["n"] or 0)
                            attempts = int(r["t"] or 0)
                            correct = int(r["c"] or 0)
                            day["accuracy"] = (
                                round(100 * correct / attempts, 1) if attempts else 0.0
                            )
            except Exception:
                pass
    except Exception:
        pass
    return days
