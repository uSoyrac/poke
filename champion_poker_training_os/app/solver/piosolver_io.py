"""PioSolver-compatible range export / import.

PioSolver and many of its clones (MonkerSolver, GTO+, Wizard) read/write
ranges in two common shapes:

  JSON (one chart per file):
    {
      "spot":   "BTN-RFI-40",
      "pot_bb": 1.5,
      "stack_bb": 40,
      "actions": ["raise", "fold"],
      "hands": {
        "AA":  {"raise": 1.0,  "fold": 0.0},
        "AKs": {"raise": 1.0,  "fold": 0.0},
        "ATo": {"raise": 0.6,  "fold": 0.4},
        ...
      }
    }

  CSV (Pio-style):
    Hand,raise,call,fold
    AA,1.0,0.0,0.0
    AKs,1.0,0.0,0.0
    ATo,0.6,0.0,0.4
    ...

This module provides:
  • export_chart_json(key, path)
  • export_chart_csv(key, path)
  • import_chart_json(path) -> dict
  • import_chart_csv(path) -> dict
  • register_chart(key, chart) — install at runtime
  • bulk_export_all(directory) — dump every chart in CHARTS
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from app.solver.preflop_charts import CHARTS, _HANDS


def _action_list_from_chart(chart: dict[str, dict[str, float]]) -> list[str]:
    """Collect every unique action verb across all hands in a chart."""
    seen: set[str] = set()
    for hand_strat in chart.values():
        for act in hand_strat:
            seen.add(act)
    # Stable order: raise > 3bet > 4bet > call > check > fold > jam
    order = ["raise", "3bet", "4bet", "bet", "call", "check", "fold", "jam", "allin"]
    head = [a for a in order if a in seen]
    tail = sorted(seen - set(head))
    return head + tail


# ── EXPORT ────────────────────────────────────────────────────────────────

def export_chart_json(
    key: str,
    out_path: str | Path,
    pot_bb: float = 1.5,
    stack_bb: int = 40,
) -> Path:
    """Write a single chart as PioSolver-style JSON."""
    chart = CHARTS.get(key)
    if not chart:
        raise KeyError(f"No chart for key {key!r}")
    payload = {
        "spot":     key,
        "pot_bb":   pot_bb,
        "stack_bb": stack_bb,
        "actions":  _action_list_from_chart(chart),
        "hands": {
            h: {a: round(f, 4) for a, f in strat.items() if f > 0}
            for h, strat in chart.items()
        },
    }
    out = Path(out_path)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def export_chart_csv(key: str, out_path: str | Path) -> Path:
    """Write a chart as PioSolver-style CSV (header row + per-hand row)."""
    chart = CHARTS.get(key)
    if not chart:
        raise KeyError(f"No chart for key {key!r}")
    actions = _action_list_from_chart(chart)
    out = Path(out_path)
    with out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Hand"] + actions)
        for h in _HANDS:
            strat = chart.get(h, {})
            row = [h] + [f"{strat.get(a, 0.0):.4f}" for a in actions]
            writer.writerow(row)
    return out


def bulk_export_all(directory: str | Path, fmt: str = "json") -> list[Path]:
    """Dump every chart into a directory. Returns list of written paths."""
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)
    exporter = export_chart_json if fmt == "json" else export_chart_csv
    written = []
    for key in CHARTS:
        path = out_dir / f"{key}.{fmt}"
        written.append(exporter(key, path))
    return written


# ── IMPORT ────────────────────────────────────────────────────────────────

def import_chart_json(in_path: str | Path) -> dict[str, dict[str, float]]:
    """Read a PioSolver-style JSON file. Returns the hands dict.

    Tolerant to:
      • files with or without the wrapping {"spot": ..., "hands": {...}}
      • frequencies that don't sum to 1.0 (normalises)
      • missing hands (filled in as 'fold' 1.0 by `_pad`)
    """
    raw = json.loads(Path(in_path).read_text())
    if isinstance(raw, dict) and "hands" in raw:
        hands = raw["hands"]
    else:
        hands = raw  # raw hand-strategy map
    return _normalise_chart(hands)


def import_chart_csv(in_path: str | Path) -> dict[str, dict[str, float]]:
    """Read a PioSolver-style CSV. First row must be 'Hand,act1,act2,...'."""
    out: dict[str, dict[str, float]] = {}
    with Path(in_path).open() as f:
        reader = csv.reader(f)
        header = next(reader)
        actions = header[1:]
        for row in reader:
            if not row:
                continue
            hand = row[0].strip()
            strat = {}
            for i, act in enumerate(actions):
                try:
                    v = float(row[i + 1])
                except (IndexError, ValueError):
                    v = 0.0
                if v > 0:
                    strat[act] = v
            out[hand] = strat
    return _normalise_chart(out)


def _normalise_chart(
    hands: dict,
) -> dict[str, dict[str, float]]:
    """Fill in missing hands (assume fold), normalise frequencies to sum=1.0."""
    out: dict[str, dict[str, float]] = {}
    for h in _HANDS:
        strat = hands.get(h)
        if not strat:
            out[h] = {"fold": 1.0}
            continue
        # Coerce to floats and drop non-positive
        cleaned = {k: float(v) for k, v in strat.items() if float(v) > 0}
        if not cleaned:
            out[h] = {"fold": 1.0}
            continue
        total = sum(cleaned.values())
        if total > 0 and abs(total - 1.0) > 0.001:
            cleaned = {k: v / total for k, v in cleaned.items()}
        out[h] = cleaned
    return out


def register_chart(key: str, chart: dict[str, dict[str, float]]) -> None:
    """Install an imported chart into the global CHARTS map at runtime."""
    CHARTS[key] = chart


def import_and_register(in_path: str | Path, key: Optional[str] = None) -> str:
    """Import a chart file and register it under `key` (or filename stem)."""
    in_path = Path(in_path)
    chart = (import_chart_csv(in_path) if in_path.suffix.lower() == ".csv"
             else import_chart_json(in_path))
    register_chart(key or in_path.stem, chart)
    return key or in_path.stem
