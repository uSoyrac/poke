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


def _ensure_decision_columns() -> None:
    """hero_decisions tablosuna analiz için ek kolonlar ekle (idempotent).

    Eski şema sadece spot_id/hero_action/solver_action/ev_loss/frequency_error/
    sizing_error içeriyordu. Leak Finder'ın zaman ve kategori bazlı analizi
    için ``category``, ``street`` ve ``created_at`` ekliyoruz.
    """
    with get_connection() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(hero_decisions)")}
        if "category" not in cols:
            conn.execute("ALTER TABLE hero_decisions ADD COLUMN category TEXT")
        if "street" not in cols:
            conn.execute("ALTER TABLE hero_decisions ADD COLUMN street TEXT")
        if "created_at" not in cols:
            # SQLite: ALTER ADD COLUMN can't use non-constant default → no default,
            # we set it explicitly on insert.
            conn.execute("ALTER TABLE hero_decisions ADD COLUMN created_at TEXT")
        conn.commit()


def _decision_category(snap: dict) -> str:
    """Snapshot scenario'sunu kaba bir leak kategorisine indirger."""
    scen = (snap.get("scenario") or "").lower()
    street = (snap.get("street") or "").lower()
    if street and street not in ("preflop", "pre-flop", "pre"):
        return "Postflop"
    if scen.startswith("push/fold") or "push/fold" in scen:
        return "Push/Fold"
    if scen.startswith("vs 3-bet") or "3-bet" in scen:
        return "vs 3-bet"
    if scen.startswith("vs rfi") or "vs rfi" in scen:
        return "vs RFI"
    if scen.startswith("rfi"):
        return "RFI"
    if "postflop" in scen:
        return "Postflop"
    return "Preflop"


def _hero_action_freq(snap: dict, action_name: str) -> float:
    """Hero'nun aldığı aksiyona GTO'nun atadığı % (0-100)."""
    a = (action_name or "").upper()
    if a == "FOLD":
        return float(snap.get("fold", 0) or 0)
    if a in ("CALL", "CHECK"):
        return float(snap.get("call", 0) or 0)
    if a in ("RAISE", "BET"):
        return float(snap.get("raise", 0) or 0)
    if a in ("ALL_IN", "ALLIN"):
        return float(snap.get("allin", 0) or 0)
    return 0.0


def _best_gto_action(snap: dict) -> str:
    opts = {
        "FOLD": float(snap.get("fold", 0) or 0),
        "CALL": float(snap.get("call", 0) or 0),
        "RAISE": float(snap.get("raise", 0) or 0),
        "ALL_IN": float(snap.get("allin", 0) or 0),
    }
    return max(opts, key=lambda k: opts[k])


def _decision_ev_loss(snap: dict, hero_action: str) -> float:
    """Kararın kaba EV kaybı (bb) — equity + pot odds'tan.

    +EV bir spotu fold ettiyse: vazgeçilen EV ≈ eq*(pot+call) - call.
    -EV bir call yaptıysa: kayıp ≈ call - eq*(pot+call).
    Diğer durumlarda 0 (sizing/frekans kaybı ayrı izlenir). Solver-exact
    değil — dürüst bir büyüklük tahmini.
    """
    eq = float(snap.get("equity", 0) or 0) / 100.0
    pot = float(snap.get("pot_bb", 0) or 0)
    to_call = float(snap.get("to_call_bb", 0) or 0)
    if eq <= 0 or to_call <= 0.01:
        return 0.0
    call_ev = eq * (pot + to_call) - to_call   # +EV ise call kârlı
    a = (hero_action or "").upper()
    if a == "FOLD" and call_ev > 0:
        return round(call_ev, 2)               # +EV spotu fold ettin
    if a in ("CALL", "CHECK") and call_ev < 0:
        return round(-call_ev, 2)              # -EV call yaptın
    return 0.0


