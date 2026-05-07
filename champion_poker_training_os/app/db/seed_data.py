from __future__ import annotations

from itertools import cycle


POSITIONS = ["UTG", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
STREETS = ["preflop", "flop", "turn", "river"]
FORMATS = ["cash", "MTT", "SNG", "PKO", "heads-up"]
POT_TYPES = ["SRP", "3BP", "4BP", "limped", "multiway"]
BOARD_TEXTURES = [
    "A-high dry",
    "K-high dynamic",
    "low connected",
    "paired",
    "monotone",
    "two-tone",
    "flush-completing river",
]
HANDS = ["AsKh", "QdQs", "JhTh", "8s8c", "Ac5c", "KdQd", "7h6h", "AdJc", "Ts9s", "5d5c"]
BOARDS = ["Ah7c2d", "KsQh8s", "9s8s4d", "QcQd3h", "Jc7c2c", "Td9h4h", "AsKd4s2c9h"]
OPTIONS = [
    ("fold", "call", "raise", "jam"),
    ("check", "bet small", "bet medium", "bet large"),
    ("fold", "call", "raise"),
    ("check", "call", "raise", "jam"),
]


def generate_spot_drills(count: int = 120) -> list[dict]:
    drills: list[dict] = []
    option_cycle = cycle(OPTIONS)
    for idx in range(count):
        street = STREETS[idx % len(STREETS)]
        options = next(option_cycle)
        best_action = options[(idx * 2 + 1) % len(options)]
        stack = [10, 15, 20, 25, 40, 60, 100, 200][idx % 8]
        pot = round(3.5 + (idx % 9) * 2.25, 1)
        drills.append(
            {
                "id": f"SPOT-{idx + 1:03d}",
                "title": f"{street.title()} {POSITIONS[idx % 7]} decision vs {['nit', 'reg', 'station', 'maniac'][idx % 4]}",
                "format": FORMATS[idx % len(FORMATS)],
                "table": ["6-max", "9-max", "HU"][idx % 3],
                "street": street,
                "position": POSITIONS[idx % len(POSITIONS)],
                "stack_bb": stack,
                "pot_bb": pot,
                "hero_cards": HANDS[idx % len(HANDS)],
                "board": "" if street == "preflop" else BOARDS[idx % len(BOARDS)],
                "board_texture": BOARD_TEXTURES[idx % len(BOARD_TEXTURES)],
                "pot_type": POT_TYPES[idx % len(POT_TYPES)],
                "action_history": _action_history(idx, street),
                "options": options,
                "best_action": best_action,
                "base_ev": round(0.85 + (idx % 6) * 0.18, 2),
                "range_advantage": ["Hero + range", "Villain + range", "Neutral ranges"][idx % 3],
                "nut_advantage": ["Hero nut advantage", "Villain nut advantage", "Shared nut density"][idx % 3],
                "icm": ["off", "bubble", "final table", "satellite", "PKO"][idx % 5],
                "source_confidence": ["Mock/demo solver", "Pre-solved library", "Rule-based heuristic"][idx % 3],
            }
        )
    return drills


def generate_hands(count: int = 100) -> list[dict]:
    hands: list[dict] = []
    drills = generate_spot_drills(count)
    for idx, drill in enumerate(drills):
        hands.append(
            {
                "id": f"HAND-{idx + 1:04d}",
                "table": f"Demo Lab {idx % 12 + 1}",
                "format": drill["format"],
                "hero": "Hero",
                "villain": ["SolverReg", "Station42", "ICMScared", "BarrelBot"][idx % 4],
                "hero_cards": drill["hero_cards"],
                "board": drill["board"] or "preflop",
                "position": drill["position"],
                "result_bb": round(((idx % 11) - 5) * 1.7, 1),
                "ev_loss": round((idx % 9) * 0.12, 2),
                "biggest_mistake": ["overfold", "thin value missed", "bad bluffcatch", "ICM punt"][idx % 4],
                "timeline": [
                    "Preflop: Hero opens 2.2bb",
                    "Flop: Villain checks, Hero bets 33%",
                    "Turn: Villain calls, Hero evaluates range shift",
                    "River: Decision node marked for review",
                ],
                "spot": drill,
            }
        )
    return hands


def generate_math_drills(count: int = 30) -> list[dict]:
    drills: list[dict] = []
    for idx in range(count):
        kind = ["pot odds", "alpha", "MDF", "EV", "Bayes"][idx % 5]
        pot = 10 + idx * 2
        bet = 4 + (idx % 7)
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
        drills.append(
            {
                "id": f"MATH-{idx + 1:03d}",
                "kind": kind,
                "prompt": prompt,
                "answer": round(answer, 3),
                "tolerance": 0.035 if kind != "EV" else 0.15,
                "explanation": _math_explanation(kind),
            }
        )
    return drills


def bot_profiles() -> list[dict]:
    names = [
        ("Nit", 14, 9, 3, 72, 4, 1.3, 12, 22, 0.25),
        ("Tight passive", 19, 11, 4, 61, 5, 1.1, 9, 35, 0.35),
        ("Calling station", 42, 14, 3, 28, 3, 0.9, 8, 78, 0.50),
        ("Maniac", 58, 41, 18, 34, 19, 3.8, 46, 38, 0.72),
        ("Loose aggressive", 34, 27, 12, 46, 14, 3.1, 32, 41, 0.58),
        ("Solid reg", 24, 19, 8, 54, 10, 2.4, 24, 43, 0.44),
        ("GTO-style reg", 26, 21, 9, 50, 11, 2.5, 28, 45, 0.50),
        ("Overfolder", 21, 16, 7, 73, 6, 1.8, 15, 20, 0.30),
        ("Overbluffer", 31, 24, 10, 48, 13, 2.9, 48, 31, 0.55),
        ("ICM scared medium stack", 18, 13, 5, 68, 5, 1.4, 10, 27, 0.12),
        ("Big stack bully", 39, 31, 14, 43, 16, 3.4, 38, 36, 0.78),
        ("Short stack jam/fold bot", 28, 26, 0, 57, 0, 2.0, 0, 0, 0.62),
    ]
    return [
        {
            "name": n,
            "vpip": vpip,
            "pfr": pfr,
            "three_bet": three,
            "fold_to_cbet": fold,
            "check_raise": xr,
            "aggression": af,
            "river_bluff": rb,
            "call_down": cd,
            "icm_risk_tolerance": icm,
            "tilt_probability": round((vpip + rb) / 220, 2),
            "adjustment": _bot_adjustment(n),
        }
        for n, vpip, pfr, three, fold, xr, af, rb, cd, icm in names
    ]


def tournament_spots() -> list[dict]:
    base = generate_spot_drills(20)
    stages = ["Bubble", "Final table", "PKO bounty", "Satellite bubble", "Heads-up"]
    spots = []
    for idx, spot in enumerate(base[:12]):
        stage = stages[idx % len(stages)]
        spots.append(
            {
                **spot,
                "id": f"TOUR-{idx + 1:03d}",
                "title": f"{stage}: {spot['position']} {spot['stack_bb']}bb pressure spot",
                "stage": stage,
                "players_left": [47, 9, 24, 11, 2][idx % 5],
                "paid_places": [45, 9, 17, 10, 2][idx % 5],
                "risk_premium": round(0.05 + (idx % 6) * 0.025, 3),
                "bubble_factor": round(1.15 + (idx % 5) * 0.18, 2),
                "bounty_ev": round((idx % 4) * 0.35, 2),
                "best_action": ["fold", "jam", "call", "raise"][idx % 4],
                "options": ("fold", "call", "raise", "jam"),
            }
        )
    return spots


def leaks() -> list[dict]:
    return [
        {
            "name": "BB underdefend vs BTN min-raise",
            "severity": "High",
            "sample_size": 58,
            "ev_lost": 18.4,
            "frequency_deviation": "-14%",
            "why": "Range folds too many suited gappers and wheel Ax hands with enough equity.",
            "fix": "Run 7-day BB defend repair: 15bb, 25bb and 40bb defend drills.",
        },
        {
            "name": "River overbluff into calling stations",
            "severity": "Critical",
            "sample_size": 31,
            "ev_lost": 26.2,
            "frequency_deviation": "+19%",
            "why": "Villain profile has high call-down tendency; blocker logic is ignored.",
            "fix": "Switch to value-heavy exploit and require nut blockers before large river bluffs.",
        },
        {
            "name": "Final table call-off too loose",
            "severity": "High",
            "sample_size": 14,
            "ev_lost": 21.7,
            "frequency_deviation": "+11%",
            "why": "chipEV instincts are overriding $EV risk premium near pay jumps.",
            "fix": "ICM bootcamp: medium stack risk premium and big stack pressure packs.",
        },
        {
            "name": "Turn overbarrel on paired boards",
            "severity": "Medium",
            "sample_size": 44,
            "ev_lost": 9.5,
            "frequency_deviation": "+8%",
            "why": "Board-pairing turns shift nut advantage toward caller range.",
            "fix": "Classify paired turns before firing second barrel.",
        },
        {
            "name": "Thin value missed vs capped ranges",
            "severity": "Medium",
            "sample_size": 39,
            "ev_lost": 7.8,
            "frequency_deviation": "-10%",
            "why": "Showdown-value hands are checked back when villain has capped bluff-catcher range.",
            "fix": "Run thin value master combat pack for river half-pot bets.",
        },
    ]


def combat_packs() -> list[dict]:
    names = [
        "Defend your BB",
        "Stop overfolding rivers",
        "Punish calling stations",
        "Survive bubble",
        "Attack medium stacks",
        "Play vs maniac",
        "Don't punt ICM",
        "River blocker master",
        "Thin value master",
        "Final table boss",
    ]
    return [
        {
            "name": name,
            "spots": 20 + idx * 8,
            "difficulty": ["Bronze", "Silver", "Gold", "Elite"][idx % 4],
            "skill_score": 62 + idx * 3,
            "boss_hand": f"BOSS-{idx + 1:02d}",
            "reward": ["XP +120", "Leak repair badge", "Boss unlock"][idx % 3],
        }
        for idx, name in enumerate(names)
    ]


def knowledge_cards() -> list[dict]:
    sources = [
        ("MDF under pressure", "Modern Poker Theory", "MDF is a defense target, not a command. Use it with range shape, blockers and opponent incentives. In ICM nodes, survival pressure can lower profitable defense frequency.", "River Decision Trainer"),
        ("Alpha and auto-profit", "Poker Mathematics", "Risk divided by risk plus reward tells how often a bluff needs folds. When villain overfolds above alpha, bluffing prints. When villain underfolds, shift value-heavy.", "Math Lab"),
        ("Bayes opponent update", "Science of Poker", "One showdown is evidence, not proof. Update priors gradually by weighting reliability, situation and sample size. The best exploit is a probability update, not a label.", "AI Coach"),
        ("Solid aggressive baseline", "Super System", "Aggression is strongest when paired with hand reading and discipline. Blind pressure and position create fold equity. Random aggression without target selection becomes spew.", "Combat Trainer"),
        ("Tournament journal review", "Every Hand Revealed", "Hand-by-hand review reveals how table image and stack pressure compound. Record key inflection spots, not only bustout hands. Use repeated review to calibrate aggression.", "Tournament Simulator"),
        ("Tell reliability", "Caro/Navarro tells", "Physical or timing tells are probability clues. They need weighting by player, context and consistency. Never let a weak tell override math in a large pot.", "Knowledge Base"),
        ("AKQ toy game", "Thinking Poker Through Game Theory", "Toy games isolate bluff/value ratios and indifference. They train why mixed strategies exist. Use them to understand solver outputs before memorizing charts.", "Math Lab"),
        ("cEV vs $EV", "Modern Poker Theory", "A chip-gaining call can lose payout equity near bubbles. Risk premium grows for medium stacks and shrinks for covering stacks. This is the heart of ICM discipline.", "ICM / PKO Trainer"),
        ("Blocker misuse risk", "Poker Mathematics", "A blocker matters only if it changes villain's continuing range. Bad players often cite blockers to justify low fold-equity bluffs. Pair blockers with node incentives.", "River Trainer"),
        ("Repetition learning", "Science of Poker", "Fast feedback plus spaced repetition beats passive reading. Convert mistakes into small drill packs. Measure trend lines, not mood after one session.", "Study Planner"),
    ]
    return [
        {
            "concept": concept,
            "source": source,
            "reference": f"Concept card {idx + 1}",
            "summary": summary,
            "application": module,
            "related_spots": ["SRP", "3BP", "ICM"][idx % 3],
            "drill_idea": f"Create 10-minute {module.lower()} drill from this concept.",
            "misuse_risk": "Do not quote long book text; use as a short private study abstraction.",
        }
        for idx, (concept, source, summary, module) in enumerate(sources)
    ]


def study_plan() -> list[dict]:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    focus = [
        "Math reflex + BTN/BB preflop",
        "Flop cbet discipline",
        "Turn barrel control",
        "River blocker decisions",
        "ICM bubble calls",
        "Fast play bot volume",
        "Weekly review and leak repair",
    ]
    return [
        {
            "day": day,
            "focus": focus[idx],
            "blocks": [
                "10 min math reflex",
                "20 min range trainer",
                "30 min postflop drill",
                "20 min simulator",
                "20 min hand review",
                "10 min AI coach summary",
            ],
            "target": f"{35 + idx * 5} drills / EV loss < {0.55 - idx * 0.04:.2f}bb",
        }
        for idx, day in enumerate(days)
    ]


def dashboard_metrics() -> dict:
    return {
        "daily_goal": "75 drills + 150 fast-play hands",
        "drills_today": 42,
        "preflop_accuracy": 84,
        "postflop_accuracy": 71,
        "river_score": 68,
        "icm_discipline": 76,
        "math_reflex": 81,
        "ev_loss_per_100": 22.6,
        "skill_score": 742,
        "streak": 6,
        "progress_7d": [62, 65, 67, 66, 71, 74, 78],
        "expensive_spots": [
            "River overbet call with weak blocker: -3.2bb",
            "Bubble AJo call-off 18bb: -2.7 $EV",
            "Turn paired-board barrel: -1.8bb",
            "BB fold vs BTN min-open: -0.9bb",
            "Missed thin value on river: -0.7bb",
        ],
    }


def _action_history(idx: int, street: str) -> str:
    lines = {
        "preflop": ["CO opens 2.2bb, BTN folds, Hero in BB", "HJ opens, CO calls, Hero on BTN"],
        "flop": ["BTN opens, BB calls. Flop checks to BTN", "CO opens, BB calls. BB checks flop"],
        "turn": ["Flop bet-call. Turn changes nut advantage", "Flop checks through. Turn probe spot"],
        "river": ["Bet-call flop, bet-call turn. River decision", "Missed draw arrives at river bluff-catch node"],
    }
    return lines[street][idx % 2]


def _math_explanation(kind: str) -> str:
    return {
        "pot odds": "Pot odds = call / final pot. Convert to percent and compare with equity.",
        "alpha": "Alpha = risk / (risk + reward). Villain must fold this often for immediate profit.",
        "MDF": "MDF = 1 - alpha. It is a baseline defense target, not a forced call rule.",
        "EV": "EV = win% * reward - lose% * risk. Positive EV decisions compound over volume.",
        "Bayes": "Posterior = likelihood * prior / total evidence. Update reads gradually.",
    }[kind]


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

