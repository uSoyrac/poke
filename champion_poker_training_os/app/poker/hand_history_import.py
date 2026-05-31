"""Gerçek el geçmişi import — çok-site metin formatı parser'ı (Phase D7).

Online oynanan GERÇEK elleri içeri alıp `played_hands`'e yazar; böylece
istatistik / leak / GTO-ilerleme analizi gerçek oyununa dayanır.

Kapsam: NLHE el geçmişi — GGPoker · CoinPoker · PokerStars (hepsi
PokerStars-türevi metin formatı: 'Dealt to', '*** FLOP ***', 'raises … to',
'collected', 'Total pot'). Site sadece BAŞLIK satırından değişir; parser
site-bağımsızdır. Hero 'Dealt to <isim>' satırından bulunur. Net kâr =
collected + uncalled_returned − invested.

Saf fonksiyon (DB/Qt bağımsız) — `parse_hands(text) → list[dict]`
(`parse_pokerstars` geriye-uyumlu alias). Her dict `repository.
save_played_hand` şemasına uygundur.
"""
from __future__ import annotations

import re

_HAND_SPLIT = re.compile(r"\n\s*\n")           # eller boş satırla ayrılır
# Site-bağımsız başlık: "<Site> Hand #<id>" / "Poker Hand #<id>" / "Game #<id>".
# GG/CoinPoker hand-id'leri alfanümerik olabilir (HD123, RC123…) → \w+.
_HID = re.compile(r"(?:Hand|Game)\s+#([A-Za-z0-9]+)")
_SITE = re.compile(r"\b(GG\s?Poker|CoinPoker|PokerStars|PartyPoker|888poker)\b",
                   re.IGNORECASE)
_DEALT = re.compile(r"Dealt to (.+?) \[([2-9TJQKA][cdhs] [2-9TJQKA][cdhs])\]")
_BOARD = re.compile(r"Board \[([^\]]+)\]")
_FLOP = re.compile(r"\*\*\* FLOP \*\*\* \[([^\]]+)\]")
_TURN = re.compile(r"\*\*\* TURN \*\*\* \[[^\]]+\] \[([2-9TJQKA][cdhs])\]")
_RIVER = re.compile(r"\*\*\* RIVER \*\*\* \[[^\]]+\] \[([2-9TJQKA][cdhs])\]")
# Para: $ € £ ₮ (CoinPoker USDT) veya sembolsüz düz sayı
_AMOUNT = r"[$€£₮]?([0-9]+(?:\.[0-9]+)?)"


def _money(s: str) -> float:
    m = re.search(_AMOUNT, s)
    return float(m.group(1)) if m else 0.0


def parse_hands(text: str) -> list[dict]:
    """El-geçmişi metnini (GGPoker/CoinPoker/PokerStars) played_hand dict
    listesine çevir. Site-bağımsız: blokta bir 'Hand/Game #<id>' başlığı +
    'Dealt to' satırı varsa parse edilir."""
    out: list[dict] = []
    for block in _HAND_SPLIT.split(text or ""):
        if "Dealt to" not in block or not _HID.search(block):
            continue
        rec = _parse_one(block)
        if rec:
            out.append(rec)
    return out


# Geriye-uyumlu alias (eski çağrı yerleri parse_pokerstars kullanıyor)
def parse_pokerstars(text: str) -> list[dict]:
    return parse_hands(text)


def _parse_one(block: str) -> dict | None:
    hid_m = _HID.search(block)
    dealt_m = _DEALT.search(block)
    if not hid_m or not dealt_m:
        return None
    site_m = _SITE.search(block)
    site = site_m.group(1) if site_m else "Bilinmeyen"
    hand_id = hid_m.group(1)
    hero = dealt_m.group(1).strip()
    hero_cards = dealt_m.group(2)

    # Büyük blind → bb birimi (sonuçları bb'ye normalize etmek için)
    bb = 1.0
    bb_m = re.search(r"\(" + _AMOUNT + r"/" + _AMOUNT + r"", block)
    if bb_m:
        try:
            bb = float(bb_m.group(2)) or 1.0
        except Exception:
            bb = 1.0

    # Board / streets
    board = ""
    bm = _BOARD.search(block)
    if bm:
        board = bm.group(1).strip()
    streets_seen = 1
    if _FLOP.search(block):
        streets_seen = 2
    if _TURN.search(block):
        streets_seen = 3
    if _RIVER.search(block):
        streets_seen = 4

    # Hero'nun yatırdığı + topladığı (street başına commit takibi)
    invested = 0.0
    collected = 0.0
    returned = 0.0
    street_commit = 0.0   # hero'nun bu street'te şu ana dek koyduğu
    esc = re.escape(hero)

    for raw in block.splitlines():
        line = raw.strip()
        # Yeni kart sokağı → street commit sıfırla. DİKKAT: blind'ler
        # "*** HOLE CARDS ***"ten ÖNCE post edilir ve preflop'a dahildir;
        # bu yüzden sadece FLOP/TURN/RIVER'da sıfırla (HOLE CARDS/SUMMARY'de değil).
        if line.startswith(("*** FLOP", "*** TURN", "*** RIVER")):
            street_commit = 0.0
            continue
        if line.startswith("***"):
            continue

        # Uncalled bet (herkes için ama hero'ya döneni al)
        m = re.match(r"Uncalled bet \(" + _AMOUNT + r"\) returned to " + esc, line)
        if m:
            returned += float(m.group(1))
            continue

        if not line.startswith(hero):
            continue
        body = line[len(hero):].lstrip(": ").strip()

        if body.startswith("posts"):
            invested += _money(body)
            street_commit += _money(body)
        elif body.startswith("calls"):
            amt = _money(body)
            invested += amt
            street_commit += amt
        elif body.startswith("bets"):
            amt = _money(body)
            invested += amt
            street_commit += amt
        elif body.startswith("raises"):
            # "raises $2 to $5" → bu street toplam commit $5 olur
            to_m = re.search(r"to " + _AMOUNT, body)
            if to_m:
                total_to = float(to_m.group(1))
                add = max(0.0, total_to - street_commit)
                invested += add
                street_commit = total_to
        elif "collected" in body:
            collected += _money(body)

    net = round(collected + returned - invested, 2)
    won = collected > 0
    pot_m = re.search(r"Total pot " + _AMOUNT, block)
    pot = float(pot_m.group(1)) if pot_m else (invested + collected)

    winner = ""
    win_m = re.search(r"won \(" + _AMOUNT + r"\) with (.+)", block)
    if win_m:
        winner = win_m.group(2).strip()[:40]

    return {
        "hand_id": f"HH-{hand_id}",
        "hero_cards": hero_cards,
        "community": board,
        "pot": round(pot / bb, 2),
        "hero_invested": round(invested / bb, 2),
        "hero_profit": round(net / bb, 2),
        "hero_won": bool(won),
        "winner_hand_name": winner,
        "streets_seen": streets_seen,
        "source": "import",
        "site": site,
    }