def record_decision_log(log: list) -> int:
    """Bir elin karar snapshot'larını hero_decisions'a kalıcılaştır.

    Sadece GTO mevcut (available) ve hero aksiyonu kaydedilmiş kararlar
    yazılır. frequency_error = 100 - (hero aksiyonuna GTO'nun atadığı %)
    → 0 = tam GTO çizgisinde, 100 = GTO'nun asla yapmadığı aksiyon.
    Döndürür: yazılan satır sayısı.
    """
    if not log:
        return 0
    _ensure_decision_columns()
    written = 0
    with get_connection() as conn:
        for snap in log:
            if not snap.get("available"):
                continue
            hero = snap.get("hero_action")
            if not hero:
                continue
            cat = _decision_category(snap)
            best = _best_gto_action(snap)
            hero_freq = _hero_action_freq(snap, hero)
            freq_err = max(0.0, 100.0 - hero_freq)
            ev_loss = _decision_ev_loss(snap, hero)
            sizing_err = ""
            if snap.get("sizing_bb") and snap.get("hero_amount"):
                try:
                    diff = float(snap["hero_amount"]) - float(snap["sizing_bb"])
                    sizing_err = f"{diff:+.1f}bb"
                except Exception:
                    sizing_err = ""
            conn.execute(
                """INSERT INTO hero_decisions
                   (spot_id, hero_action, solver_action, ev_loss,
                    frequency_error, sizing_error, category, street, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (
                    f"{snap.get('street','')}|{snap.get('scenario','')}",
                    hero, best, ev_loss, freq_err, sizing_err,
                    cat, snap.get("street", ""),
                ),
            )
            written += 1
        conn.commit()
    return written


def get_decision_leaks(min_sample: int = 8) -> list:
    """hero_decisions'tan sistematik GTO-sapması leak'leri tespit et.

    Kategori (RFI / vs RFI / vs 3-bet / Postflop / Push/Fold) bazında:
      - over-fold: GTO devam ederken (call/raise) hero fold ediyor
      - over-aggression: GTO fold ederken hero raise/bet ediyor (spew)
      - genel sapma oranı yüksek
    Veri yetersizse boş liste döner (graceful).
    """
    _ensure_decision_columns()
    with get_connection() as conn:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT spot_id, hero_action, solver_action, ev_loss, "
                "frequency_error, category FROM hero_decisions"
            ).fetchall()]
        except sqlite3.OperationalError:
            return []
    if len(rows) < min_sample:
        return []

    from collections import defaultdict
    buckets: dict[str, list] = defaultdict(list)
    for r in rows:
        buckets[r.get("category") or "Preflop"].append(r)

    leaks: list = []
    for cat, recs in buckets.items():
        n = len(recs)
        if n < min_sample:
            continue
        over_fold = [r for r in recs
                     if (r["hero_action"] == "FOLD")
                     and (r["solver_action"] not in ("FOLD",))]
        over_aggro = [r for r in recs
                      if (r["hero_action"] in ("RAISE", "BET", "ALL_IN"))
                      and (r["solver_action"] == "FOLD")]
        big_dev = [r for r in recs if (r["frequency_error"] or 0) >= 60]
        ev_lost = round(sum(float(r["ev_loss"] or 0) for r in recs), 1)

        of_rate = 100 * len(over_fold) / n
        oa_rate = 100 * len(over_aggro) / n
        dev_rate = 100 * len(big_dev) / n

        if of_rate >= 25:
            leaks.append({
                "name": f"Over-folding ({cat})",
                "severity": "High" if of_rate >= 40 else "Medium",
                "detail": (f"{cat} spotlarında GTO devam ederken %{of_rate:.0f} "
                           f"oranında fold ettin ({len(over_fold)}/{n} karar)."),
                "fix": "Devam eşiğini gözden geçir: equity ≥ break-even ise call et. "
                       "vs-3bet'te value+blocker bluff'ları folding'i bırak.",
                "ev_lost": ev_lost, "sample_size": n,
            })
        if oa_rate >= 18:
            leaks.append({
                "name": f"Over-aggression / spew ({cat})",
                "severity": "High" if oa_rate >= 30 else "Medium",
                "detail": (f"{cat} spotlarında GTO fold ederken %{oa_rate:.0f} "
                           f"oranında raise/bet yaptın ({len(over_aggro)}/{n})."),
                "fix": "Bluff frekansını düşür; sadece blocker/equity olan ellerle "
                       "agresyon. Zayıf ellerle value bölgesine girme.",
                "ev_lost": ev_lost, "sample_size": n,
            })
        if dev_rate >= 35 and of_rate < 25 and oa_rate < 18:
            leaks.append({
                "name": f"GTO çizgisinden sapma ({cat})",
                "severity": "Medium",
                "detail": (f"{cat} kararlarının %{dev_rate:.0f}'inde GTO'nun nadir "
                           f"yaptığı bir aksiyon seçtin ({len(big_dev)}/{n})."),
                "fix": "El sonu reveal panelindeki optimal dağılımı incele; "
                       "yüksek frekanslı aksiyona yaklaş.",
                "ev_lost": ev_lost, "sample_size": n,
            })
    leaks.sort(key=lambda l: l.get("ev_lost", 0), reverse=True)
    return leaks


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


# ─── Hand History Archive (date-indexed) ──────────────────────────────


def _ensure_history_index() -> None:
    """Add an index on played_hands.created_at for fast date-range queries.

    Cheap to call (CREATE INDEX IF NOT EXISTS). Idempotent.
    """
    with get_connection() as conn:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_played_hands_created_at "
            "ON played_hands(created_at DESC)"
        )
        conn.commit()


def get_dates_with_hands(limit_days: int = 90) -> list[dict]:
    """Return [{'date': 'YYYY-MM-DD', 'hands': N, 'net_bb': X, 'wins': W}, ...]
    sorted newest first. Used for the calendar / date-picker view.
    """
    _ensure_history_index()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT date(created_at) AS d,
                      COUNT(*) AS n,
                      COALESCE(SUM(hero_profit), 0) AS net_bb,
                      COALESCE(SUM(hero_won), 0) AS wins,
                      COALESCE(SUM(CASE WHEN streets_seen >= 4 THEN 1 ELSE 0 END), 0) AS sd
               FROM played_hands
               GROUP BY date(created_at)
               ORDER BY d DESC
               LIMIT ?""",
            (limit_days,),
        ).fetchall()
        return [
            {
                "date": r["d"],
                "hands": int(r["n"]),
                "net_bb": float(r["net_bb"]),
                "wins": int(r["wins"]),
                "showdowns": int(r["sd"]),
            }
            for r in rows
        ]


