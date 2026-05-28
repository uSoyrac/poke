"""Bet-sizing analizi — "5bb mi 12bb mi?" kalitesi + EV kaybı + leak.

Kullanıcı: "5bb raise %13 optimal ama 12bb %80 doğru" gibi analiz istiyor.
Bu modül o anki spot için GTO-STANDART sizing'i önerir ve kullanıcının
seçtiği boyutu puanlar (quality %, tahmini EV kaybı, verdict).

DÜRÜSTLÜK (🟠 CONCEPT): kesin sizing-EV solver gerektirir (TexasSolver çoklu
size). Bu model GTO-standart boyutlardan (yayınlanmış sizing teorisi) sapmayı
ölçer + EV-kaybını heuristik tahmin eder. Yön doğru, kesin EV yaklaşık.

Standart boyutlar (modern solver konsensusu):
  - Preflop açış: 2.2-2.5x (BTN/CO 2.3, EP 2.5, SB 3.0); ante varsa 2.0-2.3
  - 3-bet: açışın 3x'i (IP) / 3.5-4x'i (OOP)
  - Postflop c-bet: kuru board %33, ıslak %66, polarized %75
  - <15bb → jam (all-in)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engine.hand_state import ActionType, HandState, Street


@dataclass
class SizingAdvice:
    available: bool = False
    recommended_bb: float = 0.0     # önerilen "raise to" / "bet" miktarı (bb)
    recommended_frac: float = 0.0   # postflop: pot'a oran
    label: str = ""                 # "Açış 2.3bb" / "C-bet %66 pot" vb.
    note: str = ""

    def score(self, chosen_bb: float, pot_bb: float = 0.0) -> dict:
        """Seçilen boyutu puanla → {quality_pct, ev_loss_bb, verdict}."""
        rec = self.recommended_bb if self.recommended_bb > 0 else 0.01
        rel = abs(chosen_bb - rec) / rec      # rölatif sapma
        # Quality: sapma 0 → %100, sapma ~%80 → %20. Sizing EV flat near optimum.
        quality = max(0.0, min(100.0, 100.0 * (1.0 - rel * 0.85)))
        # EV-loss heuristiği: optimum yakını flat, uzakta kareyle artar.
        # pot büyüdükçe mutlak kayıp büyür. (CONCEPT — kesin değil)
        ref_pot = pot_bb if pot_bb > 0 else (rec * 2.5)
        ev_loss = round(ref_pot * 0.035 * (rel ** 2), 2)
        if quality >= 80:
            verdict = "Mükemmel — GTO-standart boyuta çok yakın."
        elif quality >= 55:
            verdict = "Kabul edilebilir — hafif sapma, küçük EV kaybı."
        elif quality >= 30:
            verdict = "Suboptimal — boyut belirgin sapmış, EV bırakıyorsun."
        else:
            verdict = "Zayıf — boyut çok uzak, ciddi EV kaybı."
        return {"quality_pct": round(quality, 0), "ev_loss_bb": ev_loss,
                "verdict": verdict, "rel_dev": round(rel * 100, 0)}


# ── PREFLOP STANDART AÇIŞ BOYUTLARI ───────────────────────────────────

def _open_size_bb(position: str, stack_bb: float, ante: bool) -> float:
    pos = (position or "").upper()
    if stack_bb <= 15:
        return round(stack_bb, 1)   # jam
    base_ep = 2.3 if ante else 2.5
    base_lp = 2.1 if ante else 2.3
    if pos in ("UTG", "UTG+1", "UTG+2", "LJ", "MP", "MP+1"):
        return base_ep
    if pos in ("HJ", "CO", "BTN", "BU"):
        return base_lp
    if pos in ("SB", "SB/BTN"):
        return 3.0 if not ante else 2.7
    return base_ep


def _board_bet_frac(hand: HandState) -> tuple[float, str]:
    """Postflop c-bet/bet için önerilen pot-oranı + açıklama."""
    from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES
    # Board texture
    board = hand.community
    if not board:
        return 0.5, "%50 pot"
    ranks = [c.value for c in board]
    suits = [c.suit for c in board]
    paired = len(set(ranks)) < len(ranks)
    suit_counts = {s: suits.count(s) for s in set(suits)}
    flush_draw = max(suit_counts.values()) >= 2
    sorted_r = sorted(set(ranks))
    connected = any(sorted_r[i+1] - sorted_r[i] <= 2 for i in range(len(sorted_r)-1))
    wet = flush_draw or connected
    if paired and not wet:
        return 0.33, "%33 pot (kuru paired — küçük)"
    if wet:
        return 0.70, "%70 pot (ıslak/dinamik — büyük, koru)"
    return 0.50, "%50 pot (orta texture)"


def sizing_advice(hand: HandState, hero_idx: int,
                  mode: str = "cash") -> SizingAdvice:
    """O anki spot için GTO-standart sizing önerisi."""
    adv = SizingAdvice()
    if not hand or hand.is_complete:
        return adv
    hero = hand.players[hero_idx]
    bb = max(hand.big_blind, 0.01)
    eff_stack = (hero.stack + hero.current_bet) / bb
    pot_bb = hand.pot / bb
    to_call = hand.to_call(hero_idx)
    ante = bool(getattr(hand, "ante", 0))

    if hand.street == Street.PREFLOP:
        if eff_stack <= 15:
            adv.recommended_bb = round(eff_stack, 1)
            adv.label = f"JAM ({eff_stack:.0f}bb) — kısa stack push/fold"
            adv.note = "≤15bb: standart sizing yok, jam-or-fold."
        elif to_call <= bb + 0.01:
            # Açış (RFI)
            sz = _open_size_bb(hero.position, eff_stack, ante)
            adv.recommended_bb = sz
            adv.label = f"Açış {sz}x ({sz:.1f}bb)"
            adv.note = (f"Modern GTO açış {sz}bb civarı"
                        + (" (ante ile küçük)" if ante else "") + ".")
        else:
            # Bir raise'e karşı 3-bet
            open_to = hand.current_bet / bb
            ip = (hero.position or "").upper() in ("BTN", "CO", "BU")
            sz = round(open_to * (3.0 if ip else 4.0), 1)
            adv.recommended_bb = sz
            adv.label = f"3-bet {sz:.1f}bb ({'IP 3x' if ip else 'OOP ~4x'} open)"
            adv.note = "3-bet: açışın IP 3x / OOP ~4x'i."
        adv.available = True
        return adv

    # Postflop bet sizing
    frac, desc = _board_bet_frac(hand)
    adv.recommended_frac = frac
    adv.recommended_bb = round(pot_bb * frac, 1)
    adv.label = f"Bet {desc}  (~{adv.recommended_bb:.1f}bb)"
    adv.note = ("Postflop boyut board texture'a bağlı. Kesin GTO size için "
                "Solver Sandbox / TexasSolver (çoklu size).")
    adv.available = True
    return adv
