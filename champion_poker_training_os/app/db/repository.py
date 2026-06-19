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


def _ensure_played_hand_columns() -> None:
    """played_hands tablosuna gerçek istatistik bayrak kolonlarını ekle
    (idempotent). Eski şemada VPIP/PFR/3bet biriken çipten yanlış türetiliyordu;
    artık preflop GÖNÜLLÜ aksiyondan gelen bayraklar kalıcılaşır.

    Yeni kolonlar NULL bırakılır (None) → ``get_player_stats`` bayrak verisi
    olmayan eski elleri eski (yaklaşık) yönteme düşürür, yeni elleri gerçek
    tanımla sayar.
    """
    with get_connection() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(played_hands)")}
        for col in ("hero_vpip", "hero_pfr", "hero_3bet_opp", "hero_3bet",
                    "hero_postflop_aggr", "hero_postflop_passive"):
            if col not in cols:
                conn.execute(f"ALTER TABLE played_hands ADD COLUMN {col} INTEGER")
        # Birim tutarlılığı: pot/hero_profit/hero_invested ÇİP cinsinden saklanır
        # (cash oyunda bb=1 olduğu için zaten bb-ölçekli). big_blind ile okurken
        # bb'ye çevrilir; game_type cash/tournament/fast ayrımı yapar. Eskiden
        # turnuva elleri çip-ölçekli, cash elleri bb-ölçekli karışıyordu →
        # 'BB/100 +16898' gibi saçma istatistikler. Cash profili artık yalnız
        # cash ellerini bb-normalize ederek sayar.
        if "big_blind" not in cols:
            conn.execute("ALTER TABLE played_hands ADD COLUMN big_blind REAL DEFAULT 1.0")
        if "game_type" not in cols:
            conn.execute("ALTER TABLE played_hands ADD COLUMN game_type TEXT DEFAULT 'cash'")
            # Legacy backfill (idempotent): bb-ölçekli kaydedilemeyen, çip-ölçekli
            # eski turnuva elleri pot>1000 ile ayrışır (cash bb-pot'ları ≪1000).
            # Bu eller cash istatistiklerden dışlanır (per-hand bb kurtarılamaz).
            conn.execute(
                "UPDATE played_hands SET game_type='tournament' "
                "WHERE pot > 1000 AND (game_type='cash' OR game_type IS NULL)")
        conn.commit()


def _flag(hand_data: dict, key: str):
    """dict'te bayrak varsa 0/1, yoksa None döndür (eski el = bilinmiyor)."""
    if key not in hand_data or hand_data[key] is None:
        return None
    return 1 if hand_data[key] else 0


