"""CoinPoker hand history parser.

CoinPoker uses a PokerStars-style format with site-specific variations:
  - Header begins with `CoinPoker Hand #` or `Game started ...` for some clients
  - Stack lines occasionally drop the trailing 'in chips'
  - Times are often in UTC instead of ET
  - Currency frequently shown as CHP / USDT, not always with $ prefix
  - Some exports use `Hold'em No Limit` interchangeably with `NL Hold'em`
"""
from __future__ import annotations

import re

from app.parsers.pokerstars_parser import (
    ACTION_RE,
    BB_RE,
    COLLECTED_RE,
    HOLE_RE,
    SB_RE,
    SEAT_RE,
    STREET_RE,
    TABLE_RE,
    TOTAL_POT_RE,
    UNCALLED_RE,
    VERB_TO_CODE,
    _classify_pot_type,
    _detect_position,
    _to_float,
)


# CoinPoker header — accept several variants:
#   CoinPoker Hand #1234567890: Tournament #98765432, $5+$0.50 USDT Hold'em No Limit ...
#   CoinPoker Hand #1234567890: Hold'em No Limit (CHP $0.05/$0.10) - 2024/06/01 19:35:21 UTC
COINPOKER_HEADER_RE = re.compile(
    r"CoinPoker\s+(?:Hand|Game)\s+#(?P<hid>[A-Za-z0-9-]+):\s*"
    r"(?P<format>.*?)(?:\s+-\s+(?P<date>\d{4}[/-]\d{2}[/-]\d{2}.*?(?:UTC|ET|GMT)))?\s*$",
    re.IGNORECASE,
)
# Fallback when the export uses `Game started`
GAME_STARTED_RE = re.compile(
    r"Game\s+started\s+at\s+(?P<date>\d{4}[/-]\d{2}[/-]\d{2}\s+\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)
# Accept lines like "Seat 3: Hero (5100)" (no 'in chips' suffix)
COIN_SEAT_RE = re.compile(
    r"Seat\s+(?P<seat>\d+):\s+(?P<name>[^()]+?)\s+\(\$?(?P<chips>[\d,.]+)\s*(?:in\s+chips|CHP|USDT)?\)",
    re.IGNORECASE,
)
# Some CoinPoker dumps use a brace-delimited table line:
COIN_TABLE_RE = re.compile(
    r"Table\s+'[^']+'\s+(?P<size>\d+)-?(?:max|handed)?.*?Seat\s+#?(?P<btn>\d+)\s+is\s+the\s+button",
    re.IGNORECASE,
)


def _split_hands(raw: str) -> list[str]:
    text = raw.replace("\r\n", "\n")
    if not text.strip():
        return []
    blocks = re.split(r"(?=^CoinPoker\s+(?:Hand|Game)\s+#)", text, flags=re.MULTILINE)
    return [b.strip() for b in blocks if b.strip()]


def _parse_block(block: str) -> dict | None:
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines:
        return None
    header = COINPOKER_HEADER_RE.match(lines[0])
    if not header:
        return None
    hand_id = header.group("hid")
    fmt = (header.group("format") or "").strip()
    date = header.group("date")

    table_match = next(
        (COIN_TABLE_RE.search(l) or TABLE_RE.search(l)
         for l in lines[:4]
         if COIN_TABLE_RE.search(l) or TABLE_RE.search(l)),
        None,
    )
    table_size = int(table_match.group("size")) if table_match else 6
    btn_seat = int(table_match.group("btn")) if table_match else 1

    seats: dict[str, int] = {}
    chips: dict[str, float] = {}
    for line in lines:
        m = COIN_SEAT_RE.match(line) or SEAT_RE.match(line)
        if m:
            name = m.group("name").strip()
            seats[name] = int(m.group("seat"))
            chips[name] = _to_float(m.group("chips"))

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

    hero_match = next((HOLE_RE.search(l) for l in lines if HOLE_RE.search(l)), None)
    hero_name = hero_match.group("name").strip() if hero_match else "Hero"
    hero_cards = hero_match.group("cards").replace(" ", "") if hero_match else ""

    hero_seat = seats.get(hero_name, btn_seat)
    effective_size = table_size if table_size > 0 else (len(seats) or 6)
    hero_position = _detect_position(hero_seat, btn_seat, max(effective_size, 2))

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

    hero_invested = 0.0
    for street_actions in streets.values():
        last_to_for_hero = 0.0
        for name, code, amt in street_actions:
            if name == hero_name and code in ("C", "B", "R"):
                last_to_for_hero = max(last_to_for_hero, amt)
        hero_invested += last_to_for_hero
    hero_invested = max(0.0, hero_invested - hero_uncalled)
    if not pot_total:
        pot_total = sum(amt for _, _, amt in streets["preflop"])

    profit = hero_collected - hero_invested
    if hero_collected == 0 and pot_total > 0:
        profit = -hero_invested

    def _codes(actions: list[tuple[str, str, float]]) -> str:
        return "".join(c for _, c, _ in actions)

    return {
        "external_id": str(hand_id),
        "site": "CoinPoker",
        "format": fmt[:80],
        "date": date,
        "hero_position": hero_position,
        "hero_cards": hero_cards,
        "board": "".join(board_cards),
        "pot_bb": bb_norm(pot_total),
        "hero_profit_bb": bb_norm(profit),
        "ev_loss": 0.0,
        "pot_type": _classify_pot_type(streets["preflop"]),
        "preflop_actions": _codes(streets["preflop"]),
        "flop_actions": _codes(streets["flop"]),
        "turn_actions": _codes(streets["turn"]),
        "river_actions": _codes(streets["river"]),
        "status": "review",
        "raw_text": block,
    }


def parse_coinpoker(raw_text: str) -> list[dict]:
    blocks = _split_hands(raw_text)
    out: list[dict] = []
    for b in blocks:
        try:
            parsed = _parse_block(b)
            if parsed:
                out.append(parsed)
        except Exception:
            continue
    return out
