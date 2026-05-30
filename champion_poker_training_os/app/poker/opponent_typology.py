"""Hellmuth hayvan-tipi rakip sınıflandırması — oyun-içi etiketleme.

Phil Hellmuth'un "Play Poker Like the Pros" tipolojisi: rakibi VPIP +
agresyon'dan beş hayvana yerleştir. Saf fonksiyon (Qt/DB bağımsız), masada
koltuk rozeti + HUD için kullanılır.

  🐭 Mouse    — tight-passive (az oynar, baskı yok)
  🦁 Lion     — tight-aggressive (disiplinli, güçlü)
  🐺 Jackal   — loose-aggressive (kaotik, çok blöf)
  🐘 Elephant — loose-passive (calling station)
  🦅 Eagle    — elit (dengeli, çok zor)  [tight-aggressive üst seviye]
"""
from __future__ import annotations

from typing import Tuple

# key → (emoji, kısa ad, nasıl oynanır — tek satır)
HELLMUTH_ANIMALS = {
    "mouse": ("🐭", "Mouse", "Tight-passive: körlerini çal, blöfle bas."),
    "lion": ("🦁", "Lion", "Tight-aggressive solid: dengeli oyna, leak verme."),
    "jackal": ("🐺", "Jackal", "Loose-aggressive: güçlü elle bekle, bluff-catch."),
    "elephant": ("🐘", "Elephant", "Calling station: acımasız value, blöf yapma."),
    "eagle": ("🦅", "Eagle", "Elit: minimum çatışma, hatasız oyna."),
}


def classify_hellmuth(vpip: float, pfr: float, aggression: float,
                      river_bluff: float = 0.0) -> Tuple[str, str, str]:
    """(emoji, ad, ipucu) döndür. VPIP + agresyon(+blöf) → hayvan tipi.

    'Aggressive' sinyali AF tek başına yanıltır (Maniac'ın AF'si yapısal düşük);
    bu yüzden river_bluff de hesaba katılır → Maniac doğru şekilde Jackal olur.
    """
    v = float(vpip or 0)
    p = float(pfr or 0)
    a = float(aggression or 0)
    rb = float(river_bluff or 0)
    if rb > 1:           # bazı kaynaklar yüzde olarak verir (12 vs 0.12)
        rb /= 100.0
    aggressive = (a >= 2.0) or (rb >= 0.28)
    passive = not aggressive
    loose = v >= 27
    if loose and passive:
        key = "elephant"
    elif loose:
        key = "jackal"
    elif passive:
        key = "mouse"
    else:
        # tight-aggressive → Lion; üst seviye (çok yüksek PFR/VPIP + agresyon) → Eagle
        ratio = p / v if v > 0 else 0
        key = "eagle" if (v <= 24 and a >= 2.9 and ratio >= 0.85) else "lion"
    emoji, name, tip = HELLMUTH_ANIMALS[key]
    return emoji, name, tip


def classify_label(vpip: float, pfr: float, aggression: float,
                   river_bluff: float = 0.0) -> str:
    """Kısa rozet metni: '🦁 Lion'."""
    emoji, name, _ = classify_hellmuth(vpip, pfr, aggression, river_bluff)
    return f"{emoji} {name}"