def save_played_hand(hand_data: dict) -> None:
    """Save a completed played hand to the database."""
    _ensure_played_hand_columns()
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO played_hands
               (hand_id, hero_cards, community, pot, hero_invested, hero_profit,
                hero_won, winner_hand_name, streets_seen, session_id,
                hero_vpip, hero_pfr, hero_3bet_opp, hero_3bet,
                hero_postflop_aggr, hero_postflop_passive, big_blind, game_type,
                created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
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
                _flag(hand_data, "hero_vpip"),
                _flag(hand_data, "hero_pfr"),
                _flag(hand_data, "hero_3bet_opp"),
                _flag(hand_data, "hero_3bet"),
                hand_data.get("hero_postflop_aggr") if hand_data.get("hero_postflop_aggr") is not None else None,
                hand_data.get("hero_postflop_passive") if hand_data.get("hero_postflop_passive") is not None else None,
                float(hand_data.get("big_blind", 1.0) or 1.0),
                hand_data.get("game_type", "cash") or "cash",
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
    _ensure_mistake_table()
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
            # GTO'dan ciddi sapma → GERÇEK spotu "Hatalarımı Tekrar Oyna" için sakla
            if (freq_err >= 60 or ev_loss > 1.0) and snap.get("hero_combo"):
                _save_mistake_spot(conn, snap, best, ev_loss, freq_err, cat)
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


def _ensure_mistake_table() -> None:
    """Gerçek hata-spotları tablosu (oyuncunun GTO'dan saptığı eller)."""
    with get_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS mistake_spots (
                id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                category TEXT, street TEXT, scenario TEXT,
                board TEXT, hero_cards TEXT, hero_position TEXT,
                n_active INTEGER, pot_bb REAL, to_call_bb REAL, eff_stack_bb REAL,
                pot_type TEXT, hero_action TEXT, best_action TEXT,
                ev_loss REAL, freq_err REAL,
                format TEXT, stage TEXT )""")
        # Eski tablolar için migration (format/stage sonradan eklendi)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(mistake_spots)")}
        if "format" not in cols:
            conn.execute("ALTER TABLE mistake_spots ADD COLUMN format TEXT")
        if "stage" not in cols:
            conn.execute("ALTER TABLE mistake_spots ADD COLUMN stage TEXT")
        conn.commit()


def _save_mistake_spot(conn, snap: dict, best: str, ev: float,
                       fe: float, cat: str) -> None:
    conn.execute(
        """INSERT INTO mistake_spots
           (category, street, scenario, board, hero_cards, hero_position,
            n_active, pot_bb, to_call_bb, eff_stack_bb, pot_type,
            hero_action, best_action, ev_loss, freq_err, format, stage, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
        (
            cat, snap.get("street", ""), snap.get("scenario", ""),
            snap.get("board", ""),
            snap.get("hero_cards_disp") or snap.get("hero_combo", ""),
            snap.get("hero_position", ""), int(snap.get("n_active", 2) or 2),
            float(snap.get("pot_bb", 0) or 0), float(snap.get("to_call_bb", 0) or 0),
            float(snap.get("eff_stack_bb", 0) or 0), snap.get("pot_type", "SRP"),
            snap.get("hero_action", ""), best, float(ev or 0), float(fe or 0),
            (snap.get("format") or "").lower(), snap.get("stage") or "",
        ),
    )


def get_mistake_spots(limit: int = 30) -> list:
    """Oyuncunun GERÇEK hata spotlarını trainer-uyumlu dict olarak döndür.

    "Hatalarımı Tekrar Oyna" için: gerçek board/kart/pozisyon ile masada
    yeniden oynanabilir. En yüksek EV-kaybı önce. Veri yoksa [].
    """
    _ensure_mistake_table()
    with get_connection() as conn:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM mistake_spots ORDER BY ev_loss DESC, id DESC LIMIT ?",
                (limit,)).fetchall()]
        except sqlite3.OperationalError:
            return []
    out = []
    for i, r in enumerate(rows):
        n = int(r.get("n_active") or 2)
        out.append({
            "id": f"MISTAKE-{r['id']:04d}",
            "title": f"Hatan: {r.get('scenario') or r.get('category')} "
                     f"· {r.get('hero_position')}",
            "position": r.get("hero_position") or "BTN",
            "stack_bb": float(r.get("eff_stack_bb") or 100),
            "table": "HU" if n <= 2 else f"{n}-max",
            "hero_cards": r.get("hero_cards") or "",
            "board": r.get("board") or "",
            "street": (r.get("street") or "preflop").lower(),
            "pot_bb": float(r.get("pot_bb") or 0),
            "scenario": r.get("scenario") or "",
            "category": r.get("category") or "",
            "options": ("fold", "call", "raise", "jam"),
            "best_action": (r.get("best_action") or "").lower(),
            "your_action": (r.get("hero_action") or "").lower(),
            "ev_loss": float(r.get("ev_loss") or 0),
            "source": "mistake",
        })
    return out


def get_position_leaks(min_sample: int = 3) -> list:
    """Pozisyon bazında EV-kaybı (mistake_spots) → 'hangi pozisyonda sızıyorum'.

    [{position, n, ev_lost}] — EV kaybı yüksekten düşüğe. "Erken pozisyonda
    marjinal raise" gibi içgörüler için. Veri yoksa [].
    """
    _ensure_mistake_table()
    with get_connection() as conn:
        try:
            rows = conn.execute(
                "SELECT hero_position AS pos, COUNT(*) AS n, "
                "COALESCE(SUM(ev_loss),0) AS ev FROM mistake_spots "
                "WHERE hero_position != '' GROUP BY hero_position").fetchall()
        except sqlite3.OperationalError:
            return []
    out = [{"position": r["pos"], "n": int(r["n"]), "ev_lost": round(float(r["ev"]), 1)}
           for r in rows if int(r["n"]) >= min_sample]
    out.sort(key=lambda x: x["ev_lost"], reverse=True)
    return out


_EARLY_POS = {"UTG", "UTG+1", "UTG+2", "MP", "EP"}
_MID_POS = {"LJ", "HJ", "CO", "MP+1"}
_LATE_POS = {"BTN", "SB", "BTN/SB"}


def _pos_bucket(pos: str) -> str:
    p = (pos or "").upper()
    if p in _EARLY_POS:
        return "erken pozisyon"
    if p in _MID_POS:
        return "orta pozisyon"
    if p in _LATE_POS:
        return "geç pozisyon"
    if p == "BB":
        return "BB"
    return "diğer"


def _stack_bucket(eff: float) -> str:
    if eff <= 20:
        return "sığ stack (≤20bb)"
    if eff <= 50:
        return "orta stack (20–50bb)"
    return "derin stack (>50bb)"


def _table_bucket(n: int) -> str:
    """Oyuncu sayısı → masa formatı. Full-ring (7+) "default" sayılıp
    etikette gizlenir; HU ve short-handed bilgi taşır."""
    n = int(n or 2)
    if n <= 2:
        return "HU"
    if n <= 6:
        return "short-handed"
    return ""          # full-ring (7+) → etikette gösterme


