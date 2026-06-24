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


# ── Villain aksiyon-dizisi çıkarımı (TEK-KAYNAK: canlı koç + sim doğrulama aynı R'yi bulur) ──
def villain_sequence(hand, hero_idx) -> Tuple[Optional[int], str, List[Tuple[str, str, str]]]:
    """hand.actions → (villain_idx, first_action, events) range_narrowing formatında.
    villain = hero'nun karşı karşıya olduğu son-agresör (yoksa aktif tek opp). None → okuma yok."""
    from app.engine.hand_state import ActionType, Street
    _ST = {Street.PREFLOP: "preflop", Street.FLOP: "flop", Street.TURN: "turn", Street.RIVER: "river"}
    acts = getattr(hand, "actions", None) or []
    # preflop raiser (PFR)
    pfr = None
    for a in acts:
        if a.street == Street.PREFLOP and a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
            pfr = a.player_idx
            break
    # main villain
    folded = {a.player_idx for a in acts if a.action_type == ActionType.FOLD}
    active = [i for i, p in enumerate(hand.players)
              if i != hero_idx and i not in folded and not getattr(p, "is_folded", False)]
    if not active:
        return None, "open", []
    vidx = active[0]
    for a in reversed(acts):
        if a.player_idx in active and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            vidx = a.player_idx
            break
    # events
    role = "aggressor" if vidx == pfr else "caller"
    first_action, events, seen_pre = "open", [], False
    for a in (x for x in acts if x.player_idx == vidx):
        stn = _ST.get(a.street, "flop")
        at = a.action_type
        if a.street == Street.PREFLOP:
            if not seen_pre:
                seen_pre = True
                if at in (ActionType.RAISE, ActionType.ALL_IN):
                    first_action = "3bet" if vidx != pfr else "open"
                elif at == ActionType.CALL:
                    first_action = "flat"
                    events.append(("preflop", "facing_raise", "call"))
            continue
        if role == "aggressor":
            if at == ActionType.CHECK:
                events.append((stn, "aggressor", "check"))
            elif at in (ActionType.BET, ActionType.ALL_IN):
                events.append((stn, "aggressor", "barrel" if a.street in (Street.TURN, Street.RIVER) else "cbet"))
            elif at == ActionType.RAISE:
                events.append((stn, "aggressor", "barrel"))
            elif at == ActionType.CALL:
                events.append((stn, "aggressor", "call"))
        else:
            if at == ActionType.CHECK:
                events.append((stn, "caller", "check"))
            elif at == ActionType.RAISE:
                events.append((stn, "caller", "check_raise"))
            elif at == ActionType.CALL:
                events.append((stn, "caller", "check_call"))
            elif at in (ActionType.BET, ActionType.ALL_IN):
                events.append((stn, "caller", "donk"))
    return vidx, first_action, events

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


# ── D313-VALIDATED el-gücü-gate'li sapma kuralları ────────────────────────────
# Sim doğrulaması: ham overlay (gating'siz) −EV (çöple call); el-gücüyle gate'lenince +EV
# (soft +28 / orta +12.6 / tough +4.3 bb/100). Ham R YÖN verir, tier hangi eli KAPSADIĞINI söyler.
_MARGINAL_TIERS = ("BLUFF-CATCH", "ZAYIF", "ORTA", "HAVA")
_VALUE_TIERS = ("GÜÇLÜ", "NUT")
_ATTACK_VALUE_TIERS = ("ORTA", "BLUFF-CATCH", "GÜÇLÜ")    # capped'e karşı ince value/blöf BET


def read_deviation(R: int, tier: str, *, facing_bet: bool, eq: float = 0.0) -> Tuple[bool, str, str]:
    """Ham R + hero el-gücü(tier) → somut sapma (D313-validated). Döner (changed, action, note).
    changed=False → GTO-baz KORU (value'yu fold'lama, çöple call'lama)."""
    t = (tier or "").upper()
    if abs(R) < 2:
        return False, "", "|R|<2 → GTO-baz (okuma belirsiz)"
    if R >= 2:                                   # value-ağır villain
        if facing_bet and t in _MARGINAL_TIERS and t not in _VALUE_TIERS:
            return True, "FOLD", "R≥+2 value-ağır + elin MARJİNAL → bluff-catch BIRAK (FOLD)"
        if not facing_bet and t in ("HAVA", "ZAYIF"):
            return True, "CHECK", "R≥+2 value-ağır → kendi blöfünü KES (CHECK)"
        return False, "", "R≥+2 ama elin value/uygun değil → baz KORU (value'yu fold'lama)"
    # R ≤ −2: capped/zayıf villain → saldır (çöple DEĞİL)
    if not facing_bet and t in _ATTACK_VALUE_TIERS:
        return True, "BET", "R≤−2 capped → ince value/blöf BET (büyük bahse saygı yok)"
    if facing_bet and t in ("BLUFF-CATCH", "ORTA") and eq >= 0.30:
        return True, "CALL", "R≤−2 capped → HAFİF CALL (yeterli equity, çöp değil)"
    return False, "", "R≤−2 ama spot uygun değil → baz KORU (çöple call'lama)"


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
               first_action: str = "open",
               dizi_kilit: bool = False) -> ReadCount:
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
    # DİZİ-KİLİDİ (tasarım decision_rule #4): postflop check-raise = value-lock floor (R≥+2;
    # naive-toplam flat(−2)+XR(+2)=0 yapıp trap'i kaçırıyordu). A/B (D314): EV-NÖTR (gürültü içinde) —
    # tough'ta +3.3, soft'ta −2.1 → DEFAULT KAPALI (naive=validated baseline, soft'ta en iyi);
    # tough-saha için OPT-IN (dizi_kilit=True; yetkin oyuncu XR'ı gerçekten value).
    if dizi_kilit and any(a in ("check_raise", "xr") for (_, _, a) in evs):
        R = max(R, 2)
        observed = True
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
