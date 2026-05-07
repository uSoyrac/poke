from __future__ import annotations

import json
import sqlite3

from app.core.config import DB_PATH, SCHEMA_PATH
from app.db.seed_data import bot_profiles, combat_packs, generate_hands, generate_spot_drills, knowledge_cards, leaks, study_plan


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            seed_database(conn)


def seed_database(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO users (id, name) VALUES (1, 'Hero')")
    conn.execute("INSERT INTO sessions (id, user_id, format, hands_count) VALUES (1, 1, 'demo mixed', 100)")
    for hand in generate_hands(100):
        conn.execute(
            "INSERT INTO hands (id, session_id, format, hero_cards, board, result_bb, raw_text) VALUES (?, 1, ?, ?, ?, ?, ?)",
            (hand["id"], hand["format"], hand["hero_cards"], hand["board"], hand["result_bb"], "Demo normalized hand history"),
        )
    for drill in generate_spot_drills(120):
        conn.execute(
            "INSERT INTO drills (id, kind, payload_json, source_confidence) VALUES (?, ?, ?, ?)",
            (drill["id"], drill["street"], json.dumps(drill), drill["source_confidence"]),
        )
    for bot in bot_profiles():
        conn.execute(
            "INSERT INTO bot_profiles (name, vpip, pfr, three_bet, fold_to_cbet, aggression, profile_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bot["name"], bot["vpip"], bot["pfr"], bot["three_bet"], bot["fold_to_cbet"], bot["aggression"], json.dumps(bot)),
        )
    for leak in leaks():
        conn.execute(
            "INSERT INTO leaks (name, severity, sample_size, ev_lost, frequency_deviation, fix_strategy) VALUES (?, ?, ?, ?, ?, ?)",
            (leak["name"], leak["severity"], leak["sample_size"], leak["ev_lost"], leak["frequency_deviation"], leak["fix"]),
        )
    for pack in combat_packs():
        conn.execute(
            "INSERT INTO combat_packs (name, spots, difficulty, skill_score, boss_hand) VALUES (?, ?, ?, ?, ?)",
            (pack["name"], pack["spots"], pack["difficulty"], pack["skill_score"], pack["boss_hand"]),
        )
    for card in knowledge_cards():
        conn.execute(
            "INSERT INTO knowledge_cards (concept, source, reference, summary, application) VALUES (?, ?, ?, ?, ?)",
            (card["concept"], card["source"], card["reference"], card["summary"], card["application"]),
        )
    for day in study_plan():
        conn.execute(
            "INSERT INTO study_plans (name, day, focus, blocks_json) VALUES (?, ?, ?, ?)",
            ("7-day world-class repair", day["day"], day["focus"], json.dumps(day["blocks"])),
        )
    conn.execute("INSERT INTO app_settings (key, value) VALUES ('rta_guard_strict', 'true')")
    conn.commit()


def table_count(table: str) -> int:
    allowed = {
        "hands",
        "drills",
        "bot_profiles",
        "leaks",
        "combat_packs",
        "knowledge_cards",
        "study_plans",
    }
    if table not in allowed:
        raise ValueError(f"Unsupported table: {table}")
    with get_connection() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

