"""Hero karar noktası yakalama — play/tournament ekranlarının paylaştığı motor.

Bir el boyunca hero'nun karşılaştığı her karar noktasının GTO snapshot'ını
(frekanslar + equity + pot matematiği) toplar; el bitince ``GTODecisionReveal``
+ ``decision_grade`` + ``repository.record_decision_log`` bu listeyi kullanır.

Street başına bir snapshot (to_call seviyesi değişirse yeni karar). bb birimi
parametrik: cash'te bb≈1 (zaten bb cinsinden), turnuvada chip→bb dönüşümü için
``bb`` (büyük blind chip değeri) verilir.
"""
from __future__ import annotations

from typing import Optional


def preflop_pot_type(hand) -> str:
    """Preflop raise sayısından pot tipi: SRP / 3BP / 4BP / limped."""
    try:
        from app.engine.hand_state import ActionType, Street
        raises = 0
        for a in hand.actions:
            if a.street != Street.PREFLOP:
                continue
            if a.action_type in (ActionType.RAISE, ActionType.BET, ActionType.ALL_IN):
                raises += 1
        if raises >= 3:
            return "4BP"
        if raises == 2:
            return "3BP"
        if raises == 1:
            return "SRP"
        return "limped"
    except Exception:
        return "SRP"


def make_snapshot(hand, hero_idx: int, gto, bb: float = 1.0,
                  sizing: Optional[dict] = None,
                  fmt: str = "", stage: str = "") -> dict:
    """Bir karar noktasının snapshot dict'ini üret (reveal/grade/persist şeması).

    ``fmt`` (cash/mtt/sng) ve ``stage`` (turnuva aşaması) segment analizinde
    'MTT · orta aşama · ...' içgörüsü için saklanır.
    """
    _bb = max(float(bb), 1e-9)
    try:
        to_call = float(hand.to_call(hero_idx))
    except Exception:
        to_call = 0.0
    # Postflop EXACT solver için spot bağlamı (board, hero combo, stack, IP)
    board = ""
    hero_combo = ""
    hero_cards_disp = ""
    hero_position = ""
    n_active = 2
    raiser_pos = ""
    villain_position = ""
    eff_stack_bb = 0.0
    in_position = True
    pot_type = "SRP"
    try:
        comm = getattr(hand, "community", []) or []
        board = " ".join(c.code for c in comm)
        hero = hand.players[hero_idx]
        hero_position = getattr(hero, "position", "") or ""
        if getattr(hero, "hole_cards", None) and len(hero.hole_cards) >= 2:
            hero_combo = hero.hole_cards[0].code + hero.hole_cards[1].code
            hero_cards_disp = " ".join(c.display for c in hero.hole_cards[:2])
        eff_stack_bb = round((hero.stack + hero.current_bet) / _bb, 1)
        n_active = int(getattr(hand, "active_count", 2) or 2)
        from app.poker.gto_live_advice import (
            _hero_in_position, _count_preflop_raises_before_hero)
        in_position = _hero_in_position(hand, hero_idx)
        pot_type = preflop_pot_type(hand)
        _, _rp = _count_preflop_raises_before_hero(hand, hero_idx)
        raiser_pos = _rp or ""
        # Tek aktif rakip (HU postflop) pozisyonu → pozisyon-bazlı solver range
        others = [p for i, p in enumerate(hand.players)
                  if i != hero_idx and not getattr(p, "is_folded", False)
                  and not getattr(p, "is_eliminated", False)]
        if len(others) == 1:
            villain_position = getattr(others[0], "position", "") or ""
    except Exception:
        pot_type = "SRP"

    snap = {
        "street": getattr(hand, "street_name", ""),
        "scenario": getattr(gto, "scenario", "") if gto else "",
        "tier": getattr(gto, "tier_label", "") if gto else "",
        "available": bool(getattr(gto, "available", False)) if gto else False,
        "note": getattr(gto, "note", "") if gto else "",
        "fold": getattr(gto, "fold", 0) if gto else 0,
        "call": getattr(gto, "call", 0) if gto else 0,
        "raise": getattr(gto, "raise_", 0) if gto else 0,
        "allin": getattr(gto, "allin", 0) if gto else 0,
        "equity": getattr(gto, "equity", 0) if gto else 0,
        "combo_note": getattr(gto, "combo_note", "") if gto else "",
        "range_adv_note": getattr(gto, "range_adv_note", "") if gto else "",
        "plan_note": getattr(gto, "plan_note", "") if gto else "",
        "pot_bb": float(getattr(hand, "pot", 0) or 0) / _bb,
        "to_call_bb": to_call / _bb,
        "board": board, "hero_combo": hero_combo,
        "hero_cards_disp": hero_cards_disp, "hero_position": hero_position,
        "n_active": n_active, "raiser_pos": raiser_pos,
        "villain_position": villain_position,
        "eff_stack_bb": eff_stack_bb, "in_position": in_position,
        "pot_type": pot_type,
        "format": fmt, "stage": stage,
        "hero_action": None, "hero_amount": None, "_bb": _bb,
    }
    if sizing:
        snap["sizing_label"] = sizing.get("label")
        snap["sizing_bb"] = sizing.get("rec_bb")
    return snap


class DecisionRecorder:
    """Bir elin karar snapshot'larını dedup ile toplar; hero aksiyonunu iliştirir."""

    def __init__(self) -> None:
        self.log: list[dict] = []
        self._keys: set = set()

    def reset(self) -> None:
        self.log = []
        self._keys = set()

    def capture(self, hand, hero_idx: int, gto, bb: float = 1.0,
                sizing: Optional[dict] = None,
                fmt: str = "", stage: str = "") -> None:
        _bb = max(float(bb), 1e-9)
        try:
            to_call = float(hand.to_call(hero_idx))
        except Exception:
            to_call = 0.0
        key = (getattr(hand, "street_name", ""), round(to_call / _bb, 1))
        if key in self._keys:
            return
        self._keys.add(key)
        self.log.append(make_snapshot(hand, hero_idx, gto, bb, sizing, fmt, stage))

    def attach_hero(self, action_type, amount, bb: float = 1.0) -> None:
        if not self.log:
            return
        last = self.log[-1]
        if last.get("hero_action") is None:
            name = getattr(action_type, "name", str(action_type))
            last["hero_action"] = name
            last["hero_amount"] = float(amount or 0) / max(float(bb), 1e-9)
