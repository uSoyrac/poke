from __future__ import annotations

from dataclasses import dataclass, field

from app.db.seed_data import tournament_spots
from app.solver.mock_solver import compare_action


# Standard blind structure (level, sb, bb, ante in % of bb)
BLIND_LEVELS = [
    (1, 100, 200, 0),
    (2, 150, 300, 30),
    (3, 200, 400, 50),
    (4, 300, 600, 75),
    (5, 400, 800, 100),
    (6, 600, 1200, 150),
    (7, 800, 1600, 200),
    (8, 1200, 2400, 300),
    (9, 1600, 3200, 400),
    (10, 2500, 5000, 600),
    (11, 4000, 8000, 1000),
    (12, 6000, 12000, 1500),
]

PAYOUT_PCT = [
    0.22, 0.15, 0.11, 0.08, 0.06, 0.05, 0.04, 0.03, 0.025, 0.02,
    0.018, 0.015, 0.013, 0.012, 0.010,
]


@dataclass
class TournamentEngine:
    field_size: int = 800
    starting_stack: int = 30000
    speed: str = "regular"
    pko: bool = True
    buyin: float = 100.0
    spots: list[dict] = field(default_factory=tournament_spots)
    index: int = 0
    roi_projection: float = 0.0
    icm_punts: int = 0
    finish_position: int = 0
    chip_stack: int = 30000
    decisions_made: int = 0
    correct_decisions: int = 0
    blind_level: int = 1

    def __post_init__(self) -> None:
        self.chip_stack = self.starting_stack

    @property
    def current_spot(self) -> dict:
        return self.spots[self.index % len(self.spots)]

    @property
    def paid_places(self) -> int:
        return max(2, int(self.field_size * 0.15))

    @property
    def prize_pool(self) -> float:
        return self.buyin * self.field_size * 0.93  # 7% rake

    @property
    def players_left(self) -> int:
        # Project from current spot context, fall back to projection
        spot = self.current_spot
        return spot.get("players_left", max(2, self.field_size - self.index * 30))

    @property
    def avg_stack(self) -> int:
        if self.players_left <= 0:
            return self.chip_stack
        return int(self.field_size * self.starting_stack / self.players_left)

    @property
    def m_ratio(self) -> float:
        sb, bb, ante_pct = self._current_blinds()
        ante = int(bb * ante_pct / 100)
        cost_per_orbit = sb + bb + ante * 9
        if cost_per_orbit <= 0:
            return 0.0
        return round(self.chip_stack / cost_per_orbit, 1)

    @property
    def stack_in_bb(self) -> float:
        _, bb, _ = self._current_blinds()
        return round(self.chip_stack / bb, 1) if bb else 0.0

    def _current_blinds(self) -> tuple[int, int, int]:
        level = min(self.blind_level - 1, len(BLIND_LEVELS) - 1)
        return BLIND_LEVELS[level][1], BLIND_LEVELS[level][2], BLIND_LEVELS[level][3]

    @property
    def blinds_label(self) -> str:
        sb, bb, ante_pct = self._current_blinds()
        return f"L{self.blind_level}  {sb}/{bb} ante {ante_pct}%"

    def payout_for(self, place: int) -> float:
        idx = place - 1
        if idx < 0 or idx >= len(PAYOUT_PCT):
            return 0.0
        return round(self.prize_pool * PAYOUT_PCT[idx], 2)

    def payout_ladder(self) -> list[tuple[int, float]]:
        return [(i + 1, self.payout_for(i + 1)) for i in range(min(8, len(PAYOUT_PCT)))]

    def decide(self, action: str) -> dict:
        spot = self.current_spot
        result = compare_action(spot, action)
        risk = spot.get("risk_premium", 0.0)
        dollar_ev_loss = round(result["ev_loss"] * (1.0 + risk * 5), 2)
        if dollar_ev_loss > 0.7:
            self.icm_punts += 1
        self.decisions_made += 1
        if result["is_correct"]:
            self.correct_decisions += 1
            self.roi_projection += 1.8
            self.chip_stack = int(self.chip_stack * 1.07)
        else:
            self.roi_projection -= dollar_ev_loss
            self.chip_stack = max(0, int(self.chip_stack * (1 - 0.05 - dollar_ev_loss * 0.02)))

        # Advance blind level every ~3 decisions
        self.blind_level = min(len(BLIND_LEVELS), 1 + self.decisions_made // 3)

        # Project finish from running ROI
        denom = 1 + max(self.roi_projection, -20) / 20
        self.finish_position = max(1, int(self.field_size / max(denom, 0.1)))

        self.index += 1
        return {
            **result,
            "dollar_ev_loss": dollar_ev_loss,
            "risk_premium": risk,
            "bubble_factor": spot.get("bubble_factor", 1.0),
            "bounty_ev": spot.get("bounty_ev", 0.0),
            "roi_projection": round(self.roi_projection, 2),
            "icm_punts": self.icm_punts,
            "finish_position": self.finish_position,
            "chip_stack": self.chip_stack,
            "blind_level": self.blind_level,
        }

    def accuracy(self) -> float:
        if self.decisions_made == 0:
            return 0.0
        return round(100 * self.correct_decisions / self.decisions_made, 1)

    def reset(self) -> None:
        self.index = 0
        self.roi_projection = 0.0
        self.icm_punts = 0
        self.finish_position = 0
        self.chip_stack = self.starting_stack
        self.decisions_made = 0
        self.correct_decisions = 0
        self.blind_level = 1
