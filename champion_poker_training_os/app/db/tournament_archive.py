"""Tournament archive — saves past tournament runs to a JSON file
so the user can review history, eliminations and leak summaries.

Stored at: ~/.champion_poker_os/tournament_archive.json
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


_ARCHIVE_DIR  = Path.home() / ".champion_poker_os"
_ARCHIVE_FILE = _ARCHIVE_DIR / "tournament_archive.json"


@dataclass
class HandRecord:
    hand_no:     int
    street:      str
    hero_pos:    str
    hero_cards:  str
    action:      str
    gto_action:  str
    ev_loss:     float
    pot:         float


@dataclass
class TournamentRecord:
    id:                 str
    started_at:         str            # ISO timestamp
    ended_at:           str
    tournament_name:    str
    field_size:         int
    buyin:              float
    starting_stack:     int
    skill_style:        str
    skill_level:        str
    finish_position:    int            # 1 = winner, field_size = first out
    hands_played:       int
    decisions:          int
    correct_decisions:  int
    total_ev_loss:      float
    icm_punts:          int
    cashed:             bool
    payout:             float
    notable_mistakes:   List[dict]     = field(default_factory=list)
    leak_summary:       str            = ""

    @property
    def accuracy(self) -> float:
        if self.decisions == 0:
            return 0.0
        return round(100 * self.correct_decisions / self.decisions, 1)

    @property
    def roi_pct(self) -> float:
        if self.buyin <= 0:
            return 0.0
        return round(100 * (self.payout - self.buyin) / self.buyin, 1)


def _ensure_dir() -> None:
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def load_archive() -> List[TournamentRecord]:
    """Return all stored tournament records, newest first."""
    if not _ARCHIVE_FILE.exists():
        return []
    try:
        raw = json.loads(_ARCHIVE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for entry in raw:
        try:
            out.append(TournamentRecord(**entry))
        except TypeError:
            # Schema drift — skip malformed entries silently rather than crash
            continue
    out.sort(key=lambda r: r.ended_at, reverse=True)
    return out


def save_tournament(record: TournamentRecord) -> None:
    """Append a single tournament result to the archive."""
    _ensure_dir()
    existing = load_archive()
    existing.insert(0, record)
    _ARCHIVE_FILE.write_text(
        json.dumps([asdict(r) for r in existing], indent=2)
    )


def clear_archive() -> None:
    """Wipe all records (used for testing)."""
    if _ARCHIVE_FILE.exists():
        _ARCHIVE_FILE.unlink()


def derive_leak_summary(mistakes: List[dict]) -> str:
    """Quick text summary of the most common leak categories."""
    if not mistakes:
        return "Belirgin leak yok — temiz çıkış."
    buckets: dict[str, int] = {}
    for m in mistakes:
        street = (m.get("street") or "?").title()
        action = (m.get("hero_action") or "?").title()
        key = f"{street} {action}"
        buckets[key] = buckets.get(key, 0) + 1
    top = sorted(buckets.items(), key=lambda x: -x[1])[:3]
    parts = [f"{n}× {k}" for k, n in top]
    return "En sık leak: " + ", ".join(parts)


def new_id() -> str:
    return datetime.now().strftime("MTT-%Y%m%d-%H%M%S")
