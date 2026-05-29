"""Oturum skor kartı — bir oturum/turnuva boyunca GTO başarımını biriktirir.

Her el bitince ``add_hand(decision_log)`` çağrılır; motor `decision_grade`'i
kullanarak karar başına not + EV kaybı toplar. ``summary()`` anlık oturum
karnesini döndürür: GTO doğruluk % (A+B oranı), ortalama puan, toplam EV kaybı
ve street/kategori bazında en zayıf nokta.

Saf veri sınıfı (Qt/DB bağımsız) → kolay test, ekranlar sadece okur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.poker.decision_grade import grade_decision


def _category(snap: dict) -> str:
    street = (snap.get("street") or "").strip().lower()
    if street in ("flop", "turn", "river"):
        return street.capitalize()
    return "Preflop"


@dataclass
class SessionScore:
    n_hands: int = 0
    n_decisions: int = 0
    score_sum: float = 0.0          # toplam puan (A=100…F=10)
    ev_lost: float = 0.0
    a_b_count: int = 0              # GTO-doğru kararlar (A veya B)
    # kategori → [puan_toplamı, adet]
    by_cat: dict = field(default_factory=dict)

    def add_hand(self, decision_log: list) -> None:
        """Bir elin notlandırılabilir kararlarını oturum toplamına ekle."""
        if not decision_log:
            return
        had_decision = False
        for snap in decision_log:
            g = grade_decision(snap)
            if g.score is None:        # available=False / aksiyon yok → atla
                continue
            had_decision = True
            self.n_decisions += 1
            self.score_sum += g.score
            self.ev_lost += g.ev_loss
            if g.letter in ("A", "B"):
                self.a_b_count += 1
            cat = _category(snap)
            agg = self.by_cat.setdefault(cat, [0.0, 0])
            agg[0] += g.score
            agg[1] += 1
        if had_decision:
            self.n_hands += 1

    @property
    def accuracy(self) -> float:
        """GTO doğruluk % = A+B kararların oranı."""
        if self.n_decisions == 0:
            return 0.0
        return round(100.0 * self.a_b_count / self.n_decisions, 1)

    @property
    def avg_score(self) -> float:
        if self.n_decisions == 0:
            return 0.0
        return round(self.score_sum / self.n_decisions, 1)

    def weakest_category(self) -> Optional[str]:
        """En düşük ortalama puanlı kategori (en az 2 karar olan)."""
        best: Optional[str] = None
        best_avg = 1e9
        for cat, (s, n) in self.by_cat.items():
            if n < 2:
                continue
            avg = s / n
            if avg < best_avg:
                best_avg = avg
                best = cat
        return best

    def summary(self) -> dict:
        return {
            "n_hands": self.n_hands,
            "n_decisions": self.n_decisions,
            "accuracy": self.accuracy,
            "avg_score": self.avg_score,
            "ev_lost": round(self.ev_lost, 1),
            "weakest": self.weakest_category(),
            "by_cat": {c: round(s / n, 1) for c, (s, n) in self.by_cat.items() if n},
        }

    def reset(self) -> None:
        self.n_hands = 0
        self.n_decisions = 0
        self.score_sum = 0.0
        self.ev_lost = 0.0
        self.a_b_count = 0
        self.by_cat = {}
