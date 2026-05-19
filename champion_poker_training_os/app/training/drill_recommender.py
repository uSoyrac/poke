"""Drill recommendation engine — turn the user's leak fingerprint into a
focused, EV-weighted drill pack.

Pipeline:

    mistakes (list[MistakeEntry])
        │
        │  group by leak_signature ("BTN / SRP / call", etc.)
        ▼
    leak buckets, ranked by Σ EV-loss
        │
        │  for each bucket, pull matching spots via
        │  `filter_spots_by_signature` (Tier 1 = tight stack-bucket match,
        │   Tier 2 = position+pot_type, Tier 3 = position only)
        ▼
    ordered spot list (max_size)

Returns a serialisable dict that is compatible with
`app.db.repository.save_drill_pack`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:                                # pragma: no cover
    from app.db.mistakes_queue import MistakeEntry


def _bucket_mistakes(mistakes: List["MistakeEntry"]) -> list[dict]:
    """Group mistakes by leak_signature → sorted by total EV-loss."""
    by_sig: dict[str, list["MistakeEntry"]] = defaultdict(list)
    for m in mistakes:
        # Skip noise — already-drilled mistakes shouldn't pull spots again.
        if getattr(m, "drilled", False):
            continue
        by_sig[m.leak_signature].append(m)
    buckets = []
    for sig, items in by_sig.items():
        total_ev = sum(abs(float(m.ev_loss or 0)) for m in items)
        avg_stack = (
            sum(float(m.stack_bb or 0) for m in items) / max(len(items), 1)
        )
        buckets.append({
            "signature":   sig,
            "count":       len(items),
            "total_ev":    round(total_ev, 2),
            "avg_stack":   avg_stack,
            "sample_ids":  [m.id for m in items[:5]],
        })
    buckets.sort(key=lambda b: b["total_ev"], reverse=True)
    return buckets


def pack_from_leaks(
    mistakes: List["MistakeEntry"],
    spots: List[dict],
    *,
    max_size: int = 10,
    pack_name: Optional[str] = None,
) -> dict:
    """Build a drill pack from the user's open mistakes.

    Returns a dict shaped like ``{name, positions, solution, starting_spot,
    preflop_action, notes}`` so it can be persisted directly via
    `save_drill_pack`. The `positions` field stores the ordered spot IDs.

    `notes` carries a human-readable summary of which leaks the pack
    targets and how many EV-bb each contributes.
    """
    from app.db.mistakes_queue import filter_spots_by_signature

    buckets = _bucket_mistakes(mistakes)
    if not buckets:
        return {
            "name": pack_name or "No-op drill pack",
            "positions": [],
            "solution": "",
            "starting_spot": "",
            "preflop_action": "",
            "notes": "No open mistakes — nothing to drill. Play more hands "
                     "or run the Spot Practice Trainer to log mistakes first.",
        }

    ordered_ids: list[str] = []
    seen: set[str] = set()
    targeted_leaks: list[str] = []

    # Allocate slots: top-EV bucket gets a bigger share, then we round-robin.
    weights = [b["total_ev"] for b in buckets]
    total_weight = sum(weights) or 1.0
    quotas = [
        max(1, int(round((w / total_weight) * max_size)))
        for w in weights
    ]
    # Trim quotas down to max_size in case rounding overshoots
    over = sum(quotas) - max_size
    for i in range(len(quotas)):
        if over <= 0:
            break
        if quotas[i] > 1:
            take = min(over, quotas[i] - 1)
            quotas[i] -= take
            over -= take

    for bucket, quota in zip(buckets, quotas):
        if quota <= 0:
            continue
        matching = filter_spots_by_signature(
            bucket["signature"], spots, stack_bb=bucket["avg_stack"] or None,
        )
        picked = 0
        for spot in matching:
            sid = spot.get("id") or spot.get("spot_id")
            if not sid or sid in seen:
                continue
            ordered_ids.append(sid)
            seen.add(sid)
            picked += 1
            if picked >= quota:
                break
        if picked > 0:
            targeted_leaks.append(
                f"{bucket['signature']} (-{bucket['total_ev']:.1f}bb · "
                f"{bucket['count']} mistakes)"
            )
        if len(ordered_ids) >= max_size:
            break

    ordered_ids = ordered_ids[:max_size]

    notes = (
        f"Drill pack auto-generated from {sum(b['count'] for b in buckets)} "
        f"open mistakes across {len(buckets)} leak signatures.\n\n"
        "Targeted leaks (ranked by EV loss):\n"
        + "\n".join(f"  • {t}" for t in targeted_leaks)
        + f"\n\nPack size: {len(ordered_ids)} spots."
    )
    starting_id = ordered_ids[0] if ordered_ids else ""
    return {
        "name": pack_name or (
            "Leak repair · "
            + datetime.now().strftime("%Y-%m-%d %H:%M")
        ),
        "positions": ordered_ids,
        "solution": "",
        "starting_spot": starting_id,
        "preflop_action": "",
        "notes": notes,
    }


def queue_pack_in_state(pack: dict, state) -> int:
    """Push the pack's spot IDs into AppState.pending_spot_queue so the
    Spot Practice Trainer pops them on each load. Returns the queued count.
    """
    positions = list(pack.get("positions") or [])
    if not positions:
        return 0
    # Replace (not append) so the user gets a clean focused run.
    state.pending_spot_queue = list(positions)
    state.pending_spot_id = positions[0]
    return len(positions)
