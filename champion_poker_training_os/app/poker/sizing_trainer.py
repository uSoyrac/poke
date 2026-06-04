"""Bet-sizing trainer motoru — saf fonksiyon, UI bağımsız (geliştirme #4).

'Raise/bet dedin → kaç bb?' drill'i. Spot (preflop açış / 3-bet / c-bet kuru-
ıslak-polar) + GTO-önerilen size üretir; kullanıcının seçimini puanlar. Puanlama
TEK KAYNAK: sizing_advice.SizingAdvice.score (sapma→quality%, EV-loss kareyle).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List

from app.poker.sizing_advice import SizingAdvice

# Senaryo şablonları: (key, label, board, pot_bb aralığı, önerilen pot-frac veya
# preflop bb, açıklama). Modern solver konsensüsü sizing'leri.
_POSTFLOP = {
    "cbet_dry":   ("C-bet · KURU board (A/K-high, bağlantısız)", "Ks 7d 2c", 0.33,
                   "Kuru board → küçük range c-bet (%33). Tüm range ucuz baskı."),
    "cbet_wet":   ("C-bet · ISLAK board (bağlı/iki-renk)", "Jh Th 9s", 0.66,
                   "Islak board → büyük bet (%66). Draw'lara pahalı, value'yu koru."),
    "cbet_polar": ("C-bet · POLAR (nut ya da hava)", "Ks Kd 4h", 0.75,
                   "Polarize range → büyük (%75+). Value maksimize / fold-equity."),
}
_PRE_OPEN = {  # pozisyon → açış bb (modern: 2.2-2.5, EP biraz büyük)
    "UTG": 2.5, "MP": 2.5, "CO": 2.3, "BTN": 2.3, "SB": 3.0,
}


@dataclass
class SizingDrill:
    scenario: str
    scenario_key: str
    board: str
    hero_cards: str
    pot_bb: float
    recommended_bb: float
    recommended_label: str
    choices_bb: List[float] = field(default_factory=list)
    note: str = ""


def _round1(x: float) -> float:
    return round(x, 1)


def generate_sizing_drill(rng: "random.Random | None" = None) -> SizingDrill:
    rng = rng or random.Random()
    kind = rng.choice(["preflop_open", "threebet", "cbet_dry", "cbet_wet",
                       "cbet_polar"])

    if kind == "preflop_open":
        pos = rng.choice(list(_PRE_OPEN.keys()))
        rec = _PRE_OPEN[pos]
        pot = 1.5
        choices = sorted({2.0, 2.3, 2.5, 3.0, 4.0, rec})
        return SizingDrill(
            scenario=f"Preflop AÇIŞ · {pos} ({'ante yok' if True else ''})",
            scenario_key="preflop_open", board="", hero_cards="A♠ K♦",
            pot_bb=pot, recommended_bb=_round1(rec),
            recommended_label=f"{rec:.1f}x ({rec:.1f}bb)", choices_bb=choices,
            note=f"Modern açış {pos}: {rec:.1f}x civarı (BTN/CO ~2.3, EP ~2.5, SB ~3).")

    if kind == "threebet":
        # IP 3-bet = açışın 3x'i; açış 2.5bb → 3-bet 7.5bb
        open_to = rng.choice([2.3, 2.5, 3.0])
        rec = _round1(open_to * 3.0)
        pot = _round1(1.5 + open_to)
        choices = sorted({_round1(open_to * m) for m in (2.0, 2.5, 3.0, 4.0)} | {rec})
        return SizingDrill(
            scenario=f"3-BET (IP) · açış {open_to:.1f}bb'ye karşı",
            scenario_key="threebet", board="", hero_cards="A♥ A♣",
            pot_bb=pot, recommended_bb=rec,
            recommended_label=f"{rec:.1f}bb (açışın 3x'i)", choices_bb=choices,
            note="IP 3-bet ≈ açışın 3x'i (OOP ~3.5-4x).")

    # Postflop c-bet
    label, board, frac, note = _POSTFLOP[kind]
    pot = float(rng.choice([6, 8, 10, 12, 15, 20]))
    rec = _round1(pot * frac)
    choices = sorted({_round1(pot * f) for f in (0.25, 0.33, 0.5, 0.66, 0.75, 1.0)}
                     | {rec})
    return SizingDrill(
        scenario=label, scenario_key=kind, board=board, hero_cards="A♠ K♠",
        pot_bb=pot, recommended_bb=rec,
        recommended_label=f"%{frac*100:.0f} pot ({rec:.1f}bb)",
        choices_bb=choices, note=note)


def score_sizing(chosen_bb: float, drill: SizingDrill) -> dict:
    """Seçilen size'ı GTO-önerilene göre puanla (quality%, ev_loss_bb, verdict)."""
    adv = SizingAdvice(available=True, recommended_bb=drill.recommended_bb)
    return adv.score(float(chosen_bb), drill.pot_bb)
