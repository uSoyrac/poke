"""Soyrac Sistem Akademisi — müfredat + drill motoru (saf, Qt'siz).

Tasarım: LXD+ID+UX workflow. Müfredat-tabanlı kendi-hızında öğren→alıştır→ustalaş.
GRADER hep soyrac_explain (mock-veri YOK); soyrac_advice/bot DEĞİŞMEZ (ekran OKUR).
Canlı Koç'tan farkı: bu oyun-DIŞI yapılandırılmış çalışma; koç oyun-içi anlık.
"""
from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional

from app.poker.soyrac_advisor import soyrac_explain, soyrac_leak_category, shcp_score

# ── 8 modüllü lineer omurga (her biri kitap + flowchart + drill senaryosu) ──
MODULES = OrderedDict([
    ("M0", dict(
        key="M0", title="Sistem Haritası", fig_key="system", scenario=None, prereq=None,
        analogy="Bridge'de eli açmadan önce 'kaç puanım var' dersin — Soyrac da aynı: "
                "her kararın tek bir akışı var.",
        learn_bullets=[
            "Tek altın ilke: elin gücü TEK eksendir (SHCP puanı).",
            "Pozisyon/board/ICM puana EKLENMEZ — sadece karar EŞİĞİNİ kaydırır.",
            "Akış: el → puan → senaryo eşiği → karar (aç/call/3bet/fold).",
            "Postflop: board oku → 7-kademe → 3 altın kural → karar.",
        ],
        subcategories=["harita"], mastery_n=4, mastery_acc=1.0, mastery_streak=4)),
    ("M1", dict(
        key="M1", title="SHCP Puanı", fig_key="preflop", scenario="RFI", prereq="M0",
        analogy="Blackjack Hi-Lo gibi: her karta değer ver, topla. A=10, K=8… suited +4.",
        learn_bullets=[
            "Kart puanı: A=10, K=8, Q=6, J=5, T=4, 9=3, 8=2, 7-4=1, 3-2=0.",
            "Suited +4 (içinde As varsa ek +2 — nut-floş blocker primi).",
            "Connector: bitişik +3, 1-gap +2, 2-gap +1, 4+gap −2.",
            "Çift: 16 + 2×rank → AA=40, KK=38 … 22=16.",
        ],
        subcategories=["puan"], mastery_n=10, mastery_acc=0.85, mastery_streak=6)),
    ("M2", dict(
        key="M2", title="Pozisyon = Eşik (RFI)", fig_key="preflop", scenario="RFI", prereq="M1",
        analogy="Blackjack'te kasanın açık kartına göre eşiğin değişir; burada da "
                "pozisyona göre açış eşiğin değişir — el aynı kalır.",
        learn_bullets=[
            "RFI eşik: UTG 15, MP 14, CO 11, BTN 8, SB 9 (geç → düşük eşik = geniş).",
            "Puan ≥ eşik → AÇ (RAISE), altında → FOLD.",
            "Eşik puana eklenmez; sadece çıtayı belirler.",
            "Erken pozisyon dar (arkanda çok kişi), geç pozisyon geniş.",
        ],
        subcategories=["UTG", "MP", "CO", "BTN", "SB"], mastery_n=10, mastery_acc=0.85, mastery_streak=6)),
    ("M3", dict(
        key="M3", title="vs-RFI (Çift Eşik)", fig_key="bb-defense", scenario="vs RFI", prereq="M2",
        analogy="Biri açtı: iki eşiğin var — call eşiği ve 3-bet eşiği. Arada call, "
                "üstünde 3-bet, altında fold.",
        learn_bullets=[
            "Çift eşik: puan ≥ 3bet eşiği → 3-BET; ≥ call eşiği → CALL; altı → FOLD.",
            "Açan ERKEN ise sıkı savun, GEÇ ise geniş (opener-adj).",
            "BB'de spekülatif çöp (suited/offsuit connector) GTO'da bile -EV → KATLA.",
            "A2s-A5s ile geç açana 3-bet blöf (AA/AK bloklar).",
        ],
        subcategories=["call", "3bet", "fold"], mastery_n=10, mastery_acc=0.85, mastery_streak=6)),
    ("M4", dict(
        key="M4", title="vs-3bet (Blocker Ekseni)", fig_key="vs3bet", scenario="vs 3-bet", prereq="M3",
        analogy="Kart sayımı gibi: 3-bet pot'ta saf puan ÇÖKER, KOMBİNATORİK önemli. "
                "A5s, AJs'i döver (blocker).",
        learn_bullets=[
            "3-bet pot pahalı: premium değilse KATLA.",
            "4-BET: QQ+/AK (B4 blocker ≥2) + A2s-A5s blöf.",
            "Düz CALL: çok güçlü (JJ+/AQs+/KQs).",
            "Gerisi fold — marjinal el 3-bet pot'ta para yakar.",
        ],
        subcategories=["4bet", "call", "fold"], mastery_n=10, mastery_acc=0.85, mastery_streak=6)),
    ("M5", dict(
        key="M5", title="Postflop 7-Kademe", fig_key="tier", scenario="postflop", prereq="M4",
        analogy="Blackjack el-değeri kademesi gibi: board'a bakıp elini 7 kademeden "
                "birine ata (NUT…HAVA).",
        learn_bullets=[
            "Önce board oku: kuru/ıslak/eşli.",
            "7-kademe: NUT/GÜÇLÜ/ORTA/ZAYIF/BLUFF-CATCH/DRAW/HAVA.",
            "NUT/GÜÇLÜ → value bas; DRAW → semi-blöf; HAVA → bırak.",
            "Sonraki sokakta bir kademe aşağı say (haircut).",
        ],
        subcategories=["NUT", "GÜÇLÜ", "ORTA", "DRAW", "HAVA"], mastery_n=10, mastery_acc=0.80, mastery_streak=5)),
    ("M6", dict(
        key="M6", title="3 Altın Kural", fig_key="postflop", scenario="postflop", prereq="M5",
        analogy="Üç güvenlik kuralı: yığını çöple riske atma, kuru board'da bas, "
                "oran tutmuyorsa katla.",
        learn_bullets=[
            "Commit-gate: yığının %70'ini riske atan bahse sadece GÜÇLÜ+/çekme ile gir.",
            "Flop range-cbet: kuru board + agresörsen her şeyle küçük bas (1/3).",
            "Pot-odds: gereken equity = to_call/(pot+to_call); altındaysan katla.",
            "Bet sizing göreli: kuru 1/3, ıslak 3/4 (pot büyür → boyut büyür).",
        ],
        subcategories=["commit-gate", "range-cbet", "pot-odds"], mastery_n=10, mastery_acc=0.80, mastery_streak=5)),
    ("M7", dict(
        key="M7", title="Format / ICM / Push-Fold", fig_key="format", scenario="RFI", prereq="M6",
        analogy="Cash'te reload var → loose oyna (balığı ez); turnuvada reload yok → "
                "sıkılaş, hayatta kal.",
        learn_bullets=[
            "Cash = SHCP loose-aggressive (fishy sahayı ez, #1-3 elit).",
            "Turnuva = daha sıkı + ICM + kısa-stack push/fold.",
            "<15bb: equity ekseni → puan ≥16 JAM, yoksa FOLD (Nash).",
            "ICM/derinlik eşiği kaydırır (elenme pahalıysa +1 sık).",
        ],
        subcategories=["cash", "turnuva", "push-fold"], mastery_n=10, mastery_acc=0.85, mastery_streak=6)),
])

