"""Duke Resulting-Fallacy aracı (D195) — KARAR kalitesini SONUÇtan ayır.

Annie Duke (*Thinking in Bets* / *Decide to Play Great Poker*): bir oyunu, karar
anındaki bilgiyle (EV) yargıla — kazanıp-kaybetmesiyle DEĞİL. "Kaybettim demek
kötü oynadım" ve "kazandım demek iyi oynadım" İKİSİ DE *resulting* yanılgısıdır.
Poker'in en önemli tek zihinsel düzeltmesi: tilt'in ve yanlış-öğrenmenin panzehiri.

İki tuzak-kadran (sonuç kararı yanıltır):
  • İYİ karar + KAYIP → varyans. Üzülme, aynı kararı tekrar ver.
  • KÖTÜ karar + KAZANÇ → şans. Ödüllendi ama çizgi yanlıştı; TEKRARLAMA.

Saf modül (UI'a/bota bağlı değil); decision_grade harfi (A-F) + sonuç (won) alır.
"""
from __future__ import annotations
from dataclasses import dataclass

_GOOD = {"A", "B"}
_BAD = {"D", "F"}


def resulting_flag(grade_letter: str, won: bool) -> dict:
    """KARAR-kalitesi × SONUÇ dört-kadranı → {quadrant, trap, note}.
    trap=True ⇒ sonuç kararı yanıltıyor (öğrenme/tilt tuzağı). C/belirsiz → nötr."""
    g = (grade_letter or "").strip().upper()[:1]
    good, bad = g in _GOOD, g in _BAD
    if good and not won:
        return {"quadrant": "iyi-karar/kayıp", "trap": True,
                "note": "İyi karar, kötü şans (varyans). Sonuç seni yanıltmasın — "
                        "aynı kararı tekrar ver."}
    if bad and won:
        return {"quadrant": "kötü-karar/kazanç", "trap": True,
                "note": "Şanslı kazanç, kötü karar. Sonuç ödüllendirdi ama çizgi "
                        "yanlıştı — TEKRARLAMA."}
    if good and won:
        return {"quadrant": "iyi-karar/kazanç", "trap": False,
                "note": "İyi karar + iyi sonuç ✓ (hak edilmiş)"}
    if bad and not won:
        return {"quadrant": "kötü-karar/kayıp", "trap": False,
                "note": "Kötü karar + kötü sonuç — ders net, çizgiyi düzelt"}
    return {"quadrant": "nötr", "trap": False, "note": ""}


@dataclass
class ResultingLedger:
    """Oturum boyu karar×sonuç kadranlarını say → sonuç-değil-karar odaklı özet."""
    good_won: int = 0
    good_lost: int = 0          # varyans kurbanı (kararın doğruydu)
    bad_won: int = 0            # şanslı (tekrarlama riski)
    bad_lost: int = 0
    neutral: int = 0

    def add(self, grade_letter: str, won: bool) -> dict:
        f = resulting_flag(grade_letter, won)
        q = f["quadrant"]
        if q == "iyi-karar/kazanç":
            self.good_won += 1
        elif q == "iyi-karar/kayıp":
            self.good_lost += 1
        elif q == "kötü-karar/kazanç":
            self.bad_won += 1
        elif q == "kötü-karar/kayıp":
            self.bad_lost += 1
        else:
            self.neutral += 1
        return f

    @property
    def traps(self) -> int:
        """Sonucun kararı yanılttığı toplam spot (iyi-kayıp + kötü-kazanç)."""
        return self.good_lost + self.bad_won

    @property
    def decision_win_rate(self) -> float:
        """KARAR-doğruluğu (iyi kararların oranı) — sonuçtan bağımsız."""
        total = self.good_won + self.good_lost + self.bad_won + self.bad_lost
        if total == 0:
            return 0.0
        return round(100.0 * (self.good_won + self.good_lost) / total, 1)

    def summary(self) -> str:
        if self.traps == 0 and self.decision_win_rate == 0:
            return "Henüz veri yok."
        parts = [f"📊 Karar-doğruluğu %{self.decision_win_rate:.0f} (SONUÇtan bağımsız)"]
        if self.good_lost:
            parts.append(f"💙 {self.good_lost} iyi-karar-kaybı = VARYANS (üzülme, "
                         f"kararların doğruydu)")
        if self.bad_won:
            parts.append(f"⚠️ {self.bad_won} kötü-karar-kazanç = ŞANS (tekrarlama; "
                         f"sonuç seni kandırmasın)")
        parts.append("🧠 Duke: oyunu KARARLA yargıla, sonuçla değil.")
        return "  ·  ".join(parts)
