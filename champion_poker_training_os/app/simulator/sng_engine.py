from __future__ import annotations

from app.simulator.mtt_engine import TournamentEngine


def create_sng_engine() -> TournamentEngine:
    return TournamentEngine(field_size=9, starting_stack=1500, speed="turbo", pko=False)