def _fmt_label(fmt: str) -> str:
    return {"mtt": "MTT", "sng": "SNG", "cash": ""}.get((fmt or "").lower(), "")


def _segment_label(fmt: str, stage: str, table: str,
                   pos_b: str, stk_b: str) -> str:
    """Anlamlı boyutları sırayla birleştir: format · aşama · masa · poz · stack.
    'cash'/full-ring/bilinmeyen-aşama gibi default'lar gizlenir."""
    parts: list[str] = []
    fl = _fmt_label(fmt)
    if fl:
        parts.append(fl)
    st = (stage or "").strip()
    if st and st.lower() not in ("", "unknown", "-", "none"):
        parts.append(st)
    if table:
        parts.append(table)
    parts.append(pos_b)
    parts.append(stk_b)
    return " · ".join(parts)


def get_segmented_insights(min_sample: int = 3) -> list:
    """Format × turnuva-aşaması × masa × pozisyon × stack segmentlerinde
    sistematik hatalar.

    "MTT'de orta aşamada short-stack'e düşünce erken pozisyonda marjinal
    raise" gibi içgörüler — gerçek mistake_spots verisinden.
    [{segment, n, ev_lost, pattern, tip}] EV-kaybı yüksekten düşüğe.
    Veri yoksa [].
    """
    _ensure_mistake_table()
    with get_connection() as conn:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT hero_position, eff_stack_bb, n_active, best_action, "
                "hero_action, ev_loss, scenario, format, stage "
                "FROM mistake_spots").fetchall()]
        except sqlite3.OperationalError:
            return []
    from collections import defaultdict
    seg: dict = defaultdict(lambda: {"n": 0, "ev": 0.0, "over_raise": 0,
                                     "over_fold": 0, "label": ""})
    for r in rows:
        pos_b = _pos_bucket(r.get("hero_position"))
        stk_b = _stack_bucket(float(r.get("eff_stack_bb") or 0))
        tbl = _table_bucket(r.get("n_active"))
        fmt = r.get("format") or ""
        stage = r.get("stage") or ""
        key = (fmt.lower(), stage, tbl, pos_b, stk_b)
        s = seg[key]
        s["n"] += 1
        s["ev"] += float(r.get("ev_loss") or 0)
        s["label"] = _segment_label(fmt, stage, tbl, pos_b, stk_b)
        ha = (r.get("hero_action") or "").upper()
        ba = (r.get("best_action") or "").upper()
        if ha in ("RAISE", "BET", "ALL_IN") and ba == "FOLD":
            s["over_raise"] += 1            # GTO fold derken raise = gereksiz agresyon
        elif ha == "FOLD" and ba in ("RAISE", "BET", "CALL", "ALL_IN"):
            s["over_fold"] += 1
    out = []
    for key, s in seg.items():
        if s["n"] < min_sample:
            continue
        if s["over_raise"] >= s["over_fold"] and s["over_raise"] > 0:
            pattern = (f"%{100*s['over_raise']/s['n']:.0f} oranında GTO fold "
                       f"derken raise/bet ettin (gereksiz agresyon)")
            tip = "Bu segmentte açılış/raise eşiğini yükselt; marjinal elleri pas geç."
        elif s["over_fold"] > 0:
            pattern = (f"%{100*s['over_fold']/s['n']:.0f} oranında GTO devam "
                       f"ederken fold ettin (over-fold)")
            tip = "Bu segmentte devam eşiğini düşür; equity'n yetiyorsa bırakma."
        else:
            pattern = "karışık sapmalar"
            tip = "El sonu reveal'da bu segment kararlarını incele."
        out.append({
            "segment": s["label"],
            "n": s["n"], "ev_lost": round(s["ev"], 1),
            "pattern": pattern, "tip": tip,
        })
    out.sort(key=lambda x: x["ev_lost"], reverse=True)
    return out


