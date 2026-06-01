"""Karar notlandırma motoru — saf fonksiyon, UI/DB bağımsız (Phase D1).

El-sonu reveal paneli, session skor kartı ve hero_decisions persist'i bu
motoru paylaşır. Bir karar snapshot'ından (GTO frekansları + hero aksiyonu +
equity/pot) bir harf notu (A-F) + EV kaybı üretir.

Snapshot anahtarları (eksikler tolere edilir):
  available (bool), fold, call, raise, allin  — GTO % (0-100)
  equity (0-100), pot_bb, to_call_bb          — pot matematiği
  hero_action (FOLD/CHECK/CALL/BET/RAISE/ALL_IN), hero_amount

Kural:
  hero_freq = GTO'nun hero'nun aldığı aksiyona verdiği % (CHECK→call slot)
  - hero en yüksek-frekans GTO aksiyonunu seçti VEYA hero_freq ≥ 60 → A
  - hero_freq ≥ 35 → B · ≥ 15 → C · < 15 → D
  EV overlay: ev_loss > 4bb → F; ev_loss > 1.5bb → en fazla C
  available=False (postflop solver yok) → notlandırma yok ("N/A")
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Harf → puan eşlemesi
_SCORE = {"A": 100, "B": 80, "C": 60, "D": 35, "F": 10}
_LETTERS_BEST_FIRST = ["A", "B", "C", "D", "F"]


@dataclass
class DecisionGrade:
    letter: str                  # A/B/C/D/F veya "N/A"
    score: Optional[int]         # 0-100 veya None (N/A)
    ev_loss: float               # bb (yaklaşık)
    note: str = ""


@dataclass
class HandGrade:
    letter: str
    score: Optional[float]       # ortalama puan veya None
    n_decisions: int
    ev_loss_total: float


def _hero_slot(action_name: str) -> Optional[str]:
    a = (action_name or "").upper().replace("-", "_")
    if a == "FOLD":
        return "fold"
    if a in ("CALL", "CHECK"):
        return "call"
    if a in ("RAISE", "BET"):
        return "raise"
    if a in ("ALL_IN", "ALLIN"):
        return "allin"
    return None


def _ev_loss(snap: dict, hero_action: str) -> float:
    """Kaba EV kaybı (bb): +EV fold veya -EV call. Diğer durumda 0."""
    eq = float(snap.get("equity", 0) or 0) / 100.0
    pot = float(snap.get("pot_bb", 0) or 0)
    to_call = float(snap.get("to_call_bb", 0) or 0)
    if eq <= 0 or to_call <= 0.01:
        return 0.0
    call_ev = eq * (pot + to_call) - to_call
    a = (hero_action or "").upper().replace("-", "_")
    if a == "FOLD" and call_ev > 0:
        return round(call_ev, 2)
    if a in ("CALL", "CHECK") and call_ev < 0:
        return round(-call_ev, 2)
    return 0.0


def _cap_letter(letter: str, floor_letter: str) -> str:
    """Notu en iyi `floor_letter` ile sınırla (örn. C → A/B'yi C'ye düşür)."""
    li = _LETTERS_BEST_FIRST.index(letter)
    fi = _LETTERS_BEST_FIRST.index(floor_letter)
    return _LETTERS_BEST_FIRST[max(li, fi)]


def grade_decision(snap: dict) -> DecisionGrade:
    if not snap.get("available"):
        return DecisionGrade("N/A", None, 0.0,
                             "Postflop solver yok — notlandırılmadı.")
    slot = _hero_slot(snap.get("hero_action", ""))
    if slot is None:
        return DecisionGrade("N/A", None, 0.0, "Hero aksiyonu yok.")

    freqs = {
        "fold": float(snap.get("fold", 0) or 0),
        "call": float(snap.get("call", 0) or 0),
        "raise": float(snap.get("raise", 0) or 0),
        "allin": float(snap.get("allin", 0) or 0),
    }
    hero_freq = freqs[slot]
    is_top = hero_freq >= max(freqs.values())

    if is_top or hero_freq >= 60:
        letter = "A"
    elif hero_freq >= 35:
        letter = "B"
    elif hero_freq >= 15:
        letter = "C"
    else:
        letter = "D"

    # Postflop board-texture modeli (CONCEPT) HEURİSTİKtir — equity tahmini
    # kesin değil. Bu yüzden heuristik spotlarda sert F/D verilmez (kullanıcıyı
    # yanıltmamak için en kötü 'C'ye sınırlanır + EV-loss F-override uygulanmaz).
    scen = (snap.get("scenario") or "").lower()
    tier = (snap.get("tier") or "").lower()
    is_estimate = ("postflop" in scen or "concept" in tier)

    ev = _ev_loss(snap, snap.get("hero_action", ""))
    if not is_estimate:
        if ev > 4.0:
            letter = "F"
        elif ev > 1.5:
            letter = _cap_letter(letter, "C")
    else:
        # heuristik: en kötü C (D/F → C)
        if letter in ("D", "F"):
            letter = "C"

    note = ""
    if is_estimate and letter == "C":
        note = "Heuristik postflop tahmini — kesin değil (EXACT solver ile doğrula)."
    elif letter in ("A", "B"):
        note = "GTO çizgisinde."
    elif letter == "C":
        note = "Azınlık aksiyon — savunulabilir ama optimal değil."
    elif letter == "D":
        note = "GTO'nun nadir yaptığı aksiyon — sapma."
    else:
        note = f"Büyük EV kaybı (~{ev:.1f}bb)."
    return DecisionGrade(letter, _SCORE[letter], ev, note)


def _letter_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def grade_hand(decisions: list) -> HandGrade:
    """Bir elin notlandırılabilir kararlarının ağırlıksız ortalaması."""
    graded = [grade_decision(d) for d in (decisions or [])]
    scored = [g for g in graded if g.score is not None]
    if not scored:
        return HandGrade("N/A", None, 0, 0.0)
    avg = sum(g.score for g in scored) / len(scored)
    ev_total = round(sum(g.ev_loss for g in scored), 2)
    return HandGrade(_letter_from_score(avg), round(avg, 1), len(scored), ev_total)
