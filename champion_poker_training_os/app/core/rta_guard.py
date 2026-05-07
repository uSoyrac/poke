from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


POKER_CLIENT_PROCESS_HINTS = (
    "pokerstars",
    "ggpoker",
    "wsop",
    "partypoker",
    "888poker",
    "acr",
    "blackchippoker",
    "wptglobal",
    "winamax",
    "natural8",
    "coinpoker",
)


@dataclass(frozen=True)
class RtaGuardStatus:
    strict_mode: bool
    locked: bool
    detected_processes: tuple[str, ...]

    @property
    def label(self) -> str:
        if self.locked:
            return "STRICT LOCKED"
        return "STRICT ACTIVE" if self.strict_mode else "MONITORING"

    @property
    def message(self) -> str:
        if self.locked:
            processes = ", ".join(self.detected_processes)
            return f"Poker client detected ({processes}). Strategy modules are locked."
        return "Offline-only training mode. No HUD, overlay, live reads or real-time advice."


class RtaGuard:
    def __init__(self, strict_mode: bool = True, hints: Iterable[str] = POKER_CLIENT_PROCESS_HINTS):
        self.strict_mode = strict_mode
        self.hints = tuple(h.lower() for h in hints)

    def scan_processes(self) -> RtaGuardStatus:
        detected: list[str] = []
        try:
            import psutil

            for proc in psutil.process_iter(["name", "cmdline"]):
                info = proc.info
                name = str(info.get("name") or "").lower()
                cmdline = " ".join(str(x) for x in (info.get("cmdline") or [])).lower()
                haystack = f"{name} {cmdline}"
                if any(hint in haystack for hint in self.hints):
                    detected.append(name or "unknown poker client")
        except Exception:
            detected = []

        locked = bool(self.strict_mode and detected)
        return RtaGuardStatus(
            strict_mode=self.strict_mode,
            locked=locked,
            detected_processes=tuple(sorted(set(detected))),
        )

    def should_refuse_live_advice(self, prompt: str) -> bool:
        live_phrases = (
            "şu an elimde",
            "su an elimde",
            "currently holding",
            "live hand",
            "right now i have",
            "masadayım",
            "masadayim",
            "ne yapayım",
            "what should i do now",
        )
        text = prompt.lower()
        return any(phrase in text for phrase in live_phrases)