_RANKS = "AKQJT98765432"
_SUITS = "shdc"


def module_list() -> list:
    return list(MODULES.values())


def _all_hand_keys() -> list:
    """169 el (AA, AKs, AKo, …)."""
    out = []
    for i, r1 in enumerate(_RANKS):
        for j, r2 in enumerate(_RANKS):
            if i == j:
                out.append(r1 + r2)
            elif i < j:
                out.append(r1 + r2 + "s")
            else:
                out.append(r2 + r1 + "o")
    return sorted(set(out))


_HANDS = _all_hand_keys()
_POS_RFI = ["UTG", "MP", "CO", "BTN", "SB"]
_OPENERS = ["UTG", "MP", "CO", "BTN"]


@dataclass
class DrillSpot:
    module_key: str
    scenario: str
    hand_key: str
    position: str = "BTN"
    vs_position: str = ""
    stack_bb: float = 100
    tourney: bool = False
    board: Optional[list] = None        # postflop için Card listesi
    difficulty: int = 1
    subcategory: str = ""
    explain: dict = field(default_factory=dict)   # soyrac_explain çıktısı (doğru cevap)

    @property
    def correct(self) -> str:
        return self.explain.get("action", "FOLD")


# ── postflop drill için minimal hand objesi ──
class _DrillP:
    def __init__(self, hole, stack=100):
        self.hole_cards = hole
        self.stack = stack


class _DrillHand:
    def __init__(self, hole, board, pot, to_call, street):
        self.players = [_DrillP(hole)]
        self.community = board
        self.pot = pot
        self.street = street
        self.hero_idx = 0
        self._tc = to_call

    def to_call(self, idx):
        return self._tc


def _deal(rng, hand_key, n_board):
    """hand_key + rastgele board kartları (çakışmasız) → (hole_cards, board_cards)."""
    from app.engine.hand_state import Card
    used = set()
    r1, r2 = hand_key[0], hand_key[1]
    suited = hand_key.endswith("s")
    s1 = rng.choice(_SUITS)
    s2 = s1 if (suited or r1 == r2) else rng.choice([s for s in _SUITS if s != s1])
    if r1 == r2:
        s2 = rng.choice([s for s in _SUITS if s != s1])
    hole = [Card(r1, s1), Card(r2, s2)]
    used = {(r1, s1), (r2, s2)}
    board = []
    while len(board) < n_board:
        r = rng.choice(_RANKS); s = rng.choice(_SUITS)
        if (r, s) in used:
            continue
        used.add((r, s)); board.append(Card(r, s))
    return hole, board


