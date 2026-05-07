from __future__ import annotations

from dataclasses import dataclass, field

from app.db.seed_data import tournament_spots
from app.solver.mock_solver import compare_action


@dataclass
class TournamentEngine:
    field_size: int = 800
    starting_stack: int = 30000
    speed: str = "regular"
    pko: bool = True
    spots: list[dict] = field(default_factory=tournament_spots)
    index: int = 0
    roi_projection: float = 0.0
    icm_punts: int = 0
    finish_position: int = 0

    @property
    def current_spot(self) -> dict:
        return self.spots[self.index % len(self.spots)]

    def decide(self, action: str) -> dict:
        spot = self.current_spot
        result = compare_action(spot, action)
        dollar_ev_loss = round(result["ev_loss"] * (1.0 + spot.get("risk_premium", 0.0) * 5), 2)
        if dollar_ev_loss > 0.7:
            self.icm_punts += 1
        self.roi_projection += 1.8 if result["is_correct"] else -dollar_ev_loss
        self.finish_position = max(1, int(self.field_size / (1 + max(self.roi_projection, -20) / 20)))
        self.index += 1
        return {
            **result,
            "dollar_ev_loss": dollar_ev_loss,
            "risk_premium": spot.get("risk_premium", 0.0),
            "bubble_factor": spot.get("bubble_factor", 1.0),
            "bounty_ev": spot.get("bounty_ev", 0.0),
            "roi_projection": round(self.roi_projection, 2),
            "icm_punts": self.icm_punts,
            "finish_position": self.finish_position,
        }

