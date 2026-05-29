"""Canlı GTO advice — oyun-içi action butonları için.

Play Session / Tournament'ta o anki spotun GTO frekanslarını döndürür:
  FOLD %35  ·  CALL %42  ·  RAISE %23  ·  ALLIN %0

Canlı game state → GTO scenario mapping:
  - effective stack (bb) hesapla
  - preflop betting history'den scenario belirle:
      0 raise  → RFI (açış)        [stack ≤ ~15bb → Push/Fold]
      1 raise  → vs RFI (defender) [vs_position = raiser]
      2+ raise → vs 3-bet
  - hero hand key + position → get_action() → frekanslar
  - frekansları görünür butonlara eşle

DÜRÜSTLÜK (aman hata olmasın):
  - PREFLOP: gerçek GTO data (EXACT/APPROX, gto_provenance ile etiketli)
  - POSTFLOP: bizim preflop chart'lar postflop bilmez → available=False,
    "Solver gerekli (Solver Sandbox / TexasSolver)" notu. Yanlış % gösterip
    yanlış öğretmektense hiç göstermiyoruz.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from app.engine.hand_state import ActionType, HandState, Street
from app.engine.bot_brain import hand_key


# Live pozisyon adlarını GTO chart pozisyonlarına eşle
_POS_MAP = {
    "UTG": "UTG", "UTG+1": "MP", "UTG+2": "MP", "LJ": "MP", "MP": "MP",
    "MP+1": "MP", "HJ": "CO", "CO": "CO", "BTN": "BTN", "BU": "BTN",
    "SB": "SB", "BB": "BB", "SB/BTN": "BTN",
}
# Pozisyon sıralaması (opener'ı belirlemek için: erken → geç)
_POS_ORDER = ["UTG", "UTG+1", "UTG+2", "LJ", "MP", "MP+1", "HJ", "CO", "BTN", "SB", "BB"]


@dataclass
class LiveAdvice:
    available: bool = False
    # Aksiyon frekansları (%)
    fold: float = 0.0
    call: float = 0.0
    raise_: float = 0.0
    allin: float = 0.0
    scenario: str = ""          # "RFI" / "vs RFI (UTG)" / "vs 3-bet" / "Push/Fold"
    tier_icon: str = ""         # ✅ / 🟡 / 🟠 / ❌
    tier_label: str = ""
    note: str = ""
    hand_key: str = ""
    stack_bb: float = 0.0
    equity: float = 0.0         # hero equity % vs modellenmiş villain range (postflop)

    def per_action(self) -> Dict[ActionType, float]:
        """ActionType → % eşlemesi (görünür butonlara uygulamak için)."""
        return {
            ActionType.FOLD: self.fold,
            ActionType.CALL: self.call,
            ActionType.CHECK: self.call,    # check, call ile aynı slot
            ActionType.RAISE: self.raise_,
            ActionType.BET: self.raise_,
            ActionType.ALL_IN: self.allin,
        }


def _norm_pos(pos: str) -> str:
    return _POS_MAP.get((pos or "").upper(), "CO")


# Postflop equity cache — (hand_key, board_code, to_call_bucket) → advice
_PF_CACHE: Dict[tuple, "LiveAdvice"] = {}


def _villain_continuing_range(n_active: int, bet_frac: float = 0.0) -> list:
    """Postflop villain'in devam ettiği makul range (top-X% playability).

    ``bet_frac`` > 0 ise villain BU bet'i attı/devam etti → range'i daralt:
    büyük bet = daha güçlü/polarize range, küçük bet = daha geniş. Pasif
    (check, bet_frac=0) durumda baz range kullanılır (capped, geniş).
    """
    from app.poker.gto_generator import get_ranked_hands
    ranked = get_ranked_hands()
    # Heads-up postflop'ta villain ~top %55, multiway daha sıkı
    pct = 55 if n_active <= 2 else (42 if n_active == 3 else 32)
    # Aksiyon-duyarlı daraltma: villain bahis yaptıysa range güçlenir.
    if bet_frac > 0:
        # 1/3 pot → ×0.88, 1/2 → ×0.82, 2/3 → ×0.76, pot → ×0.68, overbet → ~0.6
        factor = max(0.55, 1.0 - min(0.45, bet_frac * 0.42))
        pct *= factor
    target = 1326 * pct / 100
    out, acc = [], 0
    for hk in ranked:
        c = 6 if len(hk) == 2 else (4 if hk.endswith("s") else 12)
        out.append(hk)
        acc += c
        if acc >= target:
            break
    return out


def _postflop_advice(hand: HandState, hero_idx: int, adv: LiveAdvice) -> LiveAdvice:
    """Equity-temelli postflop frekans modeli (🟠 CONCEPT).

    1) Hero equity'sini modellenmiş villain devam-range'ine karşı hesapla (MC).
    2) pot odds + equity → action frekansları (GTO-flavored model).
    Solver-exact DEĞİL — yön doğru, dürüstçe CONCEPT etiketli.
    """
    hero = hand.players[hero_idx]
    from app.engine.bot_brain import hand_key
    hk = hand_key(hero.hole_cards[0], hero.hole_cards[1])
    adv.hand_key = hk
    bb = max(hand.big_blind, 0.01)
    pot = hand.pot
    to_call = hand.to_call(hero_idx)

    board_code = "".join(c.code for c in hand.community)
    hero_code = hero.hole_cards[0].code + hero.hole_cards[1].code
    tc_bucket = round(to_call / max(pot, 0.01), 1)   # pot-oranı bucket'ı
    cache_key = (hero_code, board_code, tc_bucket)
    cached = _PF_CACHE.get(cache_key)
    if cached is not None:
        return cached

    # ── Equity (MC, hız için sınırlı iter) ──
    try:
        from app.poker.mc_equity import equity_hand_vs_range
        # Villain bet attıysa (to_call>0) range'i bet boyutuna göre daralt
        bet_frac = (to_call / max(pot, 0.01)) if to_call > 0.01 else 0.0
        vr = _villain_continuing_range(hand.active_count, bet_frac)
        r = equity_hand_vs_range(hero_code, vr, board=" ".join(
            c.code for c in hand.community), iterations=1200)
        eq = r.a_equity / 100.0
    except Exception:
        return adv   # available=False kalır

    # ── Equity → frekans modeli ──
    if to_call > 0.01:
        # Facing a bet: pot odds = call için gereken equity
        pot_odds = to_call / (pot + to_call)
        # Value raise: yüksek equity
        raise_freq = max(0.0, min(0.55, (eq - 0.68) * 1.8))
        # Bluff raise: çok düşük equity + küçük bet (blocker/leverage)
        if eq < 0.30 and to_call / max(pot, 0.01) < 0.6:
            raise_freq = max(raise_freq, 0.10)
        # Fold: equity pot odds'un altındaysa
        if eq < pot_odds:
            fold_freq = min(0.92, (pot_odds - eq) / max(pot_odds, 0.01) * 1.3)
        else:
            fold_freq = max(0.0, (pot_odds - eq + 0.10) * 0.5)
        fold_freq = max(0.0, min(0.92, fold_freq))
        call_freq = max(0.0, 1.0 - raise_freq - fold_freq)
        adv.raise_ = round(100 * raise_freq, 0)
        adv.call = round(100 * call_freq, 0)
        adv.fold = round(100 * fold_freq, 0)
        adv.allin = 0.0
    else:
        # No bet: bet (value/bluff) or check
        # Value bet: yüksek equity
        bet_value = max(0.0, min(0.85, (eq - 0.55) * 2.2))
        # Bluff bet: düşük equity (showdown value yok)
        bet_bluff = max(0.0, (0.30 - eq) * 0.9) if eq < 0.30 else 0.0
        bet_freq = min(0.90, bet_value + bet_bluff)
        adv.raise_ = round(100 * bet_freq, 0)   # BET butonu
        adv.call = round(100 * (1.0 - bet_freq), 0)  # CHECK slotu
        adv.fold = 0.0
        adv.allin = 0.0

    adv.available = True
    adv.equity = round(eq * 100, 1)
    adv.scenario = f"Postflop ({hand.street_name}, eq %{eq*100:.0f})"
    adv.tier_icon = "🟠"
    adv.tier_label = "Equity-temelli (CONCEPT)"
    adv.note = ("Equity-temelli model — solver-exact değil. Tam GTO için "
                "Solver Sandbox kullan. Yön doğru, kesin frekans yaklaşık.")
    adv.stack_bb = round((hero.stack + hero.current_bet) / bb, 1)
    _PF_CACHE[cache_key] = adv
    if len(_PF_CACHE) > 500:
        _PF_CACHE.clear()
    return adv


def _count_preflop_raises_before_hero(hand: HandState, hero_idx: int):
    """(raise sayısı, son raiser'ın pozisyonu) — hero konuşmadan önce."""
    raises = 0
    last_raiser_pos = None
    for a in hand.actions:
        if a.street != Street.PREFLOP:
            break
        if a.player_idx == hero_idx:
            break   # hero'nun ilk aksiyonuna kadar
        if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
            raises += 1
            seat = hand.players[a.player_idx]
            last_raiser_pos = seat.position
    return raises, last_raiser_pos


def live_gto_advice(hand: HandState, hero_idx: int,
                    mode: str = "cash") -> LiveAdvice:
    """O anki hero spotu için GTO advice döndür."""
    adv = LiveAdvice()
    if not hand or hand.is_complete:
        return adv
    hero = hand.players[hero_idx]
    if not hero.hole_cards or len(hero.hole_cards) < 2:
        return adv

    bb = max(hand.big_blind, 0.01)
    # Effective stack: hero stack + bu el yatırdığı (street başı stack)
    eff_stack = (hero.stack + hero.current_bet) / bb
    adv.stack_bb = round(eff_stack, 1)

    # ── POSTFLOP: kendi equity-temelli motorumuz (🟠 CONCEPT) ──
    if hand.street != Street.PREFLOP:
        return _postflop_advice(hand, hero_idx, adv)

    hk = hand_key(hero.hole_cards[0], hero.hole_cards[1])
    adv.hand_key = hk
    pos = _norm_pos(hero.position)

    # ── Scenario belirle ──
    n_raises, raiser_pos = _count_preflop_raises_before_hero(hand, hero_idx)
    vs_pos = _norm_pos(raiser_pos) if raiser_pos else None

    if eff_stack <= 16 and n_raises == 0:
        scenario = "Push/Fold"
        adv.scenario = f"Push/Fold {adv.stack_bb:.0f}bb"
    elif n_raises == 0:
        scenario = "RFI"
        adv.scenario = "RFI (açış)"
    elif n_raises == 1:
        scenario = "vs RFI"
        adv.scenario = f"vs RFI ({vs_pos})" if vs_pos else "vs RFI"
    else:
        scenario = "vs 3-bet"
        adv.scenario = "vs 3-bet"

    # MTT modu kısa stack'te otomatik
    use_mode = "MTT" if (mode == "MTT" or eff_stack <= 40) else "cash"

    # ── GTO lookup ──
    try:
        from app.poker.gto_ranges import get_action
        action = get_action(pos, hk, scenario, int(round(eff_stack)),
                            use_mode, vs_position=vs_pos)
    except Exception:
        return adv

    r = float(action.get("raise", 0))
    c = float(action.get("call", 0))
    f = float(action.get("fold", 0))

    # Push/Fold: raise = JAM → allin slotuna
    if scenario == "Push/Fold":
        adv.allin = r
        adv.fold = f + c   # push/fold'da call yok
        adv.call = 0.0
        adv.raise_ = 0.0
    else:
        adv.raise_ = r
        adv.call = c
        adv.fold = f
        adv.allin = 0.0

    # ── Provenance tier ──
    try:
        from app.poker.gto_provenance import range_provenance
        tier = range_provenance(scenario, pos, int(round(eff_stack)),
                                use_mode, vs_pos)
        adv.tier_icon = tier.icon
        adv.tier_label = tier.label
    except Exception:
        adv.tier_icon = "🟡"
        adv.tier_label = "Yaklaşık"

    adv.available = True
    return adv
