"""Base agent classes and result types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    """Uniform return shape from every agent."""
    agent:    str
    success:  bool
    summary:  str
    data:     dict[str, Any] = field(default_factory=dict)
    actions:  list[str]      = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.success


class Agent:
    """Base class — all agents implement `run(**kwargs) -> AgentResult`."""

    name: str = "Agent"

    def run(self, **kwargs) -> AgentResult:  # noqa: D401
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
