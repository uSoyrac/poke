"""My Mistakes queue — every time hero makes a wrong decision the spot is
captured here so the user can drill those spots later.

Stored at: ~/.champion_poker_os/mistakes_queue.json

Schema (per entry):
    {
      "id":           "MIS-2026-05-14-19-22-33",
      "logged_at":    ISO datetime,
      "context":      "tournament" | "spot_trainer" | "play_session" | ...,
      "spot_id":      drill id if any,
      "position":     "BTN",
      "stack_bb":     40,
      "pot_type":     "SRP" | "3BP" | ...,
      "hero_cards":   "TT",
      "hero_action":  "raise",
      "gto_action":   "call",
      "ev_loss":      0.8,
      "why":          "Range advantage favours villain on this texture",
      "drilled":      False,             # has user drilled this leak?
      "drilled_at":   None,
    }
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


_DIR  = Path.home() / ".champion_poker_os"
_FILE = _DIR / "mistakes_queue.json"


@dataclass
class MistakeEntry:
    id:           str
    logged_at:    str
    context:      str
    spot_id:      str        = ""
    position:     str        = ""
    stack_bb:     float      = 0.0
    pot_type:     str        = ""
    hero_cards:   str        = ""
    hero_action:  str        = ""
    gto_action:   str        = ""
    ev_loss:      float      = 0.0
    why:          str        = ""
    drilled:      bool       = False
    drilled_at:   Optional[str] = None

    @property
    def leak_signature(self) -> str:
        """Group similar mistakes — same position+pot type+action class."""
        return f"{self.position} / {self.pot_type or 'SRP'} / {self.hero_action}"


def _ensure() -> None:
    _DIR.mkdir(parents=True, exist_ok=True)


def load_mistakes() -> List[MistakeEntry]:
    if not _FILE.exists():
        return []
    try:
        raw = json.loads(_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for entry in raw:
        try:
            out.append(MistakeEntry(**entry))
        except TypeError:
            continue
    out.sort(key=lambda m: m.logged_at, reverse=True)
    return out


def save_all(entries: List[MistakeEntry]) -> None:
    _ensure()
    _FILE.write_text(json.dumps([asdict(m) for m in entries], indent=2))


def add_mistake(entry: MistakeEntry) -> None:
    """Append a new mistake to the front of the queue (newest first)."""
    items = load_mistakes()
    items.insert(0, entry)
    save_all(items)


def mark_drilled(mistake_id: str) -> None:
    items = load_mistakes()
    now = datetime.now().isoformat(timespec="seconds")
    for m in items:
        if m.id == mistake_id:
            m.drilled = True
            m.drilled_at = now
            break
    save_all(items)


def clear_mistakes() -> None:
    if _FILE.exists():
        _FILE.unlink()


def new_id() -> str:
    return datetime.now().strftime("MIS-%Y%m%d-%H%M%S-%f")[:24]


def grouped_by_leak(entries: List[MistakeEntry]) -> dict[str, List[MistakeEntry]]:
    """Group mistakes by leak_signature for the drill UI."""
    out: dict[str, list[MistakeEntry]] = {}
    for m in entries:
        out.setdefault(m.leak_signature, []).append(m)
    return out