def get_self_insights() -> dict:
    """Oyuncunun güçlü/zayıf yönleri — gerçek veriden derlenmiş içgörüler.

    {strengths: [...], weaknesses: [...], summary: str} — Reports'ta gösterilir.
    Kaynaklar: kategori-bazlı GTO doğruluk, pozisyon-bazlı EV kaybı, leak'ler,
    played-hands istatistikleri (VPIP/WTSD/W$SD).
    """
    cats = get_gto_category_accuracy()
    pos = get_position_leaks()
    stats = get_player_stats()
    strengths, weaknesses = [], []

    # Kategori doğruluğu → güçlü (≥70) / zayıf (<55, yeterli örneklem)
    for cat, d in sorted(cats.items(), key=lambda kv: kv[1]["accuracy"]):
        if d["n"] < 5:
            continue
        if d["accuracy"] >= 72:
            strengths.append(f"{cat}: GTO doğruluk %{d['accuracy']:.0f} ({d['n']} karar)")
        elif d["accuracy"] < 55:
            weaknesses.append(f"{cat}: GTO doğruluk %{d['accuracy']:.0f} — "
                              f"en çok burada sapıyorsun ({d['n']} karar)")
    # Pozisyon-bazlı EV kaybı → en pahalı pozisyon
    if pos and pos[0]["ev_lost"] > 1:
        p = pos[0]
        weaknesses.append(f"{p['position']} pozisyonunda EV kaybın yüksek "
                          f"(~{p['ev_lost']:.0f}bb, {p['n']} hata) — bu pozisyonda "
                          f"range/sizing'ini gözden geçir.")
    # Played-hands stilistik
    if stats["total_hands"] >= 20:
        if stats["vpip"] > 33:
            weaknesses.append(f"VPIP %{stats['vpip']:.0f} fazla loose — preflop sıkılaş.")
        elif 18 <= stats["vpip"] <= 28:
            strengths.append(f"VPIP %{stats['vpip']:.0f} sağlıklı aralıkta.")
        if stats["wsd"] >= 50 and stats["wtsd"] >= 24:
            strengths.append(f"W$SD %{stats['wsd']:.0f} — showdown'larını iyi seçiyorsun.")
        elif stats["wsd"] < 45 and stats["wtsd"] > 20:
            weaknesses.append(f"W$SD %{stats['wsd']:.0f} düşük — zayıf ellerle showdown'a "
                              f"gidiyorsun, river fold'larını sıkılaştır.")
    return {"strengths": strengths[:5], "weaknesses": weaknesses[:5],
            "n_decisions": sum(d["n"] for d in cats.values())}


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


