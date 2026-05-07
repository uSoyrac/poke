from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AiProviderConfig:
    name: str
    endpoint: str = "offline"
    model: str = "mock-coach"
    enabled: bool = True


def available_providers() -> list[AiProviderConfig]:
    return [
        AiProviderConfig("Offline mock coach"),
        AiProviderConfig("OpenAI API", endpoint="https://api.openai.com", enabled=False),
        AiProviderConfig("Local Ollama", endpoint="http://localhost:11434", enabled=False),
        AiProviderConfig("LM Studio", endpoint="http://localhost:1234", enabled=False),
    ]

