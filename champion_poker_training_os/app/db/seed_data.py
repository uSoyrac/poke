from __future__ import annotations

import hashlib
from itertools import cycle

# ───────────────────────────────────────────────────────────────────────────
# GTO Wizard-style spot catalogue  (category → list of spot-dicts)
# ───────────────────────────────────────────────────────────────────────────

SPOT_CATALOG: list[dict] = [
    # ── Bread & Butter MTT Spots (Common) ─────────────────────────────────
    dict(id="MTT-25-LJ-BB-01",  name="25bb LJ RFI vs BB",        category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="LJ",  street="preflop", pot_type="SRP",   hands_played=0,   ev_delta=0.0),
    dict(id="MTT-25-BTN-LJ-01", name="25bb BTN vs LJ RFI",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="BTN", street="preflop", pot_type="SRP",   hands_played=46,  ev_delta=-23.7),
    dict(id="MTT-25-LJ-BTN-01", name="25bb LJ RFI vs BTN",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="LJ",  street="preflop", pot_type="SRP",   hands_played=43,  ev_delta=-147.8),
    dict(id="MTT-25-BB-BTN-01", name="25bb BB vs BTN RFI",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="BB",  street="preflop", pot_type="SRP",   hands_played=0,   ev_delta=0.0),
    dict(id="MTT-25-BTN-BB-01", name="25bb BTN RFI vs BB",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="BTN", street="preflop", pot_type="SRP",   hands_played=0,   ev_delta=0.0),
    dict(id="MTT-40-BTN-LJ-01", name="40bb BTN vs LJ RFI",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BTN", street="preflop", pot_type="SRP",   hands_played=218, ev_delta=+297.8),
    dict(id="MTT-40-LJ-BTN-01", name="40bb LJ RFI vs BTN",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="LJ",  street="preflop", pot_type="SRP",   hands_played=57,  ev_delta=-15.2),
    dict(id="MTT-40-BB-LJ-01",  name="40bb BB vs LJ RFI",        category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BB",  street="preflop", pot_type="SRP",   hands_played=7,   ev_delta=-13.5),
    dict(id="MTT-40-LJ-BB-01",  name="40bb LJ RFI vs BB",        category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="LJ",  street="preflop", pot_type="SRP",   hands_played=297, ev_delta=-80.8),
    dict(id="MTT-40-BB-BTN-01", name="40bb BB vs BTN RFI",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BB",  street="preflop", pot_type="SRP",   hands_played=0,   ev_delta=0.0),
    dict(id="MTT-40-BTN-BB-01", name="40bb BTN RFI vs BB",       category="Bread & Butter MTT Spots (Common)", format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BTN", street="preflop", pot_type="SRP",   hands_played=0,   ev_delta=0.0),
    # ── Board Specific Training MTT ────────────────────────────────────────
    dict(id="MTT-BOARD-DRY-01", name="Playing Dry Boards",        category="Board Specific Training MTT",       format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BTN", street="flop",    pot_type="SRP",   hands_played=104, ev_delta=-116.7),
    dict(id="MTT-BOARD-CON-01", name="Playing Connected Boards",  category="Board Specific Training MTT",       format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BTN", street="flop",    pot_type="SRP",   hands_played=19,  ev_delta=+114.1),
    dict(id="MTT-BOARD-MON-01", name="Monotone Board Defense",    category="Board Specific Training MTT",       format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BB",  street="flop",    pot_type="3BP",   hands_played=8,   ev_delta=-22.5),
    dict(id="MTT-BOARD-PAI-01", name="Paired Board C-bet",        category="Board Specific Training MTT",       format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=25,  position="BTN", street="flop",    pot_type="SRP",   hands_played=31,  ev_delta=-44.0),
    dict(id="MTT-BOARD-TWO-01", name="Two-Tone Boards OOP",       category="Board Specific Training MTT",       format_tag="Tournaments 8-Max", format="MTT",  table="8-max", stack_bb=40,  position="BB",  street="flop",    pot_type="SRP",   hands_played=14,  ev_delta=-18.3),
    # ── ICM Spots ──────────────────────────────────────────────────────────
    dict(id="MTT-ICM-BUB-01",  name="Bubble BTN vs BB Shove",    category="ICM Spots (Bubble / FT)",           format_tag="Tournaments ICM",   format="MTT",  table="8-max", stack_bb=20,  position="BTN", street="preflop", pot_type="SRP",   hands_played=67,  ev_delta=-55.2),
    dict(id="MTT-ICM-FT-01",   name="Final Table SB 3-bet",      category="ICM Spots (Bubble / FT)",           format_tag="Tournaments ICM",   format="MTT",  table="8-max", stack_bb=30,  position="SB",  street="preflop", pot_type="3BP",   hands_played=22,  ev_delta=-33.0),
    dict(id="MTT-ICM-SAT-01",  name="Satellite Fold Equity",      category="ICM Spots (Bubble / FT)",           format_tag="Tournaments ICM",   format="MTT",  table="9-max", stack_bb=15,  position="BB",  street="preflop", pot_type="SRP",   hands_played=11,  ev_delta=-8.1),
    dict(id="MTT-ICM-PKO-01",  name="PKO Spot — Call Off BB",     category="ICM Spots (Bubble / FT)",           format_tag="Tournaments ICM",   format="MTT",  table="8-max", stack_bb=25,  position="BB",  street="preflop", pot_type="SRP",   hands_played=9,   ev_delta=-19.4),
    # ── Exploitative Spots ─────────────────────────────────────────────────
    dict(id="MTT-EXPLO-01",    name="Exploit vs Fish Limper",     category="Exploitative Spots (MTT)",          format_tag="Tournaments Explo", format="MTT",  table="8-max", stack_bb=40,  position="BTN", street="preflop", pot_type="limped",hands_played=33,  ev_delta=+41.2),
    dict(id="MTT-EXPLO-02",    name="3-bet vs Nit UTG",           category="Exploitative Spots (MTT)",          format_tag="Tournaments Explo", format="MTT",  table="8-max", stack_bb=40,  position="CO",  street="preflop", pot_type="3BP",   hands_played=17,  ev_delta=+28.7),
    dict(id="MTT-EXPLO-03",    name="Bluff Catch vs Station",     category="Exploitative Spots (MTT)",          format_tag="Tournaments Explo", format="MTT",  table="8-max", stack_bb=40,  position="BB",  street="river",   pot_type="SRP",   hands_played=44,  ev_delta=-62.1),
    # ── Cash Game 8-Max ────────────────────────────────────────────────────
    dict(id="CASH-100-BTN-BB", name="100bb BTN RFI vs BB",        category="Cash Game Bread & Butter",          format_tag="Cash Games 8-Max",  format="Cash", table="8-max", stack_bb=100, position="BTN", street="preflop", pot_type="SRP",   hands_played=312, ev_delta=+187.3),
    dict(id="CASH-100-BB-BTN", name="100bb BB vs BTN RFI",        category="Cash Game Bread & Butter",          format_tag="Cash Games 8-Max",  format="Cash", table="8-max", stack_bb=100, position="BB",  street="preflop", pot_type="SRP",   hands_played=287, ev_delta=-95.4),
    dict(id="CASH-100-CO-BTN", name="100bb CO RFI vs BTN 3bet",   category="Cash Game Bread & Butter",          format_tag="Cash Games 8-Max",  format="Cash", table="8-max", stack_bb=100, position="CO",  street="preflop", pot_type="3BP",   hands_played=88,  ev_delta=-42.1),
    dict(id="CASH-100-SB-BB",  name="100bb SB vs BB Limp",        category="Cash Game Bread & Butter",          format_tag="Cash Games 8-Max",  format="Cash", table="8-max", stack_bb=100, position="SB",  street="preflop", pot_type="limped",hands_played=156, ev_delta=-77.8),
    dict(id="CASH-FLOP-01",    name="Flop C-bet OOP 3BP",         category="Cash Game Bread & Butter",          format_tag="Cash Games 8-Max",  format="Cash", table="8-max", stack_bb=100, position="SB",  street="flop",    pot_type="3BP",   hands_played=72,  ev_delta=-38.5),
    # ── Cash 6-Max ─────────────────────────────────────────────────────────
    dict(id="CASH6-BTN-BB",    name="100bb 6M BTN vs BB",         category="6-Max Cash Spots",                  format_tag="Cash Games 6-Max",  format="Cash", table="6-max", stack_bb=100, position="BTN", street="preflop", pot_type="SRP",   hands_played=445, ev_delta=+221.5),
    dict(id="CASH6-CO-BTN",    name="100bb 6M CO vs BTN",         category="6-Max Cash Spots",                  format_tag="Cash Games 6-Max",  format="Cash", table="6-max", stack_bb=100, position="CO",  street="preflop", pot_type="SRP",   hands_played=193, ev_delta=-48.7),
]

# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

POSITIONS = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
STREETS   = ["preflop", "flop", "turn", "river"]
FORMATS   = ["cash", "MTT", "SNG", "PKO", "heads-up"]
POT_TYPES_LEGACY = ["SRP", "3BP", "4BP", "limped", "multiway"]
BOARD_TEXTURES = [
    "A-high dry", "K-high dynamic", "low connected", "paired",
    "monotone", "two-tone", "flush-completing river",
]
HANDS  = ["AsKh", "QdQs", "JhTh", "8s8c", "Ac5c", "KdQd", "7h6h", "AdJc", "Ts9s", "5d5c"]
BOARDS = ["Ah7c2d", "KsQh8s", "9s8s4d", "QcQd3h", "Jc7c2c", "Td9h4h", "AsKd4s2c9h"]

PREFLOP_OPTIONS_SRP = [
    ("fold", "call", "raise", "jam"),
    ("fold", "call", "3bet", "jam"),
]
PREFLOP_OPTIONS_3BP = [
    ("fold", "call", "4bet", "jam"),
    ("fold", "call", "jam"),
]
POSTFLOP_OPTIONS = [
    ("check", "bet small", "bet large"),
    ("check", "bet medium", "bet large"),
    ("check", "call", "raise"),
]


def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:4], 16)


def _options_for(spot: dict) -> tuple[str, ...]:
    street = spot.get("street", "preflop")
    pot    = spot.get("pot_type", "SRP")
    sid    = spot["id"]
    if street == "preflop":
        pool = PREFLOP_OPTIONS_3BP if ("3BP" in pot or "3bet" in pot or "4BP" in pot) else PREFLOP_OPTIONS_SRP
    else:
        pool = POSTFLOP_OPTIONS
    return tuple(pool[_h(sid) % len(pool)])


def _best_for(spot: dict, options: tuple) -> str:
    return options[_h(spot["id"] + "best") % len(options)]


def _board_for(spot: dict) -> str:
    if spot.get("street", "preflop") == "preflop":
        return ""
    return BOARDS[_h(spot["id"]) % len(BOARDS)]


def _hand_for(spot: dict) -> str:
    return HANDS[_h(spot["id"]) % len(HANDS)]


def _action_history_for(spot: dict) -> str:
    pos    = spot.get("position", "BTN")
    pot    = spot.get("pot_type", "SRP")
    street = spot.get("street", "preflop")
    board  = _board_for(spot)
    if street == "preflop":
        if "3BP" in pot or "4BP" in pot:
            return f"UTG folds · LJ folds · {pos} raises 2.3bb · BB 3-bets 7.1bb"
        return f"UTG folds · LJ folds · {pos} raises 2.3bb"
    return f"Preflop: {pos} opens → call · Flop [{board}]: check"


def _enrich(raw: dict, idx: int) -> dict:
    spot    = dict(raw)
    options = _options_for(spot)
    best    = _best_for(spot, options)
    board   = _board_for(spot)
    stack   = spot.get("stack_bb", 40)
    pot_bb  = round(3.5 + (idx % 9) * 2.25, 1)
    spot.update(
        title          = spot.get("name", spot["id"]),
        hero_cards     = _hand_for(spot),
        board          = board,
        board_texture  = BOARD_TEXTURES[idx % len(BOARD_TEXTURES)],
        action_history = _action_history_for(spot),
        options        = options,
        best_action    = best,
        pot_bb         = pot_bb,
        base_ev        = round(0.85 + (idx % 6) * 0.18, 2),
        range_advantage= ["Hero + range", "Villain + range", "Neutral ranges"][idx % 3],
        nut_advantage  = ["Hero nut advantage", "Villain nut advantage", "Shared nut density"][idx % 3],
        icm            = "off",
        source_confidence = "Mock/demo solver",
    )
    return spot


def get_spot_catalog() -> list[dict]:
    return [_enrich(raw, idx) for idx, raw in enumerate(SPOT_CATALOG)]


def get_spots_by_format_tag(tag: str) -> list[dict]:
    return [s for s in get_spot_catalog() if s.get("format_tag") == tag]


def get_spot_categories() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for s in get_spot_catalog():
        cat = s.get("category", "Other")
        result.setdefault(cat, []).append(s)
    return result


# ───────────────────────────────────────────────────────────────────────────
# Legacy generate_spot_drills — catalogue spots first, then random fillers
# ───────────────────────────────────────────────────────────────────────────

OPTIONS_LEGACY = [
    ("fold", "call", "raise", "jam"),
    ("check", "bet small", "bet medium", "bet large"),
    ("fold", "call", "raise"),
    ("check", "call", "raise", "jam"),
]


def _action_history(idx: int, street: str) -> str:
    pre  = ["UTG folds, LJ raises 2.3bb", "SB completes, BB checks", "HJ opens 2.5bb, CO calls"][idx % 3]
    if street == "preflop":
        return pre
    post = ["Flop: check-check", "Flop: Hero bets 33%, Villain calls", "Turn: Hero fires 66% on blank"][idx % 3]
    return f"{pre} · {post}"


def generate_spot_drills(count: int = 120) -> list[dict]:
    # NEW: prefer the comprehensive auto-generated catalog (325 drills, real GTO data)
    try:
        from app.db.drill_catalog import build_full_catalog
        full = build_full_catalog()
        if full:
            # If caller asked for fewer, take all real drills (don't truncate good content)
            return full
    except Exception:
        pass
    # Legacy fallback
    catalog = get_spot_catalog()
    drills: list[dict] = list(catalog)
    option_cycle = cycle(OPTIONS_LEGACY)
    idx_offset = len(catalog)
    for idx in range(max(0, count - len(catalog))):
        real_idx = idx + idx_offset
        street   = STREETS[real_idx % len(STREETS)]
        options  = next(option_cycle)
        best_action = options[(real_idx * 2 + 1) % len(options)]
        stack    = [10, 15, 20, 25, 40, 60, 100, 200][real_idx % 8]
        pot      = round(3.5 + (real_idx % 9) * 2.25, 1)
        pos      = POSITIONS[real_idx % len(POSITIONS)]
        fmt      = FORMATS[real_idx % len(FORMATS)]
        drills.append({
            "id":           f"SPOT-{real_idx + 1:03d}",
            "name":         f"{street.title()} {pos} decision",
            "title":        f"{street.title()} {pos} decision vs {['nit', 'reg', 'station', 'maniac'][real_idx % 4]}",
            "format":       fmt,
            "format_tag":   "Tournaments 8-Max" if fmt == "MTT" else "Cash Games 8-Max",
            "table":        ["6-max", "9-max", "HU"][real_idx % 3],
            "street":       street,
            "position":     pos,
            "stack_bb":     stack,
            "pot_bb":       pot,
            "hero_cards":   HANDS[real_idx % len(HANDS)],
            "board":        "" if street == "preflop" else BOARDS[real_idx % len(BOARDS)],
            "board_texture":BOARD_TEXTURES[real_idx % len(BOARD_TEXTURES)],
            "pot_type":     POT_TYPES_LEGACY[real_idx % len(POT_TYPES_LEGACY)],
            "action_history":_action_history(real_idx, street),
            "options":      options,
            "best_action":  best_action,
            "base_ev":      round(0.85 + (real_idx % 6) * 0.18, 2),
            "range_advantage":["Hero + range", "Villain + range", "Neutral ranges"][real_idx % 3],
            "nut_advantage":["Hero nut advantage", "Villain nut advantage", "Shared nut density"][real_idx % 3],
            "icm":          ["off", "bubble", "final table", "satellite", "PKO"][real_idx % 5],
            "source_confidence":["Mock/demo solver", "Pre-solved library", "Rule-based heuristic"][real_idx % 3],
            "category":     "General Spots",
            "hands_played": 0,
            "ev_delta":     0.0,
        })
    return drills


def generate_hands(count: int = 100) -> list[dict]:
    hands: list[dict] = []
    drills = generate_spot_drills(count)
    for idx, drill in enumerate(drills):
        hands.append({
            "id":        f"HAND-{idx + 1:04d}",
            "table":     f"Demo Lab {idx % 12 + 1}",
            "format":    drill["format"],
            "hero":      "Hero",
            "villain":   ["SolverReg", "Station42", "ICMScared", "BarrelBot"][idx % 4],
            "hero_cards":drill["hero_cards"],
            "board":     drill["board"] or "preflop",
            "position":  drill["position"],
            "result_bb": round(((idx % 11) - 5) * 1.7, 1),
            "ev_loss":   round((idx % 9) * 0.12, 2),
            "biggest_mistake":["overfold", "thin value missed", "bad bluffcatch", "ICM punt"][idx % 4],
            "timeline":  [
                "Preflop: Hero opens 2.2bb",
                "Flop: Villain checks, Hero bets 33%",
                "Turn: Villain calls, Hero evaluates range shift",
                "River: Decision node marked for review",
            ],
            "spot": drill,
        })
    return hands


def generate_math_drills(count: int = 30) -> list[dict]:
    drills: list[dict] = []
    for idx in range(count):
        kind = ["pot odds", "alpha", "MDF", "EV", "Bayes"][idx % 5]
        pot  = 10 + idx * 2
        bet  = 4 + (idx % 7)
        if kind == "pot odds":
            answer = bet / (pot + 2 * bet)
            prompt = f"Pot {pot}bb, call {bet}bb. Required equity?"
        elif kind == "alpha":
            answer = bet / (bet + pot)
            prompt = f"Bluff risks {bet}bb to win {pot}bb. Required folds?"
        elif kind == "MDF":
            answer = 1 - bet / (bet + pot)
            prompt = f"Villain bets {bet}bb into {pot}bb. MDF?"
        elif kind == "EV":
            answer = 0.42 * pot - 0.58 * bet
            prompt = f"Win 42% for reward {pot}bb and risk {bet}bb. EV?"
        else:
            answer = 0.60 * 0.35 / (0.60 * 0.35 + 0.25 * 0.65)
            prompt = "Prior LAG 35%, observed big river bluff. Posterior with 60%/25% likelihoods?"
        drills.append({
            "id":     f"MATH-{idx + 1:03d}",
            "kind":   kind,
            "prompt": prompt,
            "answer": round(answer, 3),
            "hint":   f"Formula: {kind} — use pot and bet size.",
        })
    return drills


# ───────────────────────────────────────────────────────────────────────────
# Legacy helpers kept for backward-compat with existing screens / tests
# ───────────────────────────────────────────────────────────────────────────

def _bot_adjustment(name: str) -> str:
    if "station" in name.lower():
        return "Value bet thinner, bluff less, punish capped calls."
    if "nit" in name.lower() or "overfolder" in name.lower():
        return "Steal wider and apply small frequent pressure."
    if "maniac" in name.lower() or "overbluffer" in name.lower():
        return "Trap more, bluff-catch with correct blockers, avoid ego wars."
    if "icm" in name.lower():
        return "Pressure medium stacks; avoid doubling them without premium equity."
    return "Stay balanced, then adjust from showdown evidence."


def bot_profiles() -> list[dict]:
    names = [
        ("Nit",                       14, 9, 3, 72, 4, 1.3, 12, 22, 0.25),
        ("Tight passive",             19,11, 4, 61, 5, 1.1,  9, 35, 0.35),
        ("Calling station",           42,14, 3, 28, 3, 0.9,  8, 78, 0.50),
        ("Maniac",                    58,41,18, 34,19, 3.8, 46, 38, 0.72),
        ("Loose aggressive",          34,27,12, 46,14, 3.1, 32, 41, 0.58),
        ("Solid reg",                 24,19, 8, 54,10, 2.4, 24, 43, 0.44),
        ("GTO-style reg",             26,21, 9, 50,11, 2.5, 28, 45, 0.50),
        ("Overfolder",                21,16, 7, 73, 6, 1.8, 15, 20, 0.30),
        ("Overbluffer",               31,24,10, 48,13, 2.9, 48, 31, 0.55),
        ("ICM scared medium stack",   18,13, 5, 68, 5, 1.4, 10, 27, 0.12),
        ("Big stack bully",           39,31,14, 43,16, 3.4, 38, 36, 0.78),
        ("Short stack jam/fold bot",  28,26, 0, 57, 0, 2.0,  0,  0, 0.62),
    ]
    return [
        {
            "name": n, "vpip": vpip, "pfr": pfr, "three_bet": three,
            "fold_to_cbet": fold, "check_raise": xr, "aggression": af,
            "river_bluff": rb, "call_down": cd, "icm_risk_tolerance": icm,
            "tilt_probability": round((vpip + rb) / 220, 2),
            "adjustment": _bot_adjustment(n),
        }
        for n, vpip, pfr, three, fold, xr, af, rb, cd, icm in names
    ]


def tournament_spots() -> list[dict]:
    base   = generate_spot_drills(20)
    stages = ["Bubble", "Final table", "PKO bounty", "Satellite bubble", "Heads-up"]
    spots  = []
    for idx, spot in enumerate(base[:12]):
        stage = stages[idx % len(stages)]
        spots.append({
            **spot,
            "id":          f"TOUR-{idx + 1:03d}",
            "title":       f"{stage}: {spot['position']} {spot['stack_bb']}bb pressure spot",
            "stage":       stage,
            "players_left":  [47, 9, 24, 11, 2][idx % 5],
            "paid_places":   [45, 9, 17, 10, 2][idx % 5],
            "risk_premium":  round(0.05 + (idx % 6) * 0.025, 3),
            "bubble_factor": round(1.15 + (idx % 5) * 0.18, 2),
            "bounty_ev":     round((idx % 4) * 0.35, 2),
            "best_action":   ["fold", "jam", "call", "raise"][idx % 4],
            "options":       ("fold", "call", "raise", "jam"),
        })
    return spots


def leaks() -> list[dict]:
    return [
        {"name": "BB underdefend vs BTN min-raise",      "severity": "High",     "sample_size": 58, "ev_lost": 18.4, "frequency_deviation": "-14%", "why": "Range folds too many suited gappers and wheel Ax hands.", "fix": "Run 7-day BB defend repair drills."},
        {"name": "River overbluff into calling stations", "severity": "Critical", "sample_size": 31, "ev_lost": 26.2, "frequency_deviation": "+19%", "why": "Villain profile has high call-down tendency; blockers ignored.", "fix": "Switch to value-heavy exploit and require nut blockers."},
        {"name": "Final table call-off too loose",        "severity": "High",     "sample_size": 14, "ev_lost": 21.7, "frequency_deviation": "+11%", "why": "chipEV overriding $EV risk premium near pay jumps.", "fix": "ICM bootcamp: medium stack risk premium packs."},
        {"name": "Turn overbarrel on paired boards",      "severity": "Medium",   "sample_size": 44, "ev_lost":  9.5, "frequency_deviation": "+8%",  "why": "Board-pairing turns shift nut advantage toward caller.", "fix": "Classify paired turns before firing second barrel."},
        {"name": "Thin value missed vs capped ranges",    "severity": "Medium",   "sample_size": 39, "ev_lost":  7.8, "frequency_deviation": "-10%", "why": "Showdown-value hands are checked back vs capped range.", "fix": "Run thin value master combat pack."},
    ]


def combat_packs() -> list[dict]:
    names = [
        "Defend your BB", "Stop overfolding rivers", "Punish calling stations",
        "Survive bubble", "Attack medium stacks", "Play vs maniac",
        "Don't punt ICM", "River blocker master", "Thin value master", "Final table boss",
    ]
    return [
        {"name": name, "spots": 20 + idx * 8, "difficulty": ["Bronze","Silver","Gold","Elite"][idx % 4],
         "skill_score": 62 + idx * 3, "boss_hand": f"BOSS-{idx+1:02d}",
         "reward": ["XP +120", "Leak repair badge", "Boss unlock"][idx % 3]}
        for idx, name in enumerate(names)
    ]


def knowledge_cards() -> list[dict]:
    sources = [
        ("MDF under pressure",       "Modern Poker Theory",              "MDF is a defense target, not a command.",             "River Decision Trainer"),
        ("Alpha and auto-profit",     "Poker Mathematics",                "Alpha tells how often a bluff needs folds.",           "Math Lab"),
        ("Bayes opponent update",     "Science of Poker",                 "Update reads gradually via Bayesian inference.",       "AI Coach"),
        ("Solid aggressive baseline", "Super System",                     "Aggression works when paired with hand reading.",      "Combat Trainer"),
        ("Tournament journal review", "Every Hand Revealed",              "Hand-by-hand review reveals compounding effects.",     "Tournament Simulator"),
        ("Tell reliability",          "Caro/Navarro tells",               "Physical tells are probability clues, not certainty.", "Knowledge Base"),
        ("AKQ toy game",              "Thinking Poker Through Game Theory","Toy games isolate bluff/value ratios.",               "Math Lab"),
        ("cEV vs $EV",                "Modern Poker Theory",              "Chip-gaining calls can lose payout equity near bubble.","ICM / PKO Trainer"),
        ("Blocker misuse risk",       "Poker Mathematics",                "Blockers matter only if they change villain's range.", "River Decision Trainer"),
        ("Repetition learning",       "Science of Poker",                 "Fast feedback + spaced repetition beats passive reading.","Study Planner"),
    ]
    return [
        {"concept": c, "source": s, "reference": f"Concept card {i+1}", "summary": sm,
         "application": mod, "related_spots": ["SRP","3BP","ICM"][i % 3],
         "drill_idea": f"Create 10-minute {mod.lower()} drill from this concept.",
         "misuse_risk": "Do not quote long text; use as a short private study abstraction."}
        for i, (c, s, sm, mod) in enumerate(sources)
    ]


def study_plan() -> list[dict]:
    days  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    focus = ["Math reflex + BTN/BB preflop","Flop cbet discipline","Turn barrel control",
             "River blocker decisions","ICM bubble calls","Fast play bot volume","Weekly review"]
    return [
        {"day": day, "focus": focus[i],
         "blocks": ["10 min math reflex","20 min range trainer","30 min postflop drill",
                    "20 min simulator","20 min hand review","10 min AI coach summary"],
         "target": f"{35+i*5} drills / EV loss < {0.55-i*0.04:.2f}bb"}
        for i, day in enumerate(days)
    ]


def dashboard_metrics() -> dict:
    return {
        "daily_goal": "75 drills + 150 fast-play hands",
        "drills_today": 42, "preflop_accuracy": 84, "postflop_accuracy": 71,
        "river_score": 68,  "icm_discipline": 76,   "math_reflex": 81,
        "ev_loss_per_100": 22.6, "skill_score": 742, "streak": 6,
        "progress_7d": [62, 65, 67, 66, 71, 74, 78],
        "expensive_spots": [
            "River overbet call with weak blocker: -3.2bb",
            "Bubble AJo call-off 18bb: -2.7 $EV",
            "Turn paired-board barrel: -1.8bb",
            "BB fold vs BTN min-open: -0.9bb",
            "Missed thin value on river: -0.7bb",
        ],
    }
