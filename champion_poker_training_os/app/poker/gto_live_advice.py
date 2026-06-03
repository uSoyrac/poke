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

from dataclasses import dataclass
from typing import Dict

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
    combo_note: str = ""        # river bluff-catch: value/bluff combo + blocker (elit koç)

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


def _hero_has_initiative(hand: HandState, hero_idx: int) -> bool:
    """Hero preflop'taki son agresör mü (postflop c-bet inisiyatifi)?"""
    last = None
    for a in hand.actions:
        if a.street != Street.PREFLOP:
            break
        if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
            last = a.player_idx
    return last == hero_idx


def _prev_street_checked_through(hand: HandState) -> bool:
    """Bir önceki sokak agresif aksiyon olmadan (check'lenerek) mi geçildi?

    Postflop'ta önceki sokakta hiç BET/RAISE/ALL_IN yoksa agresör inisiyatifi
    bırakmış demektir → probe bet fırsatı.
    """
    cur = hand.street
    order = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]
    try:
        idx = order.index(cur)
    except ValueError:
        return False
    if idx <= 1:                       # flop'ta "önceki postflop sokak" yok
        return False
    prev = order[idx - 1]
    saw_aggression = False
    for a in hand.actions:
        if a.street == prev and a.action_type in (
                ActionType.BET, ActionType.RAISE, ActionType.ALL_IN):
            saw_aggression = True
            break
    return not saw_aggression


def _hero_in_position(hand: HandState, hero_idx: int) -> bool:
    """Postflop hero en geç mi konuşuyor (button'a en yakın aktif oyuncu)?"""
    n = len(hand.players)
    if n <= 0:
        return True
    d = getattr(hand, "dealer_idx", 0)

    def order(seat: int) -> int:        # postflop: dealer+1 ilk, dealer son
        return (seat - (d + 1)) % n

    active = [i for i, p in enumerate(hand.players)
              if not getattr(p, "is_folded", False)
              and not getattr(p, "is_eliminated", False)]
    if hero_idx not in active or not active:
        return True
    hero_o = order(hero_idx)
    return all(order(i) <= hero_o for i in active)


def _postflop_advice(hand: HandState, hero_idx: int, adv: LiveAdvice) -> LiveAdvice:
    """Board-texture-aware postflop frekans modeli (🟠 CONCEPT).

    1) Hero equity'sini modellenmiş villain devam-range'ine karşı hesapla (MC).
    2) board dokusu + inisiyatif + pozisyon + equity → action frekansları
       (postflop_gto motoru). Solver-exact DEĞİL — yön/şekil doğru, CONCEPT.
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

    # ── Board-texture-aware frekans modeli ──
    from app.poker.postflop_gto import (
        classify_board, cbet_strategy, defend_strategy,
    )
    tex = classify_board(hand.community)
    in_pos = _hero_in_position(hand, hero_idx)
    init = _hero_has_initiative(hand, hero_idx)
    street_name = (hand.street_name or "flop").lower()
    n_active = max(2, int(getattr(hand, "active_count", 2) or 2))

    if to_call > 0.01:
        # Bahis karşısında: doku + equity + pot-odds + multiway → fold/call/raise
        fold_f, call_f, raise_f = defend_strategy(eq, tex, pot, to_call,
                                                  n_active=n_active)
        adv.fold = round(100 * fold_f, 0)
        adv.call = round(100 * call_f, 0)
        adv.raise_ = round(100 * raise_f, 0)
        adv.allin = 0.0
        # RIVER bluff-catch → COMBO sayımı + blocker (elit koç: 'tek el değil,
        # combo say'). Sadece river'da (5 kart) ve bahis karşısında anlamlı.
        if street_name == "river" and len(hand.community) == 5:
            try:
                from app.poker.combinatorics import (
                    bluff_catch_analysis, coach_combo_line)
                ca = bluff_catch_analysis(
                    hero_code, " ".join(c.code for c in hand.community),
                    vr, pot, to_call)
                adv.combo_note = coach_combo_line(ca)
            except Exception:
                pass
    else:
        # Bahis yok: c-bet / donk / probe (doku/inisiyatif/pozisyon/sokak/multiway)
        probe = (not init) and _prev_street_checked_through(hand)
        bet_f, _size = cbet_strategy(eq, tex, in_pos, init,
                                     street=street_name, n_active=n_active,
                                     probe=probe)
        adv.raise_ = round(100 * bet_f, 0)        # BET slotu
        adv.call = round(100 * (1.0 - bet_f), 0)  # CHECK slotu
        adv.fold = 0.0
        adv.allin = 0.0

    pos_s = "IP" if in_pos else "OOP"
    init_s = "inisiyatif var" if init else "inisiyatif yok"
    adv.available = True
    adv.equity = round(eq * 100, 1)
    adv.scenario = (f"Postflop ({hand.street_name} · {tex.label} · "
                    f"{pos_s}, eq %{eq*100:.0f})")
    adv.tier_icon = "🟠"
    adv.tier_label = "Board-texture model (CONCEPT)"
    adv.note = (f"{tex.label} board · {pos_s} · {init_s}. Board-doku + equity "
                "heuristiği — yön/şekil doğru, solver-exact değil (tam GTO için "
                "Solver Sandbox).")
    adv.stack_bb = round((hero.stack + hero.current_bet) / bb, 1)
    _PF_CACHE[cache_key] = adv
    if len(_PF_CACHE) > 500:
        _PF_CACHE.clear()
    return adv


def _count_preflop_raises_before_hero(hand: HandState, hero_idx: int):
    """O ANKİ hero kararında masadaki toplam preflop raise sayısı + hero'nun
    karşılaştığı son (hero-olmayan) raiser'ın pozisyonu.

    Senaryo: 0 → RFI (açış), 1 → vs RFI, 2+ → vs 3-bet/4-bet.

    ÖNEMLİ: Eskiden hero'nun İLK aksiyonunda durup sonraki raise'leri (örn.
    hero açtıktan sonra gelen 3-bet) saymıyordu → hero 3-bet'e karşı
    konuşurken spot YANLIŞLIKLA 'RFI (açış)' etiketlenip açılış range'i
    (JTs RAISE %100 gibi) gösteriliyordu. Artık preflop'taki TÜM raise'ler
    (hero'nun kendi açışı dahil) sayılır → 3-bet potu doğru tanınır.
    """
    raises = 0
    last_raiser_pos = None
    for a in hand.actions:
        if a.street != Street.PREFLOP:
            continue
        if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
            raises += 1
            if a.player_idx != hero_idx:   # hero kendi raise'ine karşı oynamaz
                last_raiser_pos = hand.players[a.player_idx].position
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