def get_gto_accuracy_trend(days: int = 14) -> list:
    """Günlük GTO doğruluk eğilimi (hero_decisions'tan).

    Her gün için: karar sayısı, GTO doğruluk % (frequency_error ≤ 65 ≈ A/B
    notu, SessionScore.accuracy ile tutarlı), ortalama EV kaybı. Gelişim
    grafiği / "ilerliyor muyum" göstergesi için. Eskiden yeniye sıralı.
    """
    _ensure_decision_columns()
    with get_connection() as conn:
        try:
            rows = conn.execute(
                """SELECT date(created_at) AS d,
                          COUNT(*) AS n,
                          SUM(CASE WHEN frequency_error <= 65 THEN 1 ELSE 0 END) AS ok,
                          COALESCE(AVG(ev_loss), 0) AS avg_ev
                   FROM hero_decisions
                   WHERE created_at IS NOT NULL
                   GROUP BY date(created_at)
                   ORDER BY d DESC
                   LIMIT ?""",
                (days,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    out = [
        {
            "date": r["d"],
            "decisions": int(r["n"]),
            "accuracy": round(100.0 * (r["ok"] or 0) / r["n"], 1) if r["n"] else 0.0,
            "avg_ev_loss": round(float(r["avg_ev"] or 0), 2),
        }
        for r in rows if r["d"]
    ]
    out.reverse()   # eskiden yeniye
    return out


def get_gto_category_accuracy() -> dict:
    """Kategori bazında GTO doğruluk (hero_decisions'tan).

    {category: {"n": int, "accuracy": float, "avg_ev_loss": float}}.
    accuracy = frequency_error ≤ 65 olan kararların oranı (≈ A/B notu).
    """
    _ensure_decision_columns()
    with get_connection() as conn:
        try:
            rows = conn.execute(
                """SELECT COALESCE(category,'Preflop') AS cat,
                          COUNT(*) AS n,
                          SUM(CASE WHEN frequency_error <= 65 THEN 1 ELSE 0 END) AS ok,
                          COALESCE(AVG(ev_loss),0) AS avg_ev
                   FROM hero_decisions
                   GROUP BY COALESCE(category,'Preflop')""",
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
    out = {}
    for r in rows:
        n = int(r["n"]) or 0
        if n <= 0:
            continue
        out[r["cat"]] = {
            "n": n,
            "accuracy": round(100.0 * (r["ok"] or 0) / n, 1),
            "avg_ev_loss": round(float(r["avg_ev"] or 0), 2),
        }
    return out


def get_player_stats() -> dict:
    """Gerçek poker tanımlarıyla hero istatistikleri: VPIP, PFR, 3bet, WTSD,
    W$SD, AF, BB/100.

    VPIP/PFR/3bet artık preflop GÖNÜLLÜ aksiyon bayraklarından (hero_vpip/
    hero_pfr/hero_3bet) sayılır — kör/ante/postflop biriken çipten DEĞİL.
    Bayrak verisi olmayan ESKİ eller (NULL) varsa onlar için eski yaklaşık
    yönteme (hero_invested > 1bb) düşülür, böylece geçmiş bozulmaz.
    """
    _ensure_played_hand_columns()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM played_hands").fetchone()[0]
        if total == 0:
            return {
                "total_hands": 0, "vpip": 0, "pfr": 0, "three_bet": 0,
                "wtsd": 0, "wsd": 0, "af": 0, "profit_bb": 0, "bb_per_100": 0,
                "win_rate": 0, "avg_pot": 0,
            }

        wins = conn.execute("SELECT COUNT(*) FROM played_hands WHERE hero_won = 1").fetchone()[0]
        # Profit/pot YALNIZ cash ellerinden ve bb-NORMALİZE (hero_profit/big_blind).
        # Turnuva elleri çip-ölçekli + farklı format → cash bb/100'ü kirletir;
        # dışlanır. Eski karışık-birim 'BB/100 +16898' saçmalığının kökü buydu.
        cash_n = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE game_type='cash'").fetchone()[0]
        profit = conn.execute(
            "SELECT COALESCE(SUM(hero_profit / NULLIF(big_blind,0)), 0) "
            "FROM played_hands WHERE game_type='cash'").fetchone()[0]
        avg_pot = conn.execute(
            "SELECT COALESCE(AVG(pot / NULLIF(big_blind,0)), 0) "
            "FROM played_hands WHERE game_type='cash'").fetchone()[0]

        # ── Gerçek bayraklı eller (yeni) ──
        flagged = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE hero_vpip IS NOT NULL"
        ).fetchone()[0]
        vpip_real = conn.execute(
            "SELECT COALESCE(SUM(hero_vpip), 0) FROM played_hands WHERE hero_vpip IS NOT NULL"
        ).fetchone()[0]
        pfr_real = conn.execute(
            "SELECT COALESCE(SUM(hero_pfr), 0) FROM played_hands WHERE hero_pfr IS NOT NULL"
        ).fetchone()[0]
        tb_opp = conn.execute(
            "SELECT COALESCE(SUM(hero_3bet_opp), 0) FROM played_hands WHERE hero_3bet_opp IS NOT NULL"
        ).fetchone()[0]
        tb_did = conn.execute(
            "SELECT COALESCE(SUM(hero_3bet), 0) FROM played_hands WHERE hero_3bet IS NOT NULL"
        ).fetchone()[0]

        # ── Bayraksız eski eller — yaklaşık yöntem (geriye dönük uyum) ──
        legacy = total - flagged
        legacy_invested = conn.execute(
            "SELECT COUNT(*) FROM played_hands "
            "WHERE hero_vpip IS NULL AND hero_invested > 1"
        ).fetchone()[0] if legacy else 0

        # VPIP/PFR: gerçek bayraklı + eski-yaklaşık birleşik payda = total
        vpip_n = vpip_real + legacy_invested
        pfr_n = pfr_real + round(legacy_invested * 0.7)
        vpip = round(100 * vpip_n / total, 1)
        pfr = round(100 * pfr_n / total, 1)
        # 3bet: yalnız gerçek fırsat verisinden (eski ellerde fırsat bilinmiyor)
        three_bet = round(100 * tb_did / tb_opp, 1) if tb_opp else 0.0

        # WTSD: flop GÖREN eller payda (streets_seen>=2), SD'ye giden pay
        saw_flop = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE streets_seen >= 2"
        ).fetchone()[0]
        showdowns = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE streets_seen >= 4"
        ).fetchone()[0]
        won_at_sd = conn.execute(
            "SELECT COUNT(*) FROM played_hands WHERE streets_seen >= 4 AND hero_won = 1"
        ).fetchone()[0]

        # AF (Aggression Factor) = postflop (bet+raise) / call — gerçek tanım.
        # Veri yoksa (eski eller) nötr 1.0 göster.
        aggr_sum = conn.execute(
            "SELECT COALESCE(SUM(hero_postflop_aggr), 0) FROM played_hands "
            "WHERE hero_postflop_aggr IS NOT NULL"
        ).fetchone()[0]
        passive_sum = conn.execute(
            "SELECT COALESCE(SUM(hero_postflop_passive), 0) FROM played_hands "
            "WHERE hero_postflop_passive IS NOT NULL"
        ).fetchone()[0]
        af = round(aggr_sum / passive_sum, 2) if passive_sum else (
            round(float(aggr_sum), 2) if aggr_sum else 1.0)
        return {
            "total_hands": total,
            "vpip": vpip,
            "pfr": pfr,
            "three_bet": three_bet,
            "wtsd": round(100 * showdowns / max(saw_flop, 1), 1),
            "wsd": round(100 * won_at_sd / max(showdowns, 1), 1),
            "af": af,
            "profit_bb": round(profit, 2),
            "bb_per_100": round(100 * profit / max(cash_n, 1), 1),
            "win_rate": round(100 * wins / total, 1) if total else 0,
            "avg_pot": round(avg_pot, 1),
        }


# ─── Leak Ledger (kalıcı drill öz-bilgisi + spaced repetition) ───────


