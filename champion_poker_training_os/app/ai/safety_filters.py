from __future__ import annotations

from app.core.rta_guard import RtaGuard


def is_live_strategy_request(prompt: str) -> bool:
    return RtaGuard().should_refuse_live_advice(prompt)


def refusal_message() -> str:
    return (
        "Buna canlı oyun kararı gibi yaklaştığım için cevap veremem. "
        "El bittikten sonra hand history veya manuel offline spot olarak içeri alırsan analiz ederim."
    )

