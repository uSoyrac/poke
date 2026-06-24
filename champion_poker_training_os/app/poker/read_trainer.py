"""Rakip-okuma trainer motoru — saf fonksiyon, UI bağımsız (geliştirme #2).

Bir villain'in davranışını (stat snapshot + aksiyon log/'tell'ler) üretir;
kullanıcı tipini tahmin eder; skorlanır + exploit önerisi verilir. Ground-truth
opponent_typology.classify_hellmuth'tan gelir (tek kaynak) → gerçek bot
tiplemesiyle tutarlı. Felsefe: 'doğru oyun rakibe + okumaya göre değişir'.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from app.engine.bot_brain import BOT_ARCHETYPES
from app.poker.exploit_advice import exploit_line
from app.poker.opponent_typology import HELLMUTH_ANIMALS, classify_hellmuth

# Hellmuth hayvan adları (seçenek havuzu) — tek kaynak
_ANIMAL_NAMES = [v[1] for v in HELLMUTH_ANIMALS.values()]

# Tip → gözlemlenebilir 'tell' şablonları (okuma materyali)
_TELLS = {
    "Elephant": [
        "Preflop limp/call ile çok geniş giriyor (VPIP yüksek, PFR düşük)",
        "Flop'ta herhangi bir parça/draw ile call ediyor",
        "River'da dip çift ile bile bahsi ödüyor — neredeyse fold etmiyor",
        "Nadiren raise/blöf eder; pasif sticky",
    ],
    "Mouse": [
        "Ellerin çoğunu fold ediyor, sadece premium giriyor (VPIP düşük)",
        "C-bet'lere yüksek frekansla fold (overfold)",
        "Agresyona katlanıyor, blöf yapmıyor",
        "Açışını/c-bet'ini çalmak kolay",
    ],
    "Jackal": [
        "Light 3-bet/4-bet atıyor (3bet yüksek)",
        "Turn-river barrel ile baskı kuruyor",
        "Overbet ve blöf sık — geniş, agresif range",
        "Hafif ellerle bile pot şişiriyor",
    ],
    "Lion": [
        "Sıkı-agresif, pozisyon-duyarlı açıyor",
        "Dengeli value/blöf oranı",
        "Agresyona düşünerek karşılık veriyor",
        "Belirgin leak az — solid reg",
    ],
    "Eagle": [
        "Elit/dengeli — sömürülecek leak neredeyse yok",
        "Range/nut avantajını net kullanıyor",
        "Polarize sizing (value + saf blöf)",
        "Okuması zor; çizgisi GTO'ya yakın",
    ],
}


@dataclass
class ReadDrill:
    villain_name: str
    archetype: str               # ground-truth arketip (üretim kaynağı)
    stats: dict                  # vpip, pfr, af, fold_to_cbet, three_bet, hands
    action_log: List[str]        # gözlemlenen 'tell'ler (okuma materyali)
    correct_type: str            # Hellmuth tipi (classify_hellmuth)
    correct_exploit: str         # exploit_line önerisi
    choices: List[str] = field(default_factory=lambda: list(_ANIMAL_NAMES))


def generate_read_drill(rng: Optional[random.Random] = None) -> ReadDrill:
    """Rastgele bir arketipten gözlem-gürültülü bir okuma drill'i üret."""
    rng = rng or random.Random()
    name = rng.choice(list(BOT_ARCHETYPES.keys()))
    p = BOT_ARCHETYPES[name]

    def jit(v, amt):
        return max(0.0, round(float(v) + rng.uniform(-amt, amt), 1))

    vpip = max(1.0, jit(p.vpip, 2.0))
    pfr = min(vpip, jit(p.pfr, 2.0))
    stats = {
        "vpip": vpip,
        "pfr": pfr,
        "af": max(0.1, round(p.aggression + rng.uniform(-0.3, 0.3), 1)),
        "fold_to_cbet": jit(p.fold_to_cbet, 4.0),
        "three_bet": jit(p.three_bet, 1.5),
        "river_bluff": p.river_bluff,
        "hands": rng.randint(40, 220),
    }
    _, ctype, _ = classify_hellmuth(stats["vpip"], stats["pfr"], stats["af"],
                                    stats["river_bluff"])
    tells = list(_TELLS.get(ctype, ["Belirgin bir eğilim yok"]))
    rng.shuffle(tells)
    return ReadDrill(
        villain_name=f"villain_{rng.randint(1, 9)}",
        archetype=name,
        stats=stats,
        action_log=tells[:3],
        correct_type=ctype,
        correct_exploit=exploit_line(stats) or f"{ctype} — dengeli oyna.",
    )


def score_read(guess: str, drill: ReadDrill) -> dict:
    """Kullanıcının tip tahminini skorla → {correct, explanation, exploit}."""
    correct = (guess == drill.correct_type)
    s = drill.stats
    statline = (f"VPIP %{s['vpip']:.0f} / PFR %{s['pfr']:.0f} / "
                f"AF {s['af']} / fold-to-cbet %{s['fold_to_cbet']:.0f}")
    if correct:
        explanation = f"✓ Doğru okuma — {drill.correct_type} ({statline})."
    else:
        explanation = (f"✗ Yanlış. Doğrusu: {drill.correct_type} ({statline}). "
                       f"Bu profil tipik {drill.archetype} davranışı.")
    return {"correct": correct, "explanation": explanation,
            "exploit": drill.correct_exploit}


