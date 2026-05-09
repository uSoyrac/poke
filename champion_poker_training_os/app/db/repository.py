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
        "decision_reviews",
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


def save_decision_review(review: dict) -> int:
    """Persist one post-decision GTO/exploit review row."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO decision_reviews
               (hand_id, spot_id, street, position, hero_cards, board, pot_bb,
                hero_action, solver_action, hero_ev, best_ev, ev_loss,
                solver_frequency, best_frequency, is_correct, verdict, severity,
                sizing_feedback, exploit_note, drill_target, source_confidence,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                review.get("hand_id", 0),
                review.get("spot_id", ""),
                review.get("street", ""),
                review.get("position", ""),
                review.get("hero_cards", ""),
                review.get("board", ""),
                review.get("pot_bb", 0.0),
                review.get("hero_action", ""),
                review.get("solver_action", ""),
                review.get("hero_ev", 0.0),
                review.get("best_ev", 0.0),
                review.get("ev_loss", 0.0),
                review.get("solver_frequency", 0.0),
                review.get("best_frequency", 0.0),
                1 if review.get("is_correct") else 0,
                review.get("verdict", ""),
                review.get("severity", ""),
                review.get("sizing_feedback", ""),
                review.get("exploit_note", ""),
                review.get("drill_target", ""),
                review.get("source_confidence", "Rule-based heuristic"),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_decision_reviews(hand_id: int | None = None, limit: int = 200) -> list[dict]:
    """Return recent persisted GTO/exploit decision reviews."""
    with get_connection() as conn:
        try:
            if hand_id is None:
                rows = conn.execute(
                    "SELECT * FROM decision_reviews ORDER BY created_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM decision_reviews WHERE hand_id=? ORDER BY id",
                    (hand_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
    out = [dict(row) for row in rows]
    for row in out:
        row["is_correct"] = bool(row.get("is_correct"))
    return out


def get_decision_review_summary(limit: int = 500) -> dict:
    """Aggregate decision correctness, EV loss and worst spots."""
    reviews = get_decision_reviews(limit=limit)
    if not reviews:
        return {
            "count": 0,
            "correct": 0,
            "mistakes": 0,
            "accuracy": 0.0,
            "ev_loss": 0.0,
            "worst": [],
        }
    correct = sum(1 for row in reviews if row.get("is_correct"))
    ev_loss = round(sum(float(row.get("ev_loss") or 0.0) for row in reviews), 2)
    worst = sorted(reviews, key=lambda row: float(row.get("ev_loss") or 0.0), reverse=True)[:10]
    return {
        "count": len(reviews),
        "correct": correct,
        "mistakes": len(reviews) - correct,
        "accuracy": round(100 * correct / len(reviews), 1),
        "ev_loss": ev_loss,
        "worst": worst,
    }


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


# ─── Imported Hands (PokerStars / GG) ────────────────────────────────


def save_imported_hand(hand: dict) -> int:
    """Insert (or replace) one parsed hand and return its row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT OR REPLACE INTO imported_hands
               (external_id, site, format, date, hero_position, hero_cards, board,
                pot_bb, hero_profit_bb, ev_loss, pot_type,
                preflop_actions, flop_actions, turn_actions, river_actions,
                status, raw_text, imported_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                hand.get("external_id"),
                hand.get("site"),
                hand.get("format"),
                hand.get("date"),
                hand.get("hero_position"),
                hand.get("hero_cards"),
                hand.get("board"),
                hand.get("pot_bb", 0.0),
                hand.get("hero_profit_bb", 0.0),
                hand.get("ev_loss", 0.0),
                hand.get("pot_type"),
                hand.get("preflop_actions", ""),
                hand.get("flop_actions", ""),
                hand.get("turn_actions", ""),
                hand.get("river_actions", ""),
                hand.get("status", "review"),
                hand.get("raw_text", ""),
            ),
        )
        conn.commit()
        return cursor.lastrowid


def save_imported_hands(hands: list[dict]) -> int:
    """Bulk-save parsed hands. Returns number persisted."""
    saved = 0
    for hand in hands:
        try:
            save_imported_hand(hand)
            saved += 1
        except Exception:
            continue
    return saved


def get_imported_hands(limit: int = 200) -> list[dict]:
    """Return imported hands ordered newest first."""
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT * FROM imported_hands ORDER BY imported_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]


# ─── User Drill Packs ────────────────────────────────────────────────


