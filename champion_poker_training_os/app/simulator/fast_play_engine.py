from __future__ import annotations

from dataclasses import dataclass, field

from app.simulator.bot_profiles import all_bot_profiles
from app.simulator.bot_strategy import bot_action
from app.simulator.hand_generator import fast_play_hands
from app.solver.mock_solver import compare_action


@dataclass
class FastPlayEngine:
    mode: str = "Cash 6-max"
    bot_name: str = "Solid reg"
    hands: list[dict] = field(default_factory=lambda: fast_play_hands(60))
    index: int = 0
    hands_played: int = 0
    skill_score: int = 700
    ev_loss: float = 0.0

    @property
    def current_hand(self) -> dict:
        return self.hands[self.index % len(self.hands)]

    @property
    def bot(self) -> dict:
        for profile in all_bot_profiles():
            if profile["name"] == self.bot_name:
                return profile
        return all_bot_profiles()[0]

    def play(self, hero_action: str) -> dict:
        hand = self.current_hand
        comparison = compare_action(hand, hero_action)
        bot_response = bot_action(self.bot, hand_strength=max(0.2, 0.75 - comparison["ev_loss"] * 0.2))
        self.hands_played += 1
        self.index += 1
        self.ev_loss += comparison["ev_loss"]
        delta = 8 if comparison["is_correct"] else -max(3, int(comparison["ev_loss"] * 12))
        self.skill_score = max(100, min(1000, self.skill_score + delta))
        return {
            **comparison,
            "bot_response": bot_response,
            "hands_played": self.hands_played,
            "skill_score": self.skill_score,
            "session_ev_loss": round(self.ev_loss, 2),
        }

    def retry(self) -> None:
        self.index = max(0, self.index - 1)

