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

    # ── POSTFLOP: dürüst — preflop chart'lar postflop bilmez ──
    if hand.street != Street.PREFLOP:
        adv.available = False
        adv.tier_icon = "❌"
        adv.tier_label = "Postflop"
        adv.note = ("Postflop GTO için Solver Sandbox / TexasSolver kullan. "
                    "Canlı buton %'si sadece preflop'ta gösterilir (yanlış "
                    "öğretmemek için).")
        return adv

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
