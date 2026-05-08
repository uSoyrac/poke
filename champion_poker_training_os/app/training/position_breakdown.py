"""Pure-Python aggregator: hands per position → win rate + profit. No Qt dep."""
from __future__ import annotations


def compute_position_breakdown_from_rows(imported: list[dict], played: list[dict]) -> list[dict]:
    """Aggregate hands per position into win-rate + profit.

    Imported rows use hero_position + hero_profit_bb. Played rows lack a position
    so they're bucketed under 'Cash'.
    """
    buckets: dict[str, dict[str, float]] = {}
    for h in imported:
        pos = (h.get("hero_position") or "—").upper()
        if pos in ("?", "—", ""):
            continue
        b = buckets.setdefault(pos, {"count": 0, "wins": 0, "profit_bb": 0.0})
        b["count"] += 1
        profit = float(h.get("hero_profit_bb") or 0)
        b["profit_bb"] += profit
        if profit > 0:
            b["wins"] += 1
    for h in played:
        b = buckets.setdefault("Cash", {"count": 0, "wins": 0, "profit_bb": 0.0})
        b["count"] += 1
        profit = float(h.get("hero_profit") or 0)
        b["profit_bb"] += profit
        if h.get("hero_won"):
            b["wins"] += 1

    out = []
    for pos, b in buckets.items():
        if b["count"] == 0:
            continue
        out.append({
            "position": pos,
            "count": int(b["count"]),
            "win_rate": round(100 * b["wins"] / b["count"], 1),
            "profit_bb": round(b["profit_bb"], 2),
        })
    out.sort(key=lambda x: -x["count"])
    return out
