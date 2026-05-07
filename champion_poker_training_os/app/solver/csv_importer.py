"""Import real solver outputs (PIO Solver / GTO Wizard CSV) into a SolverLibrary.

Supported formats:
  - PIO 'Tree-builder + EV' aggregate CSV (one row per node, columns include
    spot_id, action, frequency, ev, sizing).
  - GTO Wizard 'Aggregated Reports' CSV (similar columns; we accept a few naming
    variants like 'freq', 'frequency_pct', 'pct').

Once imported the library can be queried by spot id; otherwise falls back to
mock_solver. This is a deliberate pluggable design: the trainers don't care
where solver data comes from, only that they get a SolverResult.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from app.solver.solver_schema import SolverAction, SolverResult


# Canonical column names → list of possible source aliases (lowercased).
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "spot_id": ("spot_id", "spotid", "node_id", "id", "spot"),
    "action": ("action", "action_name", "decision", "move"),
    "frequency": ("frequency", "freq", "frequency_pct", "pct", "weight", "%"),
    "ev": ("ev", "expected_value", "ev_bb", "value"),
    "sizing": ("sizing", "size", "sizing_label", "amount"),
    "best": ("best", "is_best", "best_action"),
    "source": ("source", "source_confidence", "engine"),
}


def _normalize_header(header: str) -> Optional[str]:
    h = header.strip().lower().replace(" ", "_")
    for canonical, aliases in COLUMN_ALIASES.items():
        if h in aliases:
            return canonical
    return None


def _to_float(v: str) -> float:
    if v is None:
        return 0.0
    s = str(v).strip().replace("%", "").replace(",", "")
    if not s:
        return 0.0
    try:
        f = float(s)
    except ValueError:
        return 0.0
    return f


def parse_solver_csv(text: str, default_source: str = "Imported PIO/GTO CSV") -> dict[str, SolverResult]:
    """Parse a CSV (text) into {spot_id: SolverResult}.

    Frequencies are auto-normalised to sum to 1.0 per spot. If a 'best' column
    exists it is honoured; otherwise the highest-EV action is marked best.
    """
    if not text or not text.strip():
        return {}
    reader = csv.reader(io.StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return {}
    columns = [_normalize_header(h) for h in raw_header]
    if "spot_id" not in columns or "action" not in columns:
        return {}
    idx = {col: columns.index(col) for col in COLUMN_ALIASES if col in columns}

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in reader:
        if not row or len(row) < 2:
            continue
        try:
            spot_id = (row[idx["spot_id"]] or "").strip()
            action = (row[idx["action"]] or "").strip().lower()
        except (KeyError, IndexError):
            continue
        if not spot_id or not action:
            continue
        freq = _to_float(row[idx["frequency"]]) if "frequency" in idx else 0.0
        # Heuristic: if values look like percentages (>1.5 typical), divide by 100
        if freq > 1.5:
            freq /= 100.0
        ev = _to_float(row[idx["ev"]]) if "ev" in idx else 0.0
        sizing = (row[idx["sizing"]] if "sizing" in idx and idx["sizing"] < len(row) else "").strip()
        best_flag = False
        if "best" in idx and idx["best"] < len(row):
            best_flag = (row[idx["best"]] or "").strip().lower() in {"1", "true", "yes", "best"}
        source = (
            row[idx["source"]].strip() if "source" in idx and idx["source"] < len(row)
            else default_source
        )
        grouped[spot_id].append({
            "action": action,
            "frequency": max(0.0, freq),
            "ev": ev,
            "sizing": sizing,
            "best": best_flag,
            "source": source or default_source,
        })

    results: dict[str, SolverResult] = {}
    for spot_id, rows in grouped.items():
        total_freq = sum(r["frequency"] for r in rows) or 1.0
        normalized = []
        for r in rows:
            normalized.append(SolverAction(
                action=r["action"],
                frequency=round(r["frequency"] / total_freq, 4),
                ev=round(r["ev"], 4),
                sizing=r["sizing"],
            ))
        # Choose 'best' — explicit flag wins, else highest EV
        explicit_best = next((r["action"] for r in rows if r["best"]), None)
        if explicit_best:
            best = explicit_best
        else:
            best = max(rows, key=lambda r: r["ev"])["action"]
        source = rows[0]["source"]
        results[spot_id] = SolverResult(
            spot_id=spot_id,
            best_action=best,
            actions=tuple(normalized),
            source_confidence=source,
            range_advantage="Per imported CSV — see source for details.",
            nut_advantage="Per imported CSV — see source for details.",
            explanation=f"Imported solver row from {source}.",
        )
    return results


# ─── Singleton library ─────────────────────────────────────────────────────


class SolverLibrary:
    """In-memory cache of imported SolverResults, keyed by spot_id."""

    def __init__(self) -> None:
        self._results: dict[str, SolverResult] = {}
        self._sources: list[str] = []

    def import_csv_text(self, text: str, source_name: str = "Imported CSV") -> int:
        parsed = parse_solver_csv(text, default_source=source_name)
        self._results.update(parsed)
        if source_name not in self._sources and parsed:
            self._sources.append(source_name)
        return len(parsed)

    def import_csv_file(self, path: str | Path) -> int:
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        return self.import_csv_text(text, source_name=p.name)

    def get(self, spot_id: str) -> Optional[SolverResult]:
        return self._results.get(spot_id)

    def has(self, spot_id: str) -> bool:
        return spot_id in self._results

    def size(self) -> int:
        return len(self._results)

    def sources(self) -> list[str]:
        return list(self._sources)

    def clear(self) -> None:
        self._results.clear()
        self._sources.clear()


_library: Optional[SolverLibrary] = None


def get_solver_library() -> SolverLibrary:
    global _library
    if _library is None:
        _library = SolverLibrary()
    return _library