def _ensure_leak_ledger() -> None:
    with get_connection() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS leak_ledger (
                 category TEXT PRIMARY KEY,
                 attempts INTEGER DEFAULT 0,
                 correct INTEGER DEFAULT 0,
                 streak INTEGER DEFAULT 0,
                 ev_loss REAL DEFAULT 0,
                 first_seen REAL,
                 last_seen REAL
               )""")
        conn.commit()


def record_drill_result(category: str, correct: bool, ev_loss: float = 0.0,
                        now: float | None = None) -> None:
    """Bir drill tekrarını leak-ledger'a işle (upsert + streak güncelle)."""
    import time
    now = float(now) if now is not None else time.time()
    _ensure_leak_ledger()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT attempts, correct, streak, ev_loss, first_seen "
            "FROM leak_ledger WHERE category=?", (category,)).fetchone()
        if row:
            attempts = row["attempts"] + 1
            corr = row["correct"] + (1 if correct else 0)
            streak = (row["streak"] + 1) if correct else 0
            ev = (row["ev_loss"] or 0.0) + float(ev_loss)
            first = row["first_seen"] or now
            conn.execute(
                "UPDATE leak_ledger SET attempts=?, correct=?, streak=?, "
                "ev_loss=?, first_seen=?, last_seen=? WHERE category=?",
                (attempts, corr, streak, ev, first, now, category))
        else:
            conn.execute(
                "INSERT INTO leak_ledger (category, attempts, correct, streak, "
                "ev_loss, first_seen, last_seen) VALUES (?,?,?,?,?,?,?)",
                (category, 1, 1 if correct else 0, 1 if correct else 0,
                 float(ev_loss), now, now))
        conn.commit()


def get_leak_ledger(now: float | None = None) -> list:
    """Tüm leak kategorilerinin kalıcı durumu (spaced-repetition + status)."""
    import time
    from app.poker.leak_ledger import compute_status
    now = float(now) if now is not None else time.time()
    _ensure_leak_ledger()
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM leak_ledger ORDER BY attempts DESC")]
    out = []
    for r in rows:
        st = compute_status(r["attempts"], r["correct"], r["streak"],
                            r["first_seen"] or now, r["last_seen"] or now, now)
        out.append({**r, **st})
    return out


def import_hands_from_text(text: str, session_id: int = 1) -> int:
    """PokerStars el-geçmişi metnini parse edip played_hands'e yaz.

    Döndürür: içeri alınan el sayısı. Aynı hand_id varsa REPLACE edilir
    (save_played_hand INSERT OR REPLACE). Gerçek online ellerin analiz/leak/
    GTO-ilerleme verisine katılması için.
    """
    try:
        from app.poker.hand_history_import import parse_pokerstars
    except Exception:
        return 0
    hands = parse_pokerstars(text)
    n = 0
    for h in hands:
        try:
            h["session_id"] = session_id
            save_played_hand(h)
            n += 1
        except Exception:
            continue
    return n


def get_session_history(limit: int = 50, voluntary_only: bool = False) -> list:
    """Get recent played hands.

    ``voluntary_only=True`` → sadece OYNANAN eller (preflop'ta direkt fold
    etmediğin): flop+ gördüğün (streets_seen≥2) VEYA blind dışı para koyduğun
    (hero_invested>1.01bb) eller. Hand History Analyzer bunu kullanır — sıkıcı
    preflop fold'ları eler, gerçek kararlarını gösterir.
    """
    where = ("WHERE streets_seen >= 2 OR hero_invested > 1.01"
             if voluntary_only else "")
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM played_hands {where} "
            f"ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def count_played_hands(voluntary_only: bool = False) -> int:
    """Toplam (veya sadece oynanan) el sayısı."""
    where = ("WHERE streets_seen >= 2 OR hero_invested > 1.01"
             if voluntary_only else "")
    with get_connection() as conn:
        return int(conn.execute(
            f"SELECT COUNT(*) FROM played_hands {where}").fetchone()[0])


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


