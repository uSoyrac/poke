"""Real PokerStars hand history parser.

Handles standard PokerStars-format hand histories (cash, MTT, SnG) and
the simplified demo format used in sample_data/. Returns a list of
normalized dicts ready for the imported_hands table.
"""
from __future__ import annotations

import re
from typing import Optional


# Header: PokerStars Hand #240123456789:  Tournament #..., $5+$0.50 USD Hold'em No Limit - Level VIII (75/150) - 2024/01/15 19:35:21 ET
HEADER_RE = re.compile(
    r"PokerStars\s+(?:Hand|Game)\s+#(?P<hid>[A-Za-z0-9-]+):\s*"
    r"(?P<format>.*?)\s*-\s*(?P<date>\d{4}/\d{2}/\d{2}.*?ET)?",
    re.IGNORECASE,
)
# Demo header fallback: PokerStars Hand #DEMO-0001: Tournament #ChampionLab, Hold'em No Limit - Level IX
DEMO_HEADER_RE = re.compile(
    r"PokerStars\s+Hand\s+#(?P<hid>[A-Za-z0-9-]+):\s*(?P<format>[^.\n]+)",
    re.IGNORECASE,
)
TABLE_RE = re.compile(
    r"Table\s+'[^']+'\s+(?P<size>\d+)-?max.*Seat\s+#(?P<btn>\d+)\s+is the button",
    re.IGNORECASE,
)
SEAT_RE = re.compile(
    r"Seat\s+(?P<seat>\d+):\s+(?P<name>[^()]+?)\s+\(\$?(?P<chips>[\d,.]+)\s*(?:in\s+chips)?\)",
)
SB_RE = re.compile(r"^(?P<name>.+?):\s*posts\s+small\s+blind\s+\$?(?P<amt>[\d.,]+)", re.IGNORECASE)
BB_RE = re.compile(r"^(?P<name>.+?):\s*posts\s+big\s+blind\s+\$?(?P<amt>[\d.,]+)", re.IGNORECASE)
ANTE_RE = re.compile(r"posts\s+(?:the\s+)?ante\s+\$?(?P<amt>[\d.,]+)", re.IGNORECASE)
HOLE_RE = re.compile(r"Dealt\s+to\s+(?P<name>.+?)\s+\[(?P<cards>[^\]]+)\]", re.IGNORECASE)
ACTION_RE = re.compile(
    r"^(?P<name>.+?):\s*(?P<verb>folds|checks|calls|bets|raises|all-in)\b"
    r"(?:\s+\$?(?P<amt>[\d.,]+))?(?:\s+to\s+\$?(?P<to>[\d.,]+))?",
    re.IGNORECASE,
)
STREET_RE = re.compile(
    r"\*\*\*\s+(?P<street>FLOP|TURN|RIVER|SHOW DOWN|SUMMARY|HOLE CARDS)\s*\*\*\*"
    r"(?:\s+\[(?P<cards>[^\]]+)\])?(?:\s+\[(?P<extra>[^\]]+)\])?",
    re.IGNORECASE,
)
COLLECTED_RE = re.compile(
    r"(?P<name>.+?)\s+collected\s+\$?(?P<amt>[\d.,]+)", re.IGNORECASE
)
TOTAL_POT_RE = re.compile(r"Total\s+pot\s+\$?(?P<amt>[\d.,]+)", re.IGNORECASE)
UNCALLED_RE = re.compile(
    r"Uncalled\s+bet\s+\(\$?(?P<amt>[\d.,]+)\)\s+returned\s+to\s+(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
HERO_NAME_RE = re.compile(r"Dealt\s+to\s+(.+?)\s+\[", re.IGNORECASE)


VERB_TO_CODE = {
    "folds": "F",
    "checks": "X",
    "calls": "C",
    "bets": "B",
    "raises": "R",
    "all-in": "AI",
}

POSITIONS_BY_SIZE = {
    9: ["SB", "BB", "UTG", "UTG1", "MP", "LJ", "HJ", "CO", "BTN"],
    8: ["SB", "BB", "UTG", "UTG1", "LJ", "HJ", "CO", "BTN"],
    6: ["SB", "BB", "UTG", "HJ", "CO", "BTN"],
    3: ["SB", "BB", "BTN"],
    2: ["SB", "BB"],
}


def _split_hands(raw: str) -> list[str]:
    """Split a multi-hand text into individual hand blocks.

    PokerStars separates hands by a blank line. We also accept blocks that
    begin with 'PokerStars Hand'.
    """
    text = raw.replace("\r\n", "\n")
    if not text.strip():
        return []
    # Prefer split-on-header for robustness
    blocks = re.split(r"(?=^PokerStars\s+(?:Hand|Game)\s+#)", text, flags=re.MULTILINE)
    return [b.strip() for b in blocks if b.strip()]


def _to_float(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return 0.0


def _detect_position(seat: int, button_seat: int, size: int) -> str:
    """Map seat-relative-to-button into a position label."""
    if size <= 0:
        return "?"
    rel = (seat - button_seat) % size
    layouts = POSITIONS_BY_SIZE.get(size) or POSITIONS_BY_SIZE[max(POSITIONS_BY_SIZE)]
    # SB is usually 1 seat after the button (rel == 1), so reorder
    # Build labels going clockwise starting from BTN
    if size in (9, 8):
        order = ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "LJ", "HJ", "CO"][:size]
    elif size == 6:
        order = ["BTN", "SB", "BB", "UTG", "HJ", "CO"]
    elif size == 3:
        order = ["BTN", "SB", "BB"]
    elif size == 2:
        order = ["BTN", "BB"]  # heads-up: button is SB
    else:
        order = ["BTN"] + ["SB"] + ["BB"] + ["X"] * (size - 3)
    return order[rel]


def _classify_pot_type(preflop_actions: list[tuple[str, str, float]]) -> str:
    """Look at preflop verbs to label pot type (Limp / SRP / 3BP / 4BP / 5BP / Squeeze)."""
    raises = [a for a in preflop_actions if a[1] == "R"]
    bets = [a for a in preflop_actions if a[1] == "B"]
    calls_before_raise = sum(1 for n, v, _ in preflop_actions if v == "C")
    if not raises and not bets:
        return "Limp" if calls_before_raise > 0 else "Walk"
    if len(raises) == 1:
        return "SRP"
    if len(raises) == 2:
        # Squeeze if a flat-call appeared between blinds and the second raise
        return "Squeeze" if calls_before_raise > 0 else "3BP"
    if len(raises) == 3:
        return "4BP"
    return "5BP"


def _parse_block(block: str) -> Optional[dict]:
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines:
        return None
    header_match = HEADER_RE.search(lines[0]) or DEMO_HEADER_RE.search(lines[0])
    if not header_match:
        return None
    hand_id = header_match.group("hid")
    fmt = header_match.group("format").strip()
    try:
        date = header_match.group("date")
    except (IndexError, KeyError):
        date = None

    table_match = next((TABLE_RE.search(l) for l in lines[:3] if TABLE_RE.search(l)), None)
    table_size = int(table_match.group("size")) if table_match else 6
    btn_seat = int(table_match.group("btn")) if table_match else 1

    # Seats
    seats: dict[str, int] = {}
    chips: dict[str, float] = {}
    for line in lines:
        m = SEAT_RE.match(line)
        if m:
            name = m.group("name").strip()
            seats[name] = int(m.group("seat"))
            chips[name] = _to_float(m.group("chips"))

    # Detect blinds & infer big blind size
    bb_size = 1.0
    sb_size = 0.5
    for line in lines:
        if (m := SB_RE.search(line)):
            sb_size = _to_float(m.group("amt"))
        elif (m := BB_RE.search(line)):
            bb_size = _to_float(m.group("amt"))
    if bb_size <= 0:
        bb_size = 1.0
    bb_norm = lambda v: round(v / bb_size, 2) if bb_size else v

    # Hero
    hero_match = next((HOLE_RE.search(l) for l in lines if HOLE_RE.search(l)), None)
    hero_name = hero_match.group("name").strip() if hero_match else "Hero"
    hero_cards = hero_match.group("cards").replace(" ", "") if hero_match else ""

    hero_seat = seats.get(hero_name, btn_seat)
    # Prefer table_size from TABLE_RE; fall back to seat count, then 6.
    effective_size = table_size if table_size > 0 else (len(seats) or 6)
    hero_position = _detect_position(hero_seat, btn_seat, max(effective_size, 2))

    # Walk through streets
    streets: dict[str, list[tuple[str, str, float]]] = {
        "preflop": [], "flop": [], "turn": [], "river": [],
    }
    board_cards: list[str] = []
    current = "preflop"
    pot_total = 0.0
    hero_collected = 0.0
    hero_uncalled = 0.0

    for line in lines:
        if (m := STREET_RE.match(line)):
            label = m.group("street").lower()
            if label == "flop":
                current = "flop"
                if m.group("cards"):
                    board_cards.extend(m.group("cards").split())
            elif label == "turn":
                current = "turn"
                if m.group("cards"):
                    # PokerStars writes turn as [Flop] [Turn]; pull the second one
                    board_cards.extend(re.findall(r"[2-9TJQKA][hdsc]", line)[3:4])
            elif label == "river":
                current = "river"
                board_cards.extend(re.findall(r"[2-9TJQKA][hdsc]", line)[4:5])
            elif label in ("show down", "summary"):
                current = label.replace(" ", "_")
            continue
        if (m := ACTION_RE.match(line)):
            verb = m.group("verb").lower()
            code = VERB_TO_CODE.get(verb, "?")
            amt = _to_float(m.group("to") or m.group("amt"))
            if current in streets:
                streets[current].append((m.group("name").strip(), code, amt))
            continue
        if (m := COLLECTED_RE.search(line)):
            if m.group("name").strip() == hero_name:
                hero_collected += _to_float(m.group("amt"))
        if (m := UNCALLED_RE.search(line)):
            if m.group("name").strip() == hero_name:
                hero_uncalled += _to_float(m.group("amt"))
        if (m := TOTAL_POT_RE.search(line)):
            pot_total = _to_float(m.group("amt"))

    # Hero invested across streets (sum of last-bet-to per street)
    hero_invested = 0.0
    for street_actions in streets.values():
        last_to_for_hero = 0.0
        for name, code, amt in street_actions:
            if name == hero_name and code in ("C", "B", "R"):
                last_to_for_hero = max(last_to_for_hero, amt)
        hero_invested += last_to_for_hero
    if not pot_total:
        pot_total = sum(amt for _, _, amt in streets["preflop"])

    # If Hero made an uncalled final bet, it's returned and shouldn't count as invested.
    hero_invested = max(0.0, hero_invested - hero_uncalled)
    profit = hero_collected - hero_invested
    # If Hero collected nothing but the pot wasn't shown down, profit = -invested
    if hero_collected == 0 and pot_total > 0:
        profit = -hero_invested

    def _codes(actions: list[tuple[str, str, float]]) -> str:
        return "".join(c for _, c, _ in actions)

    pot_type = _classify_pot_type(streets["preflop"])

    return {
        "external_id": str(hand_id),
        "site": "PokerStars",
        "format": fmt[:80],
        "date": date,
        "hero_position": hero_position,
        "hero_cards": hero_cards,
        "board": "".join(board_cards),
        "pot_bb": bb_norm(pot_total),
        "hero_profit_bb": bb_norm(profit),
        "ev_loss": 0.0,
        "pot_type": pot_type,
        "preflop_actions": _codes(streets["preflop"]),
        "flop_actions": _codes(streets["flop"]),
        "turn_actions": _codes(streets["turn"]),
        "river_actions": _codes(streets["river"]),
        "status": "review",
        "raw_text": block,
    }


def parse_pokerstars(raw_text: str) -> list[dict]:
    """Parse one or many PokerStars hand histories. Robust to demo + production formats."""
    blocks = _split_hands(raw_text)
    if not blocks:
        return []
    out: list[dict] = []
    for block in blocks:
        try:
            parsed = _parse_block(block)
            if parsed:
                out.append(parsed)
        except Exception:
            # Don't let one malformed hand kill the whole import
            continue
    return out
