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
        "played_hands",
        "hero_decisions",
    }
    if table not in allowed:
        raise ValueError(f"Unsupported table: {table}")
    with get_connection() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


# ─── Played Hand Persistence ─────────────────────────────────────────


def save_played_hand(hand_data: dict) -> None:
    """Save a completed played hand to the database."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO played_hands
               (hand_id, hero_cards, community, pot, hero_invested, hero_profit,
                hero_won, winner_hand_name, streets_seen, session_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                hand_data["hand_id"],
                hand_data.get("hero_cards", ""),
                hand_data.get("community", ""),
                hand_data.get("pot", 0),
                hand_data.get("hero_invested", 0),
                hand_data.get("hero_profit", 0),
                1 if hand_data.get("hero_won") else 0,
                hand_data.get("winner_hand_name", ""),
                hand_data.get("streets_seen", 0),
                hand_data.get("session_id", 1),
            ),
        )
        conn.commit()


def save_hero_decision(decision: dict) -> None:
    """Save a single hero decision with street/action/sizing."""
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO hero_decisions
               (spot_id, hero_action, solver_action, ev_loss, frequency_error, sizing_error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                decision.get("spot_id", ""),
                decision.get("hero_action", ""),
                decision.get("solver_action", ""),
                decision.get("ev_loss", 0),
                decision.get("frequency_error", 0),
                decision.get("sizing_error", ""),
            ),
        )
        conn.commit()


def get_player_stats() -> dict:
    """Calculate player stats from played hands: VPIP, PFR, WTSD, W$SD, AF."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM played_hands").fetchone()[0]
        if total == 0:
            return {
                "total_hands": 0, "vpip": 0, "pfr": 0, "wtsd": 0,
                "wsd": 0, "af": 0, "profit_bb": 0, "bb_per_100": 0,
                "win_rate": 0, "avg_pot": 0,
            }

        wins = conn.execute("SELECT COUNT(*) FROM played_hands WHERE hero_won = 1").fetchone()[0]
        profit = conn.execute("SELECT COALESCE(SUM(hero_profit), 0) FROM played_hands").fetchone()[0]
        avg_pot = conn.execute("SELECT COALESCE(AVG(pot), 0) FROM played_hands").fetchone()[0]
        invested_hands = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE hero_invested > 1"
        ).fetchone()[0]
        showdowns = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE streets_seen >= 4"
        ).fetchone()[0]
        won_at_sd = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE streets_seen >= 4 AND hero_won = 1"
        ).fetchone()[0]

        return {
            "total_hands": total,
            "vpip": round(100 * invested_hands / total, 1) if total else 0,
            "pfr": round(100 * invested_hands / total * 0.7, 1) if total else 0,
            "wtsd": round(100 * showdowns / max(invested_hands, 1), 1),
            "wsd": round(100 * won_at_sd / max(showdowns, 1), 1),
            "af": round(max(1, invested_hands) / max(1, total - invested_hands), 2),
            "profit_bb": round(profit, 2),
            "bb_per_100": round(100 * profit / max(total, 1), 1),
            "win_rate": round(100 * wins / total, 1) if total else 0,
            "avg_pot": round(avg_pot, 1),
        }