# D237: gerçek Soyrac-sapma leak'leri (soyrac_hands user_action vs soyrac_action).
# SADECE -EV leak'ler yüzeye çıkar; +EV "dokunuşlar" (loose-call, flat-cheap-flop)
# HARİÇ. Her leak'e kitap-referanslı fix. Bust-share severity'yi belirler.
_SOYRAC_LEAK_META = {
    "Over-defend — çöp/spekülatif savunma (GTO'da bile -EV)": {
        "name": "Çöp/spekülatif over-defend", "category": "Preflop",
        "fix": "Çöpü SADECE BB + indirim + kapanış multiway savun; gerisi FOLD. (Bible Böl.22.2/24.1)"},
    "Çok geniş açış (eşik altı raise)": {
        "name": "Çok geniş açış (eşik-altı)", "category": "Preflop",
        "fix": "Eşik-altı açma. Geç-poz turnuva steal'i (yarım pre-empt) hariç sıkı kal. (Böl.21)"},
    "3-bet pot over-call (premium değilken call → para yakar)": {
        "name": "3-bet pot over-call", "category": "Preflop",
        "fix": "33-66 3-bet'e FOLD, 77+ set-mine call, QQ+/AK 4-bet. (Böl.26.1) [D236 motora da girdi]"},
    "Aşırı 3-bet (premium değilken yükseltme)": {
        "name": "Aşırı 3-bet (non-premium)", "category": "Preflop",
        "fix": "Küçük çifti/zayıf eli 3-bet'leme → flat/fold. 3-bet for value 66+/JJ+. (Böl.26.1) [D234]"},
    "Aşırı 4-bet (premium/blocker yok)": {
        "name": "Aşırı 4-bet (non-premium)", "category": "Preflop",
        "fix": "4-bet SADECE QQ+/AK veya derin wheel-ace blocker-bluff. (Böl.27)"},
    "Sapma: sen R, Soyrac C": {
        "name": "Raise-yerine-flat ters çevirme", "category": "Preflop",
        "fix": "Set-miner/connector'ı raise'e çevirme → flat (ucuz flop). Agresyon value-3bet + steal'de. (Böl.26.1)"},
    # NOT (D281 değerlendirme): "sen C, Soyrac R/F" (call-yerine-raise / gevşek-call),
    # "sen F, Soyrac C" ve "çok sıkı" KASITLI eşlenmedi — bunlar en DÜŞÜK bust-paylı
    # (%15-22) +EV DOKUNUŞLAR (D238), leak DEĞİL. Soft sahada call'a sapmak +EV-max'tır
    # (Soyrac = referans, hedef değil). Gerçek -EV leak'ler yüksek-bust olanlar: over-defend
    # / geniş-açış / R→C-spew / 3bet-over-call (yukarıda eşli → Leak Finder zaten gösteriyor).
}


def _soyrac_leaks_from_rows(rows, min_count: int = 10) -> list:
    """SAF mantık (DB-bağımsız, test-edilebilir): (leak, count, busts) satırlarından
    -EV leak dict'leri üretir. rows: [{'leak','c','busts'} ...] (dict ya da sqlite.Row)."""
    out = []
    for r in rows:
        leak = r["leak"]; cnt = int(r["c"] or 0); busts = int(r["busts"] or 0)
        meta = _SOYRAC_LEAK_META.get(leak)
        if not meta or cnt < min_count:
            continue                       # touch ya da seyrek → atla
        bust_share = (busts / cnt) if cnt else 0.0
        sev = "High" if bust_share >= 0.22 or cnt >= 50 else "Medium"
        out.append({
            "name": meta["name"], "severity": sev, "category": meta["category"],
            "sample_size": cnt,
            "ev_lost": round(cnt * 0.6 * (1 + 2 * bust_share), 1),
            "frequency_deviation": f"{cnt}× (bust %{100*bust_share:.0f})",
            "detail": f"Gerçek oyununda {cnt} kez: {leak}. Bust turnuvalardaki pay %{100*bust_share:.0f}.",
            "fix": meta["fix"],
        })
    out.sort(key=lambda x: -x["ev_lost"])
    return out


def get_soyrac_deviation_leaks(min_count: int = 10) -> list:
    """soyrac_hands'teki GERÇEK kullanıcı-sapmalarından -EV leak'leri çıkarır
    (touch'lar HARİÇ). Bust-share (soyrac_results.itm join) severity'yi belirler.
    Leak Finder ekranı + drill/repair bunları gösterir → gerçek-veri → drill köprüsü."""
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT leak, COUNT(*) c, "
                "SUM(CASE WHEN sr.itm=0 THEN 1 ELSE 0 END) busts "
                "FROM soyrac_hands sh LEFT JOIN soyrac_results sr "
                "ON sh.tournament_id=sr.tournament_id "
                "WHERE sh.leak IS NOT NULL AND sh.leak!='' GROUP BY sh.leak"
            ).fetchall()
    except Exception:
        return []
    return _soyrac_leaks_from_rows([dict(r) for r in rows], min_count)


def get_leak_analysis() -> list:
    """Auto-detect leaks from played hand data + GTO-decision history.

    Üç kaynak: (1) played_hands aggregate istatistikleri (VPIP/WTSD/W$SD…),
    (2) hero_decisions karar-bazlı GTO sapmaları, (3) soyrac_hands GERÇEK
    Soyrac-sapma leak'leri (D237 — kullanıcının asıl leak'leri). Birleşir.
    """
    stats = get_player_stats()
    leaks_found = []

    # ── GERÇEK Soyrac-sapma leak'leri (D237) — kullanıcının asıl -EV sapmaları ──
    try:
        leaks_found.extend(get_soyrac_deviation_leaks())
    except Exception:
        pass

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