def save_drill_pack(pack: dict) -> int:
    """Insert (or update if id given) a user-saved drill pack. Returns row id."""
    with get_connection() as conn:
        try:
            if pack.get("id"):
                conn.execute(
                    """UPDATE user_drill_packs SET name=?, positions_json=?, solution=?,
                       starting_spot=?, preflop_action=?, notes=?, updated_at=datetime('now')
                       WHERE id=?""",
                    (
                        pack.get("name", "Untitled"),
                        json.dumps(list(pack.get("positions", []))),
                        pack.get("solution", ""),
                        pack.get("starting_spot", ""),
                        pack.get("preflop_action", ""),
                        pack.get("notes", ""),
                        pack["id"],
                    ),
                )
                conn.commit()
                return int(pack["id"])
            cur = conn.execute(
                """INSERT INTO user_drill_packs
                   (name, positions_json, solution, starting_spot, preflop_action, notes,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
                (
                    pack.get("name", "Untitled"),
                    json.dumps(list(pack.get("positions", []))),
                    pack.get("solution", ""),
                    pack.get("starting_spot", ""),
                    pack.get("preflop_action", ""),
                    pack.get("notes", ""),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.OperationalError:
            return 0


def list_drill_packs() -> list[dict]:
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT id, name, positions_json, solution, starting_spot, preflop_action, "
                "notes, created_at, updated_at FROM user_drill_packs ORDER BY updated_at DESC"
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    out: list[dict] = []
    for r in rows:
        try:
            positions = json.loads(r["positions_json"] or "[]")
        except Exception:
            positions = []
        out.append({
            "id": r["id"],
            "name": r["name"],
            "positions": positions,
            "solution": r["solution"] or "",
            "starting_spot": r["starting_spot"] or "",
            "preflop_action": r["preflop_action"] or "",
            "notes": r["notes"] or "",
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return out


def delete_drill_pack(pack_id: int) -> bool:
    with get_connection() as conn:
        try:
            cur = conn.execute("DELETE FROM user_drill_packs WHERE id=?", (pack_id,))
            conn.commit()
            return (cur.rowcount or 0) > 0
        except sqlite3.OperationalError:
            return False


# ─── Adaptive Engine Persistence ─────────────────────────────────────


def save_adaptive_state(spots: list[dict], mistake_queue: list[str]) -> int:
    """Replace all adaptive engine state with the given snapshot."""
    written = 0
    with get_connection() as conn:
        try:
            conn.execute("DELETE FROM adaptive_spots")
            conn.execute("DELETE FROM adaptive_mistake_queue")
            for s in spots:
                conn.execute(
                    """INSERT OR REPLACE INTO adaptive_spots
                       (spot_id, last_attempt_ts, next_due_ts, interval_idx,
                        correct_streak, total_attempts, total_correct,
                        last_ev_loss, rolling_ev_loss, tags, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (
                        s["spot_id"],
                        s.get("last_attempt_ts", 0),
                        s.get("next_due_ts", 0),
                        s.get("interval_idx", 0),
                        s.get("correct_streak", 0),
                        s.get("total_attempts", 0),
                        s.get("total_correct", 0),
                        s.get("last_ev_loss", 0),
                        s.get("rolling_ev_loss", 0),
                        json.dumps(list(s.get("tags", []))),
                    ),
                )
                written += 1
            for sid in mistake_queue:
                conn.execute(
                    "INSERT INTO adaptive_mistake_queue (spot_id) VALUES (?)",
                    (sid,),
                )
            conn.commit()
        except sqlite3.OperationalError:
            return 0
    return written


def load_adaptive_state() -> dict:
    """Load saved adaptive engine state. Returns {spots, mistake_queue} dicts."""
    with get_connection() as conn:
        try:
            spot_rows = conn.execute(
                "SELECT spot_id, last_attempt_ts, next_due_ts, interval_idx, "
                "correct_streak, total_attempts, total_correct, last_ev_loss, "
                "rolling_ev_loss, tags FROM adaptive_spots"
            ).fetchall()
            queue_rows = conn.execute(
                "SELECT spot_id FROM adaptive_mistake_queue ORDER BY position"
            ).fetchall()
        except sqlite3.OperationalError:
            return {"spots": [], "mistake_queue": []}
    spots: list[dict] = []
    for r in spot_rows:
        try:
            tags = json.loads(r["tags"] or "[]")
        except Exception:
            tags = []
        spots.append({
            "spot_id": r["spot_id"],
            "last_attempt_ts": r["last_attempt_ts"],
            "next_due_ts": r["next_due_ts"],
            "interval_idx": r["interval_idx"],
            "correct_streak": r["correct_streak"],
            "total_attempts": r["total_attempts"],
            "total_correct": r["total_correct"],
            "last_ev_loss": r["last_ev_loss"],
            "rolling_ev_loss": r["rolling_ev_loss"],
            "tags": tags,
        })
    return {
        "spots": spots,
        "mistake_queue": [r["spot_id"] for r in queue_rows],
    }


def clear_adaptive_state() -> None:
    with get_connection() as conn:
        try:
            conn.execute("DELETE FROM adaptive_spots")
            conn.execute("DELETE FROM adaptive_mistake_queue")
            conn.commit()
        except sqlite3.OperationalError:
            return


def imported_hands_count() -> int:
    with get_connection() as conn:
        try:
            return conn.execute("SELECT COUNT(*) FROM imported_hands").fetchone()[0]
        except sqlite3.OperationalError:
            return 0


def clear_imported_hands() -> int:
    with get_connection() as conn:
        try:
            cursor = conn.execute("DELETE FROM imported_hands")
            conn.commit()
            return cursor.rowcount
        except sqlite3.OperationalError:
            return 0


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
