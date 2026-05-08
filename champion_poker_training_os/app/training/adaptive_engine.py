"""Adaptive drill engine — spaced repetition + mistake-priority queue.

Tracks per-spot performance: timestamp of last review, current SR interval,
streak of correct answers, last EV loss, last accuracy. Selects the next drill
by combining:
  - Due-for-review spots (interval expired)
  - High-EV-loss mistakes (queued at top, decayed by recency)
  - Spaced-repetition fresh material (filling remaining slots)

The engine itself is pure Python (no Qt) for easy testing. UI screens (Spot
Trainer, Drill Builder) call `record_attempt(spot_id, ev_loss, correct)` and
`next_drill()` to get the recommended spot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Optional


# SM-2-style intervals (days). Mistakes always reset to interval index 0.
SR_INTERVALS_DAYS = [0, 1, 3, 7, 14, 30, 60, 90]
SECONDS_PER_DAY = 86_400


@dataclass
class SpotState:
    """Per-spot training history. EV loss is the worst recent miss."""
    spot_id: str
    last_attempt_ts: float = 0.0
    next_due_ts: float = 0.0
    interval_idx: int = 0
    correct_streak: int = 0
    total_attempts: int = 0
    total_correct: int = 0
    last_ev_loss: float = 0.0
    rolling_ev_loss: float = 0.0   # EWMA, weights more recent misses
    tags: tuple[str, ...] = ()

    @property
    def accuracy(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.total_correct / self.total_attempts

    def is_due(self, now: float) -> bool:
        return self.next_due_ts <= now

    def record(self, correct: bool, ev_loss: float, now: float) -> None:
        self.total_attempts += 1
        self.last_attempt_ts = now
        self.last_ev_loss = max(0.0, ev_loss)
        # EWMA with alpha=0.6 — recent misses dominate
        self.rolling_ev_loss = 0.4 * self.rolling_ev_loss + 0.6 * self.last_ev_loss
        if correct:
            self.total_correct += 1
            self.correct_streak += 1
            self.interval_idx = min(len(SR_INTERVALS_DAYS) - 1, self.interval_idx + 1)
        else:
            self.correct_streak = 0
            # Demote: drop two slots on miss, never below 0 (re-show tomorrow at most)
            self.interval_idx = max(0, self.interval_idx - 2)
        days = SR_INTERVALS_DAYS[self.interval_idx]
        self.next_due_ts = now + days * SECONDS_PER_DAY


@dataclass
class AdaptiveEngine:
    """Tracks spot states and produces a prioritized queue of next drills."""

    spots: dict[str, SpotState] = field(default_factory=dict)
    mistake_queue: list[str] = field(default_factory=list)  # ordered by priority
    _now: Optional[float] = None  # injected for tests

    def now(self) -> float:
        return self._now if self._now is not None else time.time()

    # --- intake ----------------------------------------------------------
    def register(self, spot_id: str, tags: Iterable[str] = ()) -> SpotState:
        state = self.spots.get(spot_id)
        if state is None:
            state = SpotState(spot_id=spot_id, tags=tuple(tags))
            self.spots[spot_id] = state
        return state

    def record_attempt(self, spot_id: str, correct: bool, ev_loss: float = 0.0,
                        tags: Iterable[str] = ()) -> SpotState:
        state = self.register(spot_id, tags)
        state.record(correct, ev_loss, self.now())
        # Mistake queue maintenance: push high-EV losses, drop on success
        if not correct and ev_loss > 0.3:
            if spot_id in self.mistake_queue:
                self.mistake_queue.remove(spot_id)
            self.mistake_queue.insert(0, spot_id)
            # Cap queue size
            self.mistake_queue = self.mistake_queue[:50]
        elif correct and state.correct_streak >= 2 and spot_id in self.mistake_queue:
            self.mistake_queue.remove(spot_id)
        return state

    # --- selection -------------------------------------------------------
    def next_drill(self, candidates: list[str], exclude: Iterable[str] = ()) -> Optional[str]:
        """Pick the best next spot from `candidates`.

        Priority:
          1) Top of mistake queue if its spot is in candidates
          2) Due-for-review spots, ranked by score(state)
          3) Highest-priority unseen spot from candidates
        """
        excluded = set(exclude)
        candidate_set = set(candidates)

        # 1) Mistake queue
        for sid in self.mistake_queue:
            if sid in candidate_set and sid not in excluded:
                return sid

        # 2) Due reviews
        now = self.now()
        due = [
            (self._priority(self.spots[sid]), sid)
            for sid in candidates
            if sid in self.spots and sid not in excluded and self.spots[sid].is_due(now)
        ]
        if due:
            due.sort(reverse=True)
            return due[0][1]

        # 3) Unseen
        unseen = [sid for sid in candidates if sid not in self.spots and sid not in excluded]
        if unseen:
            return unseen[0]

        # 4) Anything else not excluded
        remaining = [sid for sid in candidates if sid not in excluded]
        return remaining[0] if remaining else None

    def queue_size(self) -> dict[str, int]:
        now = self.now()
        return {
            "tracked": len(self.spots),
            "mistakes_pending": len(self.mistake_queue),
            "due_for_review": sum(1 for s in self.spots.values() if s.is_due(now)),
        }

    def weakness_summary(self, top_n: int = 5) -> list[dict]:
        """Return the spots with worst rolling EV loss + lowest accuracy."""
        scored = sorted(
            self.spots.values(),
            key=lambda s: (-s.rolling_ev_loss, s.accuracy),
        )
        out = []
        for s in scored[:top_n]:
            if s.total_attempts == 0:
                continue
            out.append({
                "spot_id": s.spot_id,
                "attempts": s.total_attempts,
                "accuracy": round(100 * s.accuracy, 1),
                "last_ev_loss": round(s.last_ev_loss, 2),
                "rolling_ev_loss": round(s.rolling_ev_loss, 2),
                "streak": s.correct_streak,
                "tags": list(s.tags),
            })
        return out

    @staticmethod
    def _priority(state: SpotState) -> float:
        """Higher = surface this spot sooner. Combines EV loss + lateness + low acc."""
        miss_weight = state.rolling_ev_loss * 4.0
        accuracy_penalty = (1.0 - state.accuracy) * 2.0
        # Older intervals = lower urgency (well-mastered material), shorter = high
        interval_penalty = -state.interval_idx * 0.5
        return miss_weight + accuracy_penalty + interval_penalty

    # --- persistence ----------------------------------------------------
    def to_dicts(self) -> tuple[list[dict], list[str]]:
        """Snapshot the engine into JSON-friendly dicts for DB persistence."""
        spots = []
        for s in self.spots.values():
            spots.append({
                "spot_id": s.spot_id,
                "last_attempt_ts": s.last_attempt_ts,
                "next_due_ts": s.next_due_ts,
                "interval_idx": s.interval_idx,
                "correct_streak": s.correct_streak,
                "total_attempts": s.total_attempts,
                "total_correct": s.total_correct,
                "last_ev_loss": s.last_ev_loss,
                "rolling_ev_loss": s.rolling_ev_loss,
                "tags": list(s.tags),
            })
        return spots, list(self.mistake_queue)

    def load_from_dicts(self, spots: list[dict], mistake_queue: list[str]) -> None:
        """Hydrate the engine from previously-saved dicts."""
        self.spots = {}
        for d in spots:
            self.spots[d["spot_id"]] = SpotState(
                spot_id=d["spot_id"],
                last_attempt_ts=d.get("last_attempt_ts", 0),
                next_due_ts=d.get("next_due_ts", 0),
                interval_idx=d.get("interval_idx", 0),
                correct_streak=d.get("correct_streak", 0),
                total_attempts=d.get("total_attempts", 0),
                total_correct=d.get("total_correct", 0),
                last_ev_loss=d.get("last_ev_loss", 0),
                rolling_ev_loss=d.get("rolling_ev_loss", 0),
                tags=tuple(d.get("tags", [])),
            )
        self.mistake_queue = list(mistake_queue)

    def save_to_db(self) -> int:
        """Persist current state to the DB. Returns number of spot rows written."""
        from app.db.repository import save_adaptive_state
        spots, queue = self.to_dicts()
        return save_adaptive_state(spots, queue)

    def load_from_db(self) -> int:
        """Populate from DB (called once on app start). Returns spots loaded."""
        from app.db.repository import load_adaptive_state
        snap = load_adaptive_state()
        self.load_from_dicts(snap["spots"], snap["mistake_queue"])
        return len(snap["spots"])
