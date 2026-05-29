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


def make_snapshot(hand, hero_idx: int, gto, bb: float = 1.0,
                  sizing: Optional[dict] = None) -> dict:
    """Bir karar noktasının snapshot dict'ini üret (reveal/grade/persist şeması)."""
    _bb = max(float(bb), 1e-9)
    try:
        to_call = float(hand.to_call(hero_idx))
    except Exception:
        to_call = 0.0
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
        "pot_bb": float(getattr(hand, "pot", 0) or 0) / _bb,
        "to_call_bb": to_call / _bb,
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
                sizing: Optional[dict] = None) -> None:
        _bb = max(float(bb), 1e-9)
        try:
            to_call = float(hand.to_call(hero_idx))
        except Exception:
            to_call = 0.0
        key = (getattr(hand, "street_name", ""), round(to_call / _bb, 1))
        if key in self._keys:
            return
        self._keys.add(key)
        self.log.append(make_snapshot(hand, hero_idx, gto, bb, sizing))

    def attach_hero(self, action_type, amount, bb: float = 1.0) -> None:
        if not self.log:
            return
        last = self.log[-1]
        if last.get("hero_action") is None:
            name = getattr(action_type, "name", str(action_type))
            last["hero_action"] = name
            last["hero_amount"] = float(amount or 0) / max(float(bb), 1e-9)
