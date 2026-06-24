"""SAYIM-MVP (D312): rakip OKUMA-SAYACI R — masada villain başına TEK tamsayı.

Agent-ordusu tasarımının (soyrac-opponent-read-system) düşmanca-denetimden geçen savunulabilir
çekirdeği. Blackjack Hi-Lo analojisi — AMA poker'de villain-başına ayrı sayaç olduğundan masada
SADECE el-içi DİZİ sinyalleri taşınır (frekans-statları HUD/post-session'ın işi, insan kafasında DEĞİL).

KISITLAR (mutlak):
• %100 İNSAN-HESAPLANABİLİR: masada kafada/kağıtta tek tamsayı R. Ölçek TEK-KAYNAK
  range_narrowing motoru (sdelta) — panel=insan=motor AYNI sayıyı bulur (test_read_count_scale_alignment).
• READ-GATED / advice-only: villain yok + dizi yok → R=0, 'GTO' (identity). soyrac base
  advice_from_hand'e ASLA girmez → bot fidelity 0-sapma korunur.
• PRIOR TEK BAŞINA SAPMA AÇMAZ: tip-prior ±1 ile sınırlı; |R|≥2 sapma DAİMA gözlenen dizi ister.
• +EV = DÜŞÜK-GÜVEN kabaca-monoton güç-proxy (kanıtlanmış log-LR DEĞİL); belirsizde GTO'ya çök.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.poker.opponent_typology import type_prior
from app.poker.range_narrowing import narrow

_DEV_GTO = "|R|<2 → GTO-BAZ (MDF/pot-odds — okuma belirsiz, uydurma edge yok)"
_DEV_VALUE = "R≥+2 VALUE-AĞIR → marjinali FOLD, kendi blöfünü KES, büyük bahse SAYGI"
_DEV_CAPPED = "R≤−2 CAPPED/zayıf → ince value-bet'i BÜYÜT + blöfle, büyük bahse saygı YOK"

_SHAPE_READ = {
    "capped": "CAPPED — güçlü uç yok",
    "polarized": "POLARİZE — ya nuts ya blöf (bluff-catch)",
    "strong": "GÜÇLÜ/value-ağır",
    "wide": "GENİŞ",
    "weak": "ZAYIF/dağınık",
}


@dataclass
class ReadCount:
    R: int                       # masada taşınan TEK sayı (prior + gözlenen dizi)
    prior: int                   # tipten el-başı prior (±1)
    seq: int                     # gözlenen el-içi dizi deltası (motor running_count)
    shape: str                   # capped/polarized/strong/wide/weak
    confidence: str              # 'high' (dizi gözlendi) / 'low' (yalnız prior → GTO)
    read: str                    # kısa insan-okuması
    deviation: str               # okuma→sapma kuralı
    steps: List[str] = field(default_factory=list)   # rc tally (kafadan doğrula)


def read_count(villain_type: Optional[str],
               events: Optional[List[Tuple[str, str, str]]] = None,
               *, villain_pos: str = "BTN",
               first_action: str = "open") -> ReadCount:
    """Tip + gözlenen el-içi dizi → tek-sayı R okuması (advice-only, read-gated).

    villain_type: classify_hellmuth anahtarı (mouse/lion/jackal/elephant/eagle) ya da None.
    events: [(street, role, action)] — range_narrowing motoruna birebir geçer.
    first_action: villain'in preflop ilk aksiyonu (open/flat/3bet).

    READ-GATED: villain_type=None + events boş → R=0, confidence='low', 'GTO' (identity).
    Ölçek TEK-KAYNAK range_narrowing.narrow().running_count; R = prior + dizi.
    """
    prior = type_prior(villain_type)
    evs = list(events or [])
    nr = narrow(villain_pos, evs, first_action)
    seq = int(nr.running_count)            # motor running_count = gözlenen dizi deltası (tamsayı)
    observed = seq != 0                    # gözlenen el-içi dizi sinyali var mı (ikili güven)
    R = prior + seq
    # PRIOR TEK BAŞINA SAPMA AÇAMAZ: prior ±1 → |R|≥2 ancak gözlenen dizi (seq≠0) ile mümkün.
    # 'and observed' açık-güvenlik: belirsizde (dizi yok) DAİMA GTO-baz.
    if abs(R) >= 2 and observed:
        deviation = _DEV_VALUE if R >= 2 else _DEV_CAPPED
    else:
        deviation = _DEV_GTO
    confidence = "high" if observed else "low"
    read = f"R={R:+d} · {_SHAPE_READ.get(nr.shape, nr.shape)}"
    return ReadCount(R=R, prior=prior, seq=seq, shape=nr.shape,
                     confidence=confidence, read=read, deviation=deviation,
                     steps=list(nr.rc_steps))
