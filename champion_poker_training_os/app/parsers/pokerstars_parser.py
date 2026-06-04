"""Gerçek PokerStars el-geçmişi parser'ı (NLHE cash).

Standart PokerStars metin formatını parse eder. Çıktı dict'leri played_hands
şeması + hero-stat bayrakları + bb-normalize (D97) ile uyumludur, böylece
import edilen GERÇEK eller leak analizi / drill üretimi için kullanılabilir.

Desteklenen: cash NLHE (6-max/9-max/HU). Turnuva el-başlıkları 'Tournament'
içerir → game_type='tournament' işaretlenir (chip-ölçekli).
"""
from __future__ import annotations

import re
from typing import Optional

# Button'dan offset → pozisyon (n oyuncuya göre). 0=BTN.
_POS_BY_OFFSET = {
    2: ["BTN", "BB"],                                  # HU: button=SB/BTN
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "UTG", "CO"],
    6: ["BTN", "SB", "BB", "UTG", "MP", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"],
}

_HEADER_RE = re.compile(r"PokerStars Hand #(\d+):.*?\(\$?([\d.]+)/\$?([\d.]+)")
_BUTTON_RE = re.compile(r"Seat #(\d+) is the button")
_SEAT_RE = re.compile(r"Seat (\d+): (.+?) \(\$?([\d,.]+) in chips\)")
_DEALT_RE = re.compile(r"Dealt to (.+?) \[(..) (..)\]")
_BOARD_RE = re.compile(r"Board \[([^\]]+)\]")
_STREET_CARDS_RE = re.compile(
    r"\*\*\* (FLOP|TURN|RIVER) \*\*\*.*?\[([^\]]+)\]\s*(?:\[([^\]]+)\])?")
_COLLECT_RE = re.compile(r"collected \(?\$?([\d,.]+)\)?")
_UNCALLED_RE = re.compile(r"Uncalled bet \(\$?([\d,.]+)\) returned to (.+)")


def _f(s: str) -> float:
    return float(s.replace(",", ""))


def _split_hands(raw: str) -> list[str]:
    parts = re.split(r"(?=PokerStars Hand #)", raw)
    return [p for p in parts if p.strip().startswith("PokerStars Hand")]


def _parse_one(block: str, hero_name: Optional[str]) -> Optional[dict]:
    m = _HEADER_RE.search(block)
    if not m:
        return None
    hand_id, sb, bb = m.group(1), _f(m.group(2)), _f(m.group(3))
    game_type = "tournament" if "Tournament" in block.split("\n", 1)[0] else "cash"
    bm = _BUTTON_RE.search(block)
    button_seat = int(bm.group(1)) if bm else 1

    seats = [(int(s), name.strip()) for s, name, _ in _SEAT_RE.findall(block)]
    seats.sort()
    if not seats:
        return None

    dm = _DEALT_RE.search(block)
    if hero_name is None and dm:
        hero_name = dm.group(1).strip()
    if hero_name is None:
        return None
    hero_cards = (f"{dm.group(2)} {dm.group(3)}"
                 if dm and dm.group(1).strip() == hero_name else "")

    hero_seat = next((s for s, n in seats if n == hero_name), None)
    if hero_seat is None:
        return None

    occ = [s for s, _ in seats]
    n = len(occ)
    bi = occ.index(button_seat) if button_seat in occ else 0
    offset = (occ.index(hero_seat) - bi) % n
    pos_list = _POS_BY_OFFSET.get(n, _POS_BY_OFFSET[6])
    hero_position = pos_list[offset] if offset < len(pos_list) else "MP"

    board = ""
    bdm = _BOARD_RE.search(block)
    if bdm:
        board = bdm.group(1).strip()
    else:
        cards: list[str] = []
        for _, c1, c2 in _STREET_CARDS_RE.findall(block):
            for grp in (c1, c2):
                if grp:
                    cards.extend(grp.split())
        board = " ".join(cards)

    streets = {"PREFLOP": "*** HOLE CARDS ***", "FLOP": "*** FLOP ***",
               "TURN": "*** TURN ***", "RIVER": "*** RIVER ***"}
    idxs = {k: block.find(v) for k, v in streets.items()}
    order = [k for k in ("PREFLOP", "FLOP", "TURN", "RIVER") if idxs[k] >= 0]
    streets_seen = len(order)

    invested = 0.0
    hero_vpip = hero_pfr = 0
    hero_postflop_aggr = hero_postflop_passive = 0
    esc = re.escape(hero_name)
    raise_re = re.compile(rf"^{esc}: raises \$?[\d,.]+ to \$?([\d,.]+)", re.M)
    bet_re = re.compile(rf"^{esc}: bets \$?([\d,.]+)", re.M)
    call_re = re.compile(rf"^{esc}: calls \$?([\d,.]+)", re.M)
    blind_re = re.compile(rf"^{esc}: posts (?:small|big) blind \$?([\d,.]+)", re.M)

    for si, st in enumerate(order):
        seg_start = idxs[st]
        seg_end = idxs[order[si + 1]] if si + 1 < len(order) else len(block)
        seg = block[seg_start:seg_end]
        committed = 0.0
        is_preflop = (st == "PREFLOP")
        if is_preflop:
            for bl in blind_re.findall(block[:idxs["PREFLOP"]]):
                committed += _f(bl)
        raises = raise_re.findall(seg)
        bets = bet_re.findall(seg)
        calls = call_re.findall(seg)
        for rm in raises:
            committed = _f(rm)          # 'to' = bu sokaktaki toplam taahhüt
        for bmt in bets:
            committed += _f(bmt)
        for cm in calls:
            committed += _f(cm)
        invested += committed
        if is_preflop:
            if raises or bets:
                hero_vpip = 1; hero_pfr = 1
            elif calls:
                hero_vpip = 1
        else:
            hero_postflop_aggr += len(raises) + len(bets)
            hero_postflop_passive += len(calls)

    for amt, who in _UNCALLED_RE.findall(block):
        if who.strip() == hero_name:
            invested -= _f(amt)

    collected = 0.0
    for line in block.splitlines():
        ls = line.strip()
        if ls.startswith(hero_name) and "collected" in ls:
            cm = _COLLECT_RE.search(ls)
            if cm:
                collected += _f(cm.group(1))

    net = collected - invested
    pm = re.search(r"Total pot \$?([\d,.]+)", block)
    pot_total = _f(pm.group(1)) if pm else 0.0

    return {
        "site": "PokerStars",
        "hand_id": hand_id,
        "game_type": game_type,
        "small_blind": sb,
        "big_blind": bb,
        "hero_cards": hero_cards,
        "hero_position": hero_position,
        "board": board,
        "community": board,
        "streets_seen": streets_seen,
        "pot": round(pot_total, 2),
        "hero_invested": round(invested, 2),
        "hero_profit": round(net, 2),
        "result_bb": round(net / bb, 2) if bb else 0.0,
        "hero_won": collected > 0.0,
        "hero_vpip": hero_vpip,
        "hero_pfr": hero_pfr,
        "hero_3bet_opp": 0,
        "hero_3bet": 0,
        "hero_postflop_aggr": hero_postflop_aggr,
        "hero_postflop_passive": hero_postflop_passive,
        "raw_text": block.strip(),
    }


def parse_pokerstars(raw_text: str, hero_name: Optional[str] = None) -> list[dict]:
    """PokerStars el-geçmişi metnini parse et → hand dict listesi."""
    out = []
    for block in _split_hands(raw_text):
        try:
            h = _parse_one(block, hero_name)
        except Exception:
            h = None
        if h:
            out.append(h)
    return out
