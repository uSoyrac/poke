"""Bridge Negatif-Çıkarım Motoru (D190) — villain'in range'ini YAPMADIKLARINDAN daralt.

Felsefe (kullanıcının bridge zanaatı): usta oyuncu kendi eline değil, rakibin
NE YAPMADIĞINA bakar. Bridge'de "partner 2♠ demedi → 5+ maça yok"; poker'de
"villain 3-bet yapmadı → QQ+/AK büyük ölçüde düştü". Her pas/zayıf-aksiyon
range'in GÜÇLÜ ucunu siler (negatif çıkarım). Soyrac el-SINIFINI biliyordu ama
villain range'ini sokak-sokak daraltmıyordu — bu o boşluğu kapatır.

İnsan-kafadan-takip edilebilir: combo-combo değil, 7 KOVA ağırlığı (bridge HCP
gibi). Çıktının kalbi `chain` (çıkarım zinciri = öğretim).

API:
  narrow(hero_pos, villain_pos, events) -> NarrowResult
    events: [(street, role, action), ...] villain'in rol+aksiyon dizisi.
  Kovalar: premium/strong/broadway/pairs/suited_conn/suited_ax/air
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

# ── 7 KOVA (villain range — insan-takip-edilebilir sınıflar) ──────────────
BUCKETS = ["premium", "strong", "broadway", "pairs", "suited_conn", "suited_ax", "air"]
_LABEL = {
    "premium": "Premium (QQ+/AK)",
    "strong": "Güçlü (JJ-99/AQ/AJs/KQs)",
    "broadway": "Broadway (KJ/QJ/JT/AT…)",
    "pairs": "Küçük çift (88-22, set-mine)",
    "suited_conn": "Suited connector (T9s-54s)",
    "suited_ax": "Suited Ax (A2s-A9s)",
    "air": "Hava / zayıf offsuit",
}

# ── BAŞLANGIÇ RANGE'LERİ (pozisyon × ilk aksiyon) — kova ağırlıkları 0..1 ──
# Açış (RFI) pozisyon-genişliğine göre; flat (call) CAPPED (premium yok=3bet'lerdi);
# 3-bet POLARİZE (premium + suited_ax/suited_conn blöf).
def _rfi_range(pos: str) -> Dict[str, float]:
    pos = (pos or "").upper()
    if pos in ("UTG", "UTG+1", "UTG+2"):
        return {"premium": 1.0, "strong": 1.0, "broadway": 0.5, "pairs": 0.6,
                "suited_conn": 0.3, "suited_ax": 0.4, "air": 0.0}
    if pos in ("MP", "MP+1", "LJ", "HJ"):
        return {"premium": 1.0, "strong": 1.0, "broadway": 0.8, "pairs": 0.8,
                "suited_conn": 0.6, "suited_ax": 0.7, "air": 0.05}
    if pos in ("CO", "BTN", "BU"):
        return {"premium": 1.0, "strong": 1.0, "broadway": 1.0, "pairs": 1.0,
                "suited_conn": 1.0, "suited_ax": 1.0, "air": 0.25}
    if pos in ("SB", "SB/BTN"):
        return {"premium": 1.0, "strong": 1.0, "broadway": 0.9, "pairs": 0.9,
                "suited_conn": 0.7, "suited_ax": 0.9, "air": 0.15}
    return {b: 0.6 for b in BUCKETS}


@dataclass
class NarrowResult:
    buckets: Dict[str, float]                      # nihai ağırlıklar
    chain: List[str] = field(default_factory=list) # çıkarım zinciri (öğretim)
    summary: str = ""                              # tek-cümle okuma
    shape: str = ""                                # capped/polarized/strong/wide/weak
    running_count: int = 0                         # blackjack tarzı tek-sayı (kafadan takip)
    rc_steps: List[str] = field(default_factory=list)  # adım-adım tally (+1/-2 → toplam)


def _top_buckets(b: Dict[str, float], n: int = 3) -> List[str]:
    live = [(k, v) for k, v in b.items() if v >= 0.15]
    live.sort(key=lambda x: -x[1])
    return [k for k, _ in live[:n]]


def _shape(strength: float, polar: bool, total: float) -> str:
    """Range biçimi — aksiyon-SEMANTİĞİ (güç-sinyali) tabanlı, mutlak-ağırlık değil.
    strength: aksiyon dizisinin kümülatif güç sinyali (cap'ler −, barrel/XR +).
    polar: hat polarize mi (3bet-start / river-bet / triple-barrel).
    total: kalan kova ağırlığı (genişlik için)."""
    if strength <= -2.0:
        return "capped"        # güçlü uç silinmiş → blöf/ince-value seni döver
    if polar and strength >= 1.0:
        return "polarized"     # ya nuts ya blöf → orta elinle bluff-catch
    if strength >= 1.5:
        return "strong"        # value-ağır → saygı duy
    if strength <= -0.5:
        return "weak"          # pasif/cap-eğilimli
    return "wide" if total > 4.0 else "weak"


def starting_range(villain_pos: str, first_action: str) -> Dict[str, float]:
    """Villain'in ilk-aksiyon range'i (pozisyon + open/call/3bet)."""
    fa = (first_action or "open").lower()
    base = _rfi_range(villain_pos)
    if fa in ("open", "raise", "rfi"):
        return dict(base)
    if fa in ("call", "flat", "limp"):
        # FLAT = NEGATİF ÇIKARIM: premium'u büyük ölçüde sil (3-bet'lerdi); flat
        # range = set-mine çiftler + suited broadway/connector + bazı strong slow-play.
        r = dict(base)
        r["premium"] *= 0.10                       # QQ+/AK nadiren flat (trap)
        r["strong"] *= 0.55
        r["air"] *= 0.3
        return r
    if fa in ("3bet", "3-bet", "reraise"):
        # 3-BET = POLARİZE: premium value + suited_ax/suited_conn blöf; orta düşer.
        return {"premium": 1.0, "strong": 0.5, "broadway": 0.2, "pairs": 0.35,
                "suited_conn": 0.5, "suited_ax": 0.8, "air": 0.0}
    return dict(base)


# ── NEGATİF-ÇIKARIM KURALLARI (sokak-sokak) ──────────────────────────────
# Her kural: (yeni_ağırlık-çarpanları, çıkarım-metni). Çoğu GÜÇLÜ ucu siler.
def _apply(buckets: Dict[str, float], street: str, role: str,
           action: str) -> Tuple[Dict[str, float], str, float, bool]:
    """→ (yeni_buckets, çıkarım-notu, güç-sinyali-delta, polar-mı). Çoğu pas GÜÇLÜ
    ucu siler (negatif sinyal); barrel/check-raise pozitif (+ polar)."""
    b = dict(buckets)
    st, ro, ac = street.lower(), role.lower(), action.lower()

    def mult(**kw):
        for k, m in kw.items():
            b[k] = round(b.get(k, 0) * m, 3)

    # PREFLOP: facing-raise'de pas/call → cap
    if st == "preflop" and ro in ("facing_raise", "facing_3bet", "vs_raise"):
        if ac in ("call", "flat"):
            mult(premium=0.12, strong=0.6)
            return b, "↘ Önündeki raise'e 3-bet YAPMADI → QQ+/AK büyük ölçüde düştü (flat = capped)", -2.0, False
        if ac in ("fold",):
            return b, "↘ Fold etti → range bitti", 0.0, False
    # FLOP+ AGRESÖR (preflop raiser): check = cbet YAPMADI → güçlü value cap
    if st in ("flop", "turn", "river") and ro == "aggressor":
        if ac in ("check", "check_back", "x"):
            if st == "flop":
                mult(premium=0.55, strong=0.5, pairs=1.1, broadway=1.05)
                return b, "↘ Agresördü ama flop'u CBET ETMEDİ → set/üst-çift azaldı (give-up/orta ağırlık)", -1.2, False
            mult(premium=0.4, strong=0.45)
            return b, f"↘ {st}'i BARREL ETMEDİ → güçlü value daha da düştü (range zayıfladı)", -1.0, False
        if ac in ("bet", "cbet", "barrel"):
            if st == "river":
                mult(broadway=0.5, pairs=0.5, suited_conn=0.4, air=1.2)
                return b, "↗ River'da hâlâ bahis → POLARİZE (nuts ya da blöf); orta el yok", 1.2, True
            mult(broadway=0.7, pairs=0.7, air=0.8)
            return b, f"↗ {st}'i barrel etti → value + devam-çekme; zayıf orta düştü", (0.8 if st == "turn" else 0.5), False
    # FLOP+ CALLER (preflop caller / OOP defender)
    if st in ("flop", "turn", "river") and ro in ("caller", "defender", "oop"):
        if ac in ("check_call", "call"):
            mult(premium=0.7, air=0.6)
            return b, f"↘ {st}'i check-call → çekme/orta ağırlık (set'i bazen slow-play, ama range zayıf-yoğun)", -0.8, False
        if ac in ("check_raise", "raise", "xr"):
            mult(broadway=0.4, pairs=1.3, suited_conn=1.1, air=0.5, premium=1.2, strong=1.1)
            return b, f"↗ {st}'te check-raise → POLARİZE güçlü: set/2-pair/güçlü çekme (orta el değil)", 2.0, True
        if ac in ("donk", "lead"):
            mult(premium=0.5, strong=0.7, suited_conn=1.2, pairs=1.1)
            return b, f"↘ {st}'te donk-bet → genelde orta/çekme (gerçek nuts check-raise'i seçerdi)", -0.3, False
        if ac in ("check", "x"):
            mult(premium=0.6, strong=0.7)
            return b, f"↘ {st}'i check → güçlü value azaldı (genelde değer için bahis gelirdi)", -0.8, False
        if ac in ("fold",):
            return b, "↘ Fold → range bitti", 0.0, False
    return b, f"· {st} {role} {action} (nötr)", 0.0, False


def narrow(villain_pos: str, events: List[Tuple[str, str, str]],
           first_action: str = "open") -> NarrowResult:
    """Villain aksiyon dizisini negatif-çıkarımla işle → daralmış range + zincir.

    events: [(street, role, action)] — role ∈ aggressor/caller/facing_raise/...
    first_action: villain'in preflop ilk aksiyonu (open/call/3bet)."""
    buckets = starting_range(villain_pos, first_action)
    chain = [f"🎴 Başlangıç ({villain_pos} {first_action}): "
             + ", ".join(f"{_LABEL[k].split(' ')[0]}" for k in _top_buckets(buckets))]
    # 3-bet başlangıcı doğal polarize; flat başlangıcı capped sinyali
    _is3 = (first_action or "").lower() in ("3bet", "3-bet", "reraise")
    strength = 1.0 if _is3 else 0.0
    polar = _is3
    # RUNNING COUNT (D196, blackjack): aksiyon-başına temiz tamsayı +/−, tek koşan sayı.
    # Kafadan takip edilir; sdelta'nın yuvarlanmışı. 3bet açılışı +1, flat −2 ile başlar.
    rc = 1 if _is3 else 0
    rc_steps = [f"{first_action} → {rc:+d}"]
    for ev in events:
        street, role, action = (list(ev) + ["", "", ""])[:3]
        buckets, note, sdelta, p = _apply(buckets, street, role, action)
        strength += sdelta
        polar = polar or p
        d = int(round(sdelta))
        rc += d
        rc_steps.append(f"{street[:1].upper()}:{action} {d:+d} → {rc:+d}")
        chain.append(note)
    shape = _shape(strength, polar, sum(buckets.values()))
    tops = _top_buckets(buckets)
    _shape_read = {
        "capped": "CAPPED — güçlü ucu yok → blöf yap, ince value-bet'i büyüt, büyük bahse saygı YOK",
        "polarized": "POLARİZE — ya nuts ya blöf → orta elinle BLUFF-CATCH (büyük overbet'e fold)",
        "strong": "GÜÇLÜ/value-ağır → saygı duy, blöf yapma, marjinali bırak",
        "wide": "GENİŞ → value'nu değerlendir, ince value-bet kârlı",
        "weak": "ZAYIF/dağınık → agresyon + value bet",
    }
    summary = (f"Villain range biçimi: {shape.upper()} → " + _shape_read.get(shape, ""))
    chain.append(f"🧠 SONUÇ: {', '.join(_LABEL[t] for t in tops)}")
    return NarrowResult(buckets=buckets, chain=chain, summary=summary, shape=shape,
                        running_count=rc, rc_steps=rc_steps)


def running_count_read(rc: int) -> str:
    """Tek-sayı running-count → hızlı okuma (blackjack: yüksek count = avantaj)."""
    if rc <= -3:
        return f"RC {rc:+d} → ÇOK ZAYIF/capped: blöf + ince value, büyük bahse saygı yok"
    if rc <= -1:
        return f"RC {rc:+d} → zayıf eğilim: agresyona dön, value-bet"
    if rc >= 3:
        return f"RC {rc:+d} → ÇOK GÜÇLÜ/polarize: saygı + orta elinle bluff-catch"
    if rc >= 1:
        return f"RC {rc:+d} → güçlü eğilim: marjinali bırak"
    return f"RC {rc:+d} → nötr: standart oyna"


def narrow_line(villain_pos: str, events: List[Tuple[str, str, str]],
                first_action: str = "open") -> str:
    """Tek-string özet (koç paneli/akademi için)."""
    r = narrow(villain_pos, events, first_action)
    return " → ".join(r.chain) + f"\n{r.summary}"