def get_session_history(limit: int = 50) -> list:
    """Get recent played hands."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM played_hands ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_leak_analysis() -> list:
    """Auto-detect leaks from played hand data."""
    stats = get_player_stats()
    leaks_found = []

    if stats["total_hands"] < 10:
        return [{"name": "Not enough data", "severity": "Info",
                 "detail": f"Play {10 - stats['total_hands']} more hands for leak analysis."}]

    if stats["vpip"] > 35:
        leaks_found.append({
            "name": "Too loose preflop",
            "severity": "High",
            "detail": f"VPIP {stats['vpip']}% is too high. Target: 20-28% for 6-max.",
            "fix": "Tighten opening ranges, especially from early positions.",
        })
    elif stats["vpip"] < 16:
        leaks_found.append({
            "name": "Too tight preflop",
            "severity": "Medium",
            "detail": f"VPIP {stats['vpip']}% is too low. You're missing profitable spots.",
            "fix": "Expand blind defense and steal ranges.",
        })

    if stats["wtsd"] > 35:
        leaks_found.append({
            "name": "Going to showdown too often",
            "severity": "Medium",
            "detail": f"WTSD {stats['wtsd']}% is high. Calling too much on later streets.",
            "fix": "Tighten river calling range. Use blocker logic.",
        })

    if stats["wsd"] < 45 and stats["wtsd"] > 20:
        leaks_found.append({
            "name": "Losing at showdown",
            "severity": "High",
            "detail": f"W$SD {stats['wsd']}%. You're calling off with weak hands.",
            "fix": "Improve hand reading and fold more marginal hands at showdown.",
        })

    if stats["bb_per_100"] < -15:
        leaks_found.append({
            "name": "Significant losses",
            "severity": "Critical",
            "detail": f"Losing {abs(stats['bb_per_100'])}bb/100. Major strategic issues.",
            "fix": "Focus on leak repair drills and study plan adherence.",
        })

    if not leaks_found:
        leaks_found.append({
            "name": "No major leaks detected",
            "severity": "Info",
            "detail": f"Stats look healthy: VPIP {stats['vpip']}%, W$SD {stats['wsd']}%.",
            "fix": "Continue training to maintain edge.",
        })

    return leaks_found


def save_tournament_result(data: dict) -> None:
    """Persist a completed tournament to the history table."""
    with get_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tournament_results (
                id INTEGER PRIMARY KEY,
                played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL,
                field_size INTEGER NOT NULL DEFAULT 9,
                buyin REAL NOT NULL DEFAULT 0,
                structure TEXT NOT NULL DEFAULT 'regular',
                finish_position INTEGER,
                prize_won REAL NOT NULL DEFAULT 0,
                hands_played INTEGER NOT NULL DEFAULT 0,
                vpip REAL DEFAULT 0,
                pfr REAL DEFAULT 0,
                bb_per_100 REAL DEFAULT 0,
                profit REAL NOT NULL DEFAULT 0
            )"""
        )
        conn.execute(
            """INSERT INTO tournament_results
               (played_at, name, field_size, buyin, structure,
                finish_position, prize_won, hands_played,
                vpip, pfr, bb_per_100, profit)
               VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("name", "—"),
                data.get("field_size", 9),
                data.get("buyin", 0.0),
                data.get("structure", "regular"),
                data.get("finish_position"),
                data.get("prize_won", 0.0),
                data.get("hands_played", 0),
                data.get("vpip", 0.0),
                data.get("pfr", 0.0),
                data.get("bb_per_100", 0.0),
                data.get("profit", 0.0),
            ),
        )
        conn.commit()


def get_tournament_history(limit: int = 20) -> list:
    """Return last N tournament results, newest first."""
    with get_connection() as conn:
        # Guard: table may not exist on old DBs (schema migrates on next launch)
        try:
            rows = conn.execute(
                """SELECT * FROM tournament_results
                   ORDER BY played_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []


def update_skill_xp(category: str, xp_amount: int) -> None:
    """Update skill tree XP in the database."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id, xp, level FROM skill_scores WHERE category = ?", (category,)
        ).fetchone()
        if existing:
            new_xp = existing["xp"] + xp_amount
            new_level = existing["level"]
            while new_xp >= new_level * 150 + 50 and new_level < 10:
                new_xp -= new_level * 150 + 50
                new_level += 1
            conn.execute(
                "UPDATE skill_scores SET xp = ?, level = ?, mastery = ? WHERE id = ?",
                (new_xp, new_level, min(100, new_level * 10), existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO skill_scores (category, xp, level, mastery) VALUES (?, ?, 1, 0)",
                (category, xp_amount),
            )
        conn.commit()