def get_hands_for_date(date_str: str, limit: int = 500,
                         offset: int = 0) -> list[dict]:
    """Return hands played on a specific date (YYYY-MM-DD), newest first.

    Paginated for scalability — 200M-hand archive only loads `limit`
    rows at a time.
    """
    _ensure_history_index()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM played_hands
               WHERE date(created_at) = ?
               ORDER BY created_at DESC, id DESC
               LIMIT ? OFFSET ?""",
            (date_str, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_hand_count_for_date(date_str: str) -> int:
    """Total hand count for a specific day (for pagination UI)."""
    _ensure_history_index()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM played_hands WHERE date(created_at) = ?",
            (date_str,),
        ).fetchone()
        return int(row["n"]) if row else 0


def get_overall_archive_stats() -> dict:
    """Aggregate stats across the entire archive (cheap-ish, uses indices)."""
    _ensure_history_index()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM played_hands").fetchone()[0]
        if total == 0:
            return {"total_hands": 0, "total_days": 0, "net_bb": 0.0,
                    "first_date": None, "last_date": None}
        net = conn.execute(
            "SELECT COALESCE(SUM(hero_profit), 0) FROM played_hands"
        ).fetchone()[0]
        days_row = conn.execute(
            "SELECT COUNT(DISTINCT date(created_at)) FROM played_hands"
        ).fetchone()
        bounds = conn.execute(
            "SELECT MIN(date(created_at)) AS first_d, "
            "       MAX(date(created_at)) AS last_d "
            "FROM played_hands"
        ).fetchone()
        return {
            "total_hands": int(total),
            "total_days": int(days_row[0]),
            "net_bb": float(net),
            "first_date": bounds["first_d"],
            "last_date": bounds["last_d"],
        }


def get_leak_analysis() -> list:
    """Auto-detect leaks from played hand data + GTO-decision history.

    İki kaynak: (1) played_hands aggregate istatistikleri (VPIP/WTSD/W$SD…),
    (2) hero_decisions karar-bazlı GTO sapmaları (over-fold/spew, kategori
    bazında). İkisi birleşir.
    """
    stats = get_player_stats()
    leaks_found = []

    # ── Karar-bazlı GTO leak'leri (her zaman dene; veri varsa ekler) ──
    try:
        leaks_found.extend(get_decision_leaks())
    except Exception:
        pass

    if stats["total_hands"] < 10:
        if leaks_found:
            return leaks_found
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

    # Aggregate (played_hands) leak'lerinin örneklem boyutu = oynanan el sayısı
    for lk in leaks_found:
        if "sample_size" not in lk and lk.get("severity") != "Info":
            lk["sample_size"] = stats["total_hands"]

    has_real = any(l.get("severity") != "Info" for l in leaks_found)
    if not has_real:
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