# ════════════════════════════════════════════════════════════════════
# SOYRAC GERÇEK EL-KAYDI — kullanıcının turnuva elleri + Soyrac-vs-sen
# karşılaştırması (gerçek otopsi için). Schema dosyasına dokunmaz.
# ════════════════════════════════════════════════════════════════════
def _ensure_soyrac_hands(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS soyrac_hands (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, tournament_id INTEGER,
            street TEXT, scenario TEXT, hero_cards TEXT, position TEXT, stack_bb REAL,
            user_action TEXT, soyrac_action TEXT, aligned INTEGER, leak TEXT)""")


def next_soyrac_tournament_id() -> int:
    conn = get_connection()
    try:
        _ensure_soyrac_hands(conn)
        row = conn.execute("SELECT COALESCE(MAX(tournament_id), 0) + 1 FROM soyrac_hands").fetchone()
        return int(row[0])
    finally:
        conn.close()


def record_soyrac_hands(rows: list, tournament_id: int) -> int:
    """Bir elin hero kararlarını kaydet. rows: [{street,scenario,hero_cards,position,
    stack_bb,user_action,soyrac_action,aligned,leak}]. Döner: yazılan satır sayısı."""
    if not rows:
        return 0
    from datetime import datetime
    conn = get_connection()
    try:
        _ensure_soyrac_hands(conn)
        ts = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            conn.execute(
                """INSERT INTO soyrac_hands (ts, tournament_id, street, scenario,
                    hero_cards, position, stack_bb, user_action, soyrac_action, aligned, leak)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, tournament_id, r.get("street"), r.get("scenario"), r.get("hero_cards"),
                 r.get("position"), r.get("stack_bb"), r.get("user_action"),
                 r.get("soyrac_action"), 1 if r.get("aligned") else 0, r.get("leak")))
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_soyrac_autopsy(n_tournaments: int = 3) -> dict:
    """Son N turnuvanın Soyrac-vs-sen otopsisi: hizalanma%, en sık leak'ler,
    senaryo bazında doğruluk."""
    from collections import Counter
    conn = get_connection()
    try:
        _ensure_soyrac_hands(conn)
        tids = [r[0] for r in conn.execute(
            "SELECT DISTINCT tournament_id FROM soyrac_hands ORDER BY tournament_id DESC LIMIT ?",
            (n_tournaments,)).fetchall()]
        if not tids:
            return {"tournaments": 0, "decisions": 0, "aligned_pct": 0,
                    "top_leaks": [], "by_scenario": {}}
        ph = ",".join("?" * len(tids))
        rows = conn.execute(
            f"SELECT scenario, user_action, soyrac_action, aligned, leak "
            f"FROM soyrac_hands WHERE tournament_id IN ({ph})", tids).fetchall()
    finally:
        conn.close()
    total = len(rows)
    aligned = sum(1 for r in rows if r[3])
    leaks = Counter(r[4] for r in rows if r[4])
    by_scn = {}
    for r in rows:
        scn = r[0] or "?"
        d = by_scn.setdefault(scn, [0, 0])
        d[0] += 1
        d[1] += r[3]
    return {"tournaments": len(tids), "decisions": total,
            "aligned_pct": round(100 * aligned / max(total, 1)),
            "top_leaks": leaks.most_common(6),
            "by_scenario": {k: (v[0], round(100 * v[1] / max(v[0], 1))) for k, v in by_scn.items()}}


def _ensure_soyrac_results(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS soyrac_results (
            tournament_id INTEGER PRIMARY KEY, ts TEXT, finish INTEGER,
            field_size INTEGER, itm INTEGER, profit REAL, pct_rank REAL)""")


def record_soyrac_result(tournament_id, finish, field_size, itm, profit, pct_rank=0) -> None:
    """Turnuva SONUCUNU kaydet (bitiş-yeri/ITM/kâr) — otopsi trendi için."""
    from datetime import datetime
    conn = get_connection()
    try:
        _ensure_soyrac_results(conn)
        conn.execute(
            """INSERT OR REPLACE INTO soyrac_results
               (tournament_id, ts, finish, field_size, itm, profit, pct_rank)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (int(tournament_id), datetime.now().isoformat(timespec="seconds"),
             int(finish or 0), int(field_size or 0), 1 if itm else 0,
             float(profit or 0), float(pct_rank or 0)))
        conn.commit()
    finally:
        conn.close()


def get_soyrac_results(n: int = 20) -> list:
    """Son N turnuva sonucu (yeni→eski)."""
    conn = get_connection()
    try:
        _ensure_soyrac_results(conn)
        rows = conn.execute(
            "SELECT tournament_id, finish, field_size, itm, profit, pct_rank, ts "
            "FROM soyrac_results ORDER BY tournament_id DESC LIMIT ?", (n,)).fetchall()
        return [dict(zip(("tournament_id", "finish", "field_size", "itm",
                          "profit", "pct_rank", "ts"), r)) for r in rows]
    finally:
        conn.close()
