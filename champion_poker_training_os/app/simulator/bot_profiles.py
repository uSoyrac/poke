from __future__ import annotations

from app.db.seed_data import bot_profiles as _seed_bot_profiles


def all_bot_profiles() -> list[dict]:
    return _seed_bot_profiles()


def get_bot_profile(name: str) -> dict:
    for bot in all_bot_profiles():
        if bot["name"] == name:
            return bot
    return all_bot_profiles()[0]