def _pick_hand(rng, scenario, position, vs_position, difficulty):
    """Zorluğa göre el seç: 1=eşikten uzak (net), 2=eşik-civarı, 3=marjinal/mixed."""
    if difficulty <= 1:
        # net: ya çok güçlü ya çok çöp
        pool = [h for h in _HANDS if shcp_score(h) >= 28 or shcp_score(h) <= 4]
    elif difficulty == 2:
        # eşik civarı: orta puanlar
        pool = [h for h in _HANDS if 8 <= shcp_score(h) <= 24]
    else:
        pool = _HANDS
    return rng.choice(pool or _HANDS)


def make_drill(module_key: str, difficulty: int = 1, rng=None) -> Optional[DrillSpot]:
    """Modüle-kilitli bir drill üret; doğru cevabı soyrac_explain ile önceden hesapla."""
    rng = rng or random.Random()
    mod = MODULES.get(module_key)
    if not mod or not mod["scenario"]:
        return None
    scenario = mod["scenario"]
    tourney = module_key == "M7" and rng.random() < 0.5

    if scenario == "postflop":
        position = rng.choice(_POS_RFI)
        hand_key = _pick_hand(rng, scenario, position, "", difficulty)
        n_board = rng.choice([3, 3, 4, 5])      # ağırlıklı flop
        from app.engine.hand_state import Street
        st = {3: Street.FLOP, 4: Street.TURN, 5: Street.RIVER}[n_board]
        hole, board = _deal(rng, hand_key, n_board)
        pot = rng.choice([6, 10, 14, 20])
        to_call = rng.choice([0, 0, pot // 3, pot // 2]) if difficulty < 3 else rng.choice([0, pot // 2, int(pot * 0.9)])
        hand = _DrillHand(hole, board, pot, to_call, st)
        exp = soyrac_explain(hand_key, position, "RFI", hand=hand, hero_idx=0)
        return DrillSpot(module_key=module_key, scenario=scenario, hand_key=hand_key,
                         position=position, stack_bb=100, board=board, difficulty=difficulty,
                         subcategory=exp.get("tier", ""), explain=exp)

    # preflop senaryolar
    if scenario == "RFI":
        position = rng.choice(_POS_RFI)
        vs_position = ""
        stack = 12 if (tourney and rng.random() < 0.4) else 100
    elif scenario == "vs RFI":
        position = rng.choice(["BB", "SB", "BTN", "CO"])
        vs_position = rng.choice([o for o in _OPENERS if o != position] or _OPENERS)
        stack = 100
    else:  # vs 3-bet
        position = rng.choice(["CO", "BTN", "MP"])
        vs_position = "BB"
        stack = 100
    hand_key = _pick_hand(rng, scenario, position, vs_position, difficulty)
    exp = soyrac_explain(hand_key, position, scenario, vs_position=vs_position,
                         stack_bb=stack, n_active=9, tourney=tourney)
    return DrillSpot(module_key=module_key, scenario=scenario, hand_key=hand_key,
                     position=position, vs_position=vs_position, stack_bb=stack,
                     tourney=tourney, difficulty=difficulty,
                     subcategory=_norm_action(exp.get("action", "")), explain=exp)


def _norm_action(a: str) -> str:
    a = (a or "").upper()
    if any(k in a for k in ("RAISE", "3-BET", "4-BET", "JAM", "BET")):
        return "RAISE"
    if "CALL" in a or "CHECK" in a:
        return "CALL"
    return "FOLD"


@dataclass
class DrillResult:
    is_correct: bool
    correct_action: str
    user_action: str
    why: str
    chain_steps: list
    leak_category: Optional[str] = None


def grade_drill(spot: DrillSpot, user_action: str) -> DrillResult:
    """Kullanıcı cevabını NORMALİZE ederek doğru cevapla karşılaştır (motordan)."""
    correct = _norm_action(spot.correct)
    user = _norm_action(user_action)
    ok = correct == user
    leak = None if ok else soyrac_leak_category(spot.explain, user_action)
    return DrillResult(is_correct=ok, correct_action=spot.correct, user_action=user_action,
                       why=spot.explain.get("why", ""),
                       chain_steps=spot.explain.get("chain_steps", []), leak_category=leak)


def compute_badge(best_accuracy: float, streak: int, mod: dict, leak_resolved: bool = False) -> str:
    """🥉 geçti · 🥈 geçti ama spaced-rep bekliyor · 🥇 leak çözüldü (gecikmeli re-test)."""
    passed = best_accuracy >= mod.get("mastery_acc", 0.85) and streak >= mod.get("mastery_streak", 6)
    if not passed:
        return ""
    return "🥇" if leak_resolved else "🥈"


def belt(badges: list) -> str:
    """Global 'Soyrac Kuşağı' — kaç modülde rozet var."""
    earned = sum(1 for b in badges if b)
    n = len(MODULES) - 1  # M0 hariç (giriş)
    if earned >= n:
        return f"🥇 Soyrac Ustası ({earned}/{n})"
    if earned >= n * 0.6:
        return f"🥈 Soyrac Kalfası ({earned}/{n})"
    if earned >= 1:
        return f"🥉 Soyrac Çırağı ({earned}/{n})"
    return f"Başlangıç ({earned}/{n})"
