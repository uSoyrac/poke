from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuizState:
    index: int = 0
    correct: int = 0
    answered: int = 0

    def record(self, is_correct: bool) -> None:
        self.answered += 1
        self.correct += int(is_correct)
        self.index += 1

    @property
    def accuracy(self) -> float:
        return 0.0 if self.answered == 0 else self.correct / self.answered

