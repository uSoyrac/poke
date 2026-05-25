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


def generate_math_drills(count: int = 0) -> list[dict]:
    """Generate comprehensive math drills across 9 poker math categories.

    count=0 (default) returns all drills. Pass count>0 to limit for backward compat.
    """
    drills: list[dict] = []
    _d = ["easy", "easy", "medium", "medium", "hard"]

    # ── 1. POT ODDS (20 drills) ──────────────────────────────────────────
    for idx, (pot, bet) in enumerate([
        (10, 4), (20, 8), (15, 6), (30, 10), (25, 7),
        (40, 15), (8, 3), (50, 18), (12, 5), (35, 12),
        (60, 22), (18, 7), (45, 16), (22, 9), (70, 25),
        (9, 4), (28, 11), (55, 20), (16, 6), (38, 14),
    ]):
        answer = round(bet / (pot + 2 * bet), 3)
        drills.append({
            "id": f"MATH-PO-{idx+1:02d}", "kind": "pot_odds", "category": "pot_odds",
            "difficulty": _d[idx % 5],
            "prompt": f"Pot {pot}bb. Villain bets {bet}bb. Minimum equity to call?",
            "answer": answer, "tolerance": 0.025,
            "explanation": f"call / (pot + 2×call) = {bet} / {pot + 2*bet} = {answer:.3f} ({answer*100:.1f}%)",
            "formula": "equity = call / (pot + 2×call)",
        })

    # ── 2. ALPHA — required fold equity (20 drills) ──────────────────────
    for idx, (pot, bet) in enumerate([
        (10, 4), (20, 8), (15, 6), (30, 10), (25, 7),
        (40, 15), (8, 3), (50, 18), (12, 5), (35, 12),
        (60, 22), (18, 7), (45, 16), (22, 9), (70, 25),
        (9, 4), (28, 11), (55, 20), (16, 6), (38, 14),
    ]):
        answer = round(bet / (bet + pot), 3)
        drills.append({
            "id": f"MATH-AL-{idx+1:02d}", "kind": "alpha", "category": "alpha",
            "difficulty": _d[idx % 5],
            "prompt": f"You bluff {bet}bb into a {pot}bb pot. Required fold frequency for immediate profit?",
            "answer": answer, "tolerance": 0.025,
            "explanation": f"alpha = bet / (bet + pot) = {bet} / {bet + pot} = {answer:.3f} ({answer*100:.1f}%)",
            "formula": "alpha = bet / (bet + pot)",
        })

    # ── 3. MDF — minimum defense frequency (20 drills) ───────────────────
    for idx, (pot, bet) in enumerate([
        (10, 4), (20, 8), (15, 6), (30, 10), (25, 7),
        (40, 15), (8, 3), (50, 18), (12, 5), (35, 12),
        (60, 22), (18, 7), (45, 16), (22, 9), (70, 25),
        (9, 4), (28, 11), (55, 20), (16, 6), (38, 14),
    ]):
        alpha = bet / (bet + pot)
        answer = round(1 - alpha, 3)
        drills.append({
            "id": f"MATH-MDF-{idx+1:02d}", "kind": "mdf", "category": "mdf",
            "difficulty": _d[idx % 5],
            "prompt": f"Villain bets {bet}bb into {pot}bb. Your minimum defense frequency (MDF)?",
            "answer": answer, "tolerance": 0.025,
            "explanation": f"MDF = 1 − alpha = 1 − {alpha:.3f} = {answer:.3f} ({answer*100:.1f}%). Defend at least {answer*100:.0f}%.",
            "formula": "MDF = pot / (pot + bet) = 1 − alpha",
        })

    # ── 4. EXPECTED VALUE (15 drills) ─────────────────────────────────────
    for idx, (win_pct, pot, risk) in enumerate([
        (0.45, 20, 8), (0.30, 30, 12), (0.55, 15, 6), (0.38, 25, 10), (0.62, 40, 15),
        (0.25, 50, 20), (0.50, 10, 4), (0.35, 35, 12), (0.70, 8, 3), (0.42, 60, 22),
        (0.28, 18, 7), (0.60, 45, 16), (0.33, 22, 9), (0.48, 70, 25), (0.40, 28, 11),
    ]):
        lose_pct = round(1 - win_pct, 2)
        answer = round(win_pct * pot - lose_pct * risk, 2)
        drills.append({
            "id": f"MATH-EV-{idx+1:02d}", "kind": "ev", "category": "ev",
            "difficulty": ["easy", "medium", "medium", "hard", "hard"][idx % 5],
            "prompt": f"Win {win_pct*100:.0f}% · pot reward {pot}bb · risk {risk}bb. EV of the call?",
            "answer": answer, "tolerance": 0.30,
            "explanation": f"EV = {win_pct}×{pot} − {lose_pct}×{risk} = {win_pct*pot:.2f} − {lose_pct*risk:.2f} = {answer:+.2f}bb",
            "formula": "EV = win% × reward − lose% × risk",
        })

    # ── 5. ICM MATH (15 drills) ───────────────────────────────────────────
    icm_data = [
        (20, 30, 9, 15, 20, 0.04), (15, 25, 6, 12, 15, 0.06), (10, 20, 4, 8, 10, 0.06),
        (30, 25, 5, 20, 30, 0.02), (8,  20, 3, 7,  8,  0.08), (25, 30, 7, 18, 25, 0.03),
        (40, 25, 4, 30, 40, 0.01), (12, 22, 5, 10, 12, 0.06), (18, 28, 6, 14, 18, 0.04),
        (35, 30, 3, 25, 35, 0.02), (22, 25, 8, 16, 22, 0.03), (16, 20, 4, 12, 16, 0.05),
        (28, 30, 5, 22, 28, 0.03), (14, 25, 9, 10, 14, 0.05), (45, 30, 3, 35, 45, 0.01),
    ]
    for idx, (h, avg, players, pot, call, premium) in enumerate(icm_data):
        chip_eq = round(call / (pot + 2 * call), 3)
        answer = round(chip_eq + premium, 3)
        drills.append({
            "id": f"MATH-ICM-{idx+1:02d}", "kind": "icm", "category": "icm",
            "difficulty": ["medium", "hard", "hard"][idx % 3],
            "prompt": (
                f"Hero {h}bb · avg {avg}bb · {players} players left. "
                f"Villain jams {call}bb into {pot}bb. chipEV equity = {chip_eq:.1%}. "
                f"Minimum equity with ~{premium:.0%} ICM risk premium?"
            ),
            "answer": answer, "tolerance": 0.035,
            "explanation": f"chipEV requires {chip_eq:.1%}. ICM risk premium ≈{premium:.0%} → total {answer:.1%}. Tighten ranges near pay jumps.",
            "formula": "ICM equity = chipEV equity + risk_premium",
        })

    # ── 6. COMBOS (15 drills) ──────────────────────────────────────────────
    for idx, (prompt, answer, explanation) in enumerate([
        ("Pocket Aces (AA) — how many combinations?", 6.0,
         "C(4,2) = 6. Four aces choose two."),
        ("AKo offsuit — how many combinations?", 12.0,
         "4 aces × 4 kings = 16 total. Minus 4 suited = 12 offsuit."),
        ("AKs suited — how many combinations?", 4.0,
         "One per suit: Ah-Kh, Ad-Kd, Ac-Kc, As-Ks = 4."),
        ("AK total (suited + offsuit) — how many combos?", 16.0,
         "AKs (4) + AKo (12) = 16 total combos."),
        ("KK with one King on the board — how many KK combos remain?", 3.0,
         "3 remaining kings: C(3,2) = 3."),
        ("JTs (suited connectors) — how many combinations?", 4.0,
         "4 suits: Jh-Th, Jd-Td, Jc-Tc, Js-Ts = 4."),
        ("All pocket pairs (22–AA) combined — total combos?", 78.0,
         "13 pairs × 6 combos each = 78."),
        ("QQ with Qh on the board — remaining QQ combos?", 3.0,
         "3 remaining queens: C(3,2) = 3."),
        ("All suited Ace-X combos (Ax suited, 12 possible partners) — total?", 48.0,
         "12 non-ace ranks × 4 suits = 48 suited ace combos."),
        ("AA with Ah in your hand — remaining AA combos villain can have?", 3.0,
         "3 remaining aces: C(3,2) = 3."),
        ("Total two-card combinations from a full deck (52 cards)?", 1326.0,
         "C(52,2) = 52×51/2 = 1326."),
        ("TT on a K-7-2 board (no tens removed) — how many TT combos?", 6.0,
         "No board blockers on tens: C(4,2) = 6."),
        ("54s — how many suited combinations?", 4.0,
         "4 suits: 5h-4h, 5d-4d, 5c-4c, 5s-4s = 4."),
        ("Any offsuit unpaired hand — how many offsuit combos?", 12.0,
         "4×4 = 16 total. Minus 4 suited = 12 offsuit."),
        ("KQo with Kh on the board — remaining KQo combos?", 9.0,
         "3 remaining kings × 4 queens − same-suit pairs = 3×4 − 3 = 9."),
    ]):
        drills.append({
            "id": f"MATH-CB-{idx+1:02d}", "kind": "combos", "category": "combos",
            "difficulty": _d[idx % 5],
            "prompt": prompt, "answer": float(answer), "tolerance": 0.5,
            "explanation": explanation,
            "formula": "Pairs: C(4,2)=6 · Suited: 4 · Offsuit: 12 · Total: 16",
        })

    # ── 7. PUSH / FOLD (15 drills) ────────────────────────────────────────
    for idx, (prompt, answer, explanation) in enumerate([
        ("10bb stack, AJs from CO. Jam equity vs typical CO calling range?", 0.68,
         "AJs at 10bb from CO: ≈68% equity vs CO calling range. Clear jam."),
        ("8bb stack, K9s from BTN. Push equity vs BB defend?", 0.62,
         "K9s at 8bb BTN: ≈62% vs BB defend range — standard push."),
        ("12bb stack, 22 from CO. Approximate equity vs calling range?", 0.52,
         "22 at 12bb: ≈52% vs CO calling range — marginal jam."),
        ("7bb stack, A5o from SB. Jam equity vs BB defense?", 0.58,
         "A5o at 7bb SB vs BB: ≈58% vs BB defend — push."),
        ("15bb stack, QQ facing UTG open. Jam equity?", 0.80,
         "QQ at 15bb vs UTG open: ≈80%+ equity — always jam."),
        ("9bb, KJo from UTG. Fold or shove? Equity vs UTG calling range?", 0.55,
         "KJo at 9bb UTG: ≈55% vs UTG calling range — marginal."),
        ("6bb vs fold-happy BB. Approximate profitable push frequency?", 0.70,
         "At 6bb vs tight BB: push ≈70%+ of hands for fold equity."),
        ("11bb, JTs from CO. Push equity vs typical calling range?", 0.62,
         "JTs at 11bb CO: ≈62% vs calling range — profitable push."),
        ("13bb, A2s from SB. Jam equity vs BB?", 0.56,
         "A2s at 13bb SB: ≈56% vs BB defend — push."),
        ("8bb, 88 from UTG. Equity vs UTG calling range?", 0.70,
         "88 at 8bb UTG: ≈70% equity — clear jam."),
        ("20bb, AQo facing BTN open. Rejam equity?", 0.62,
         "AQo 3bet jam at 20bb vs BTN opening range: ≈62% — profitable."),
        ("5bb stack from SB — profitable push frequency vs BB?", 0.75,
         "At 5bb any two from SB: ≈75%+ profitable vs most BB defenses."),
        ("16bb, TT facing UTG open. Jam equity?", 0.72,
         "TT at 16bb vs UTG open: ≈72% equity — jam."),
        ("10bb, J9s from BTN. Push equity vs calling range?", 0.58,
         "J9s at 10bb BTN: ≈58% vs calling range — marginal push."),
        ("14bb, AKo. Jam equity vs most calling ranges?", 0.68,
         "AKo at 14bb: ≈68% equity vs most calling ranges — always jam."),
    ]):
        drills.append({
            "id": f"MATH-PF-{idx+1:02d}", "kind": "push_fold", "category": "push_fold",
            "difficulty": ["easy", "medium", "medium", "hard", "hard"][idx % 5],
            "prompt": prompt, "answer": answer, "tolerance": 0.10,
            "explanation": explanation,
            "formula": "Equity vs calling range (ICM stack depth + position + hand strength)",
        })

    # ── 8. GTO FREQUENCY (15 drills) ─────────────────────────────────────
    for idx, (prompt, answer, tolerance, explanation) in enumerate([
        ("You bet 50% pot. GTO bluff% of your betting range?", 0.333, 0.05,
         "50% pot bet: caller needs 25% equity. Bluff% ≈ 33% of betting range."),
        ("You bet 100% pot (1× pot). GTO bluff%?", 0.50, 0.05,
         "1× pot: caller needs 33% equity. Bluff% = 50% for GTO indifference."),
        ("You bet 33% pot. GTO bluff%?", 0.20, 0.05,
         "33% pot: caller needs 20% equity. Bluff% ≈ 20%."),
        ("You bet 75% pot. GTO bluff%?", 0.43, 0.05,
         "75% pot: caller needs 30% equity. Bluff% ≈ 43%."),
        ("You bet 150% pot (overbet). GTO bluff%?", 0.60, 0.05,
         "150% pot: caller needs 37.5% equity. Bluff% ≈ 60%."),
        ("12 value combos betting 50% pot. Balanced bluff count?", 4.0, 0.6,
         "50% pot: 1 bluff per 3 combos (bluff 25%). 12/3 = 4 bluffs."),
        ("9 value combos betting 100% pot. Balanced bluff count?", 9.0, 0.6,
         "1× pot: equal bluffs to value (50%). 9 bluffs."),
        ("18 value combos betting 33% pot. Balanced bluffs?", 4.0, 0.6,
         "33% pot: bluff% ≈ 20%. 18 × 0.25 ≈ 4–5 bluffs."),
        ("Villain bets 50% pot. Your MDF? (decimal)", 0.667, 0.03,
         "MDF = pot / (pot + bet) = 1/(1 + 0.5) = 0.667."),
        ("Villain bets 100% pot. Your MDF?", 0.50, 0.03,
         "MDF = pot / (pot + bet) = 1/(1 + 1) = 0.50."),
        ("Villain bets 75% pot. Your MDF?", 0.571, 0.03,
         "MDF = 1 / (1 + 0.75) = 0.571 (57.1%)."),
        ("River bet at 67% pot. Your MDF?", 0.60, 0.03,
         "MDF = 1 / (1 + 0.667) = 0.60 (60%)."),
        ("Value:bluff ratio for 50% pot betting?", 2.0, 0.3,
         "Bluff% = 33%, value% = 67%. Ratio = 2 value per bluff."),
        ("Overbet 2× pot. GTO bluff%?", 0.67, 0.05,
         "2× pot: caller needs 40% equity. Bluff% ≈ 67%."),
        ("Facing river bet. Pot 40bb, bet 20bb. Your MDF?", 0.667, 0.03,
         "MDF = 40 / (40 + 20) = 40/60 = 0.667."),
    ]):
        drills.append({
            "id": f"MATH-GTO-{idx+1:02d}", "kind": "gto_freq", "category": "gto_freq",
            "difficulty": _d[idx % 5],
            "prompt": prompt, "answer": answer, "tolerance": tolerance,
            "explanation": explanation,
            "formula": "MDF = pot / (pot + bet) · Bluff% = bet / (pot + 2×bet)",
        })

    # ── 9. BAYES UPDATE (15 drills) ───────────────────────────────────────
    def _bayes(p_e_h: float, p_h: float, p_e_nh: float) -> float:
        return round(p_e_h * p_h / (p_e_h * p_h + p_e_nh * (1 - p_h)), 3)

    for idx, (prompt, answer, tolerance, explanation) in enumerate([
        ("Prior P(bluff)=35%. Aggressive line: 60% likely if bluff, 15% if value. Posterior P(bluff)?",
         _bayes(0.60, 0.35, 0.15), 0.04,
         f"P(bluff|obs) = 0.60×0.35 / (0.60×0.35 + 0.15×0.65) = {_bayes(0.60, 0.35, 0.15):.3f}"),
        ("Prior P(strong)=40%. River bet: 70% if strong, 30% if weak. P(strong|bet)?",
         _bayes(0.70, 0.40, 0.30), 0.04,
         f"P(strong|bet) = 0.70×0.40 / (0.70×0.40 + 0.30×0.60) = {_bayes(0.70, 0.40, 0.30):.3f}"),
        ("Prior P(bluff)=50%. Overbet river: 80% if bluff, 20% if value. P(bluff)?",
         _bayes(0.80, 0.50, 0.20), 0.04,
         f"P(bluff|overbet) = 0.80×0.50 / (0.80×0.50 + 0.20×0.50) = {_bayes(0.80, 0.50, 0.20):.3f}"),
        ("Prior P(fish)=25%. Limps multiway: 70% if fish, 20% if reg. P(fish)?",
         _bayes(0.70, 0.25, 0.20), 0.04,
         f"P(fish|limp) = 0.70×0.25 / (0.70×0.25 + 0.20×0.75) = {_bayes(0.70, 0.25, 0.20):.3f}"),
        ("Prior P(value)=60%. Check-raise river: 30% if value, 70% if bluff. P(value)?",
         _bayes(0.30, 0.60, 0.70), 0.04,
         f"P(value|XR) = 0.30×0.60 / (0.30×0.60 + 0.70×0.40) = {_bayes(0.30, 0.60, 0.70):.3f}"),
        ("Prior P(strong)=30%. Turn check: 5% if strong, 60% if weak. P(strong|check)?",
         _bayes(0.05, 0.30, 0.60), 0.04,
         f"P(strong|check) = {_bayes(0.05, 0.30, 0.60):.3f}. Slow-playing is rare evidence."),
        ("Prior P(bluff)=45%. Fast bet timing: 55% if bluff, 35% if value. P(bluff)?",
         _bayes(0.55, 0.45, 0.35), 0.04,
         f"P(bluff|fast) = {_bayes(0.55, 0.45, 0.35):.3f}. Timing tells need weighting by sample."),
        ("Prior P(pair)=55%. Villain checks flop twice: 80% if pair, 30% if draw. P(pair)?",
         _bayes(0.80, 0.55, 0.30), 0.04,
         f"P(pair|check×2) = {_bayes(0.80, 0.55, 0.30):.3f}"),
        ("Prior P(nuts)=10%. River jam: 90% if nuts, 20% if bluff. P(nuts|jam)?",
         _bayes(0.90, 0.10, 0.20), 0.04,
         f"P(nuts|jam) = {_bayes(0.90, 0.10, 0.20):.3f}. Low prior matters."),
        ("Prior P(draw)=40%. Turn raise: 60% if draw, 5% if made. P(draw|raise)?",
         _bayes(0.60, 0.40, 0.05), 0.04,
         f"P(draw|raise) = {_bayes(0.60, 0.40, 0.05):.3f}. Raises heavily suggest draws on this texture."),
        ("Prior P(bluff)=30%. Second barrel: 65% if bluff, 45% if value. P(bluff)?",
         _bayes(0.65, 0.30, 0.45), 0.04,
         f"P(bluff|barrel) = {_bayes(0.65, 0.30, 0.45):.3f}"),
        ("50/50 prior bluff/value. River bet equally likely from both. Posterior P(bluff)?",
         0.50, 0.04,
         "Equal likelihoods → Bayes does not update. P(bluff) stays 0.50."),
        ("Prior P(strong)=35%. Tank then check: 10% if strong, 70% if weak. P(strong)?",
         _bayes(0.10, 0.35, 0.70), 0.04,
         f"P(strong|tank-check) = {_bayes(0.10, 0.35, 0.70):.3f}. Tank-then-check is a weak signal."),
        ("Prior P(nit)=20%. Villain 3bets: 10% if nit, 40% if non-nit. P(nit|3bet)?",
         _bayes(0.10, 0.20, 0.40), 0.04,
         f"P(nit|3bet) = {_bayes(0.10, 0.20, 0.40):.3f}. 3bets are anti-evidence of nit."),
        ("Prior P(bluff)=40%. Villain shows 3 bluffs this session: 60% bluff, 30% value likelihood. P(bluff)?",
         _bayes(0.60, 0.40, 0.30), 0.04,
         f"Evidence of bluffing: P(bluff) → {_bayes(0.60, 0.40, 0.30):.3f}. Update gradually."),
    ]):
        drills.append({
            "id": f"MATH-BY-{idx+1:02d}", "kind": "bayes", "category": "bayes",
            "difficulty": ["medium", "medium", "hard", "hard", "hard"][idx % 5],
            "prompt": prompt, "answer": round(answer, 3), "tolerance": tolerance,
            "explanation": explanation,
            "formula": "P(H|E) = P(E|H)·P(H) / [P(E|H)·P(H) + P(E|¬H)·P(¬H)]",
        })

    if count and count < len(drills):
        return drills[:count]
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