# ── ÇIKARIM ZİNCİRİ DRILL (D192, bridge negatif-çıkarım — range_narrowing) ──
_INFERENCE_SCENARIOS = [
    ("CO", "open",
     [("preflop", "facing_3bet", "call"), ("flop", "aggressor", "check")],
     "CO açtı · 3-bet'ine CALL etti (4-bet yok) · flop'u CHECK etti (cbet yok)"),
    ("UTG", "open",
     [("flop", "aggressor", "bet"), ("turn", "aggressor", "check")],
     "UTG açtı · flop CBET · turn CHECK (barrel yok)"),
    ("BB", "call",
     [("flop", "caller", "check_raise")],
     "BTN'e karşı BB CALL etti · flopta CHECK-RAISE"),
    ("BTN", "3bet",
     [("flop", "aggressor", "bet"), ("turn", "aggressor", "barrel"),
      ("river", "aggressor", "bet")],
     "BTN 3-BET etti · flop+turn+river üç sokak BARREL"),
    ("HJ", "open",
     [("flop", "aggressor", "bet"), ("turn", "aggressor", "barrel")],
     "HJ açtı · flop+turn BARREL (river kaldı)"),
    ("SB", "open",
     [("preflop", "facing_3bet", "call"), ("flop", "caller", "check_call"),
      ("turn", "caller", "check")],
     "SB açtı · 3-bet'e CALL · flop CHECK-CALL · turn CHECK"),
    ("MP", "open",
     [("flop", "caller", "donk")],
     "MP açtı (sonra caller) · flopta DONK-BET"),
]

_SHAPE_LABELS = {
    "capped": "CAPPED (güçlü uç yok)",
    "polarized": "POLARİZE (nuts ya da blöf)",
    "strong": "GÜÇLÜ (value-ağır)",
    "wide": "GENİŞ (dağınık)",
    "weak": "ZAYIF (pasif)",
}


@dataclass
class InferenceDrill:
    villain_pos: str
    headline: str
    chain: List[str]
    correct_shape: str
    summary: str
    choices: List[str]


def generate_inference_drill(rng: Optional[random.Random] = None) -> InferenceDrill:
    """Bir aksiyon-dizisi üret → range_narrowing ile doğru biçimi (shape) bul;
    kullanıcı 'villain range'i hangi biçim?' tahmin eder, reveal = çıkarım zinciri."""
    rng = rng or random
    pos, fa, events, headline = rng.choice(_INFERENCE_SCENARIOS)
    from app.poker.range_narrowing import narrow
    r = narrow(pos, events, first_action=fa)
    distractors = [s for s in _SHAPE_LABELS if s != r.shape]
    rng.shuffle(distractors)
    opts = [r.shape] + distractors[:3]
    rng.shuffle(opts)
    return InferenceDrill(
        villain_pos=pos, headline=headline, chain=r.chain,
        correct_shape=r.shape, summary=r.summary,
        choices=[_SHAPE_LABELS[s] for s in opts],
    )


def score_inference(choice_label: str, drill: InferenceDrill) -> dict:
    """Biçim tahminini skorla → {correct, chain, summary, correct_label}."""
    correct = (choice_label == _SHAPE_LABELS[drill.correct_shape])
    return {"correct": correct, "chain": drill.chain, "summary": drill.summary,
            "correct_label": _SHAPE_LABELS[drill.correct_shape]}


# ── SAYIM-MVP 'R tahmin et' drill'i (D315): tek-sayı okuma-sayacını öğret ──
_RC_TYPE_LABEL = {
    "mouse": "🐭 Mouse (tight-passive, prior +1)",
    "lion": "🦁 Lion (TAG, prior 0)",
    "jackal": "🐺 Jackal (LAG/blöfçü, prior −1)",
    "elephant": "🐘 Elephant (station, prior +1)",
    "eagle": "🦅 Eagle (elit, prior +1)",
}


@dataclass
class ReadCountDrill:
    villain_pos: str
    villain_type: str          # hellmuth anahtarı
    headline: str
    correct_R: int
    steps: List[str]           # rc tally (reveal — kafadan doğrula)
    read: str
    choices: List[int]


def generate_read_count_drill(rng: Optional[random.Random] = None) -> ReadCountDrill:
    """Aksiyon-dizisi + villain tipi ver → kullanıcı tek-sayı R'yi hesaplar (SAYIM-MVP).
    Reveal = tally adımları (prior + dizi → R)."""
    rng = rng or random
    pos, fa, events, headline = rng.choice(_INFERENCE_SCENARIOS)
    vtype = rng.choice(list(_RC_TYPE_LABEL))
    from app.poker.read_count import read_count
    rc = read_count(vtype, events, villain_pos=pos, first_action=fa)
    choices = list(range(rc.R - 2, rc.R + 3))     # 5 ardışık tamsayı (doğru ortada)
    return ReadCountDrill(
        villain_pos=pos, villain_type=vtype,
        headline=f"{_RC_TYPE_LABEL[vtype]}\n{headline}",
        correct_R=rc.R, steps=rc.steps, read=rc.read, choices=choices)


def score_read_count(choice_R: int, drill: ReadCountDrill) -> dict:
    """R tahminini skorla → {correct, correct_R, steps, read}."""
    return {"correct": (choice_R == drill.correct_R), "correct_R": drill.correct_R,
            "steps": drill.steps, "read": drill.read}
