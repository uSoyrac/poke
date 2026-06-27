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

# SAYIM-MVP (D312): el-başı OKUMA-SAYACI R prior'u — TEK-KAYNAK başlangıç tablosu.
# Yorum: R>0 = "saygı, value-eğilimli" (blöfleme, marjinali bırak); R<0 = "capped/blöfçü, saldır".
# ±1 ile SINIRLI: prior TEK BAŞINA asla |R|≥2 sapma eşiğini AÇMAZ — sapma daima GÖZLENEN
# el-içi dizi gerektirir (denetim şartı). HELLMUTH_ANIMALS 3-tuple çözümlemesini kırmamak için
# AYRI tablo. 🐘 station/🐭 nit/🦅 elit = bahsi value (saygı, +1); 🐺 LAG blöfçü (saldır, −1);
# 🦁 TAG dengeli (exploit yok, 0). Veri yok → 0 (NÖTR, GTO-baz; uydurma popülasyon-edge yok).
HELLMUTH_PRIOR = {"elephant": 1, "mouse": 1, "eagle": 1, "lion": 0, "jackal": -1}


def type_prior(key: str) -> int:
    """Tip anahtarından el-başı R prior'u (±1 cap). Bilinmeyen/yok → 0."""
    return max(-1, min(1, HELLMUTH_PRIOR.get((key or "").lower(), 0)))


def classify_hellmuth(vpip: float, pfr: float, aggression: float,
                      river_bluff: float = 0.0, *,
                      fold_to_cbet: "float | None" = None,
                      call_down: "float | None" = None) -> Tuple[str, str, str]:
    """(emoji, ad, ipucu) döndür. VPIP + VPIP−PFR GAP + agresyon(+blöf+F-cbet+call↓) → hayvan tipi.

    D330 (kullanıcı yakaladı: 24/7/AF1.5/F-cbet0/Call56 = STATION ama 'Lion solid' etiketleniyordu):
    VPIP−PFR GAP eklendi — büyük gap (çok-call az-raise) = pasif-preflop/station; eski kod yalnız
    AF/river-bluff'a bakıp pasif-loose'u 'Lion TAG' sanıyordu (yanlış exploit: 'station'ı exploit etme').
    F-cbet (düşük=öder) + call↓ (yüksek=öder) opsiyonel teyit. 'Aggressive' AF tek başına yanıltır →
    river_bluff de katılır (Maniac→Jackal).
    """
    v = float(vpip or 0)
    p = float(pfr or 0)
    a = float(aggression or 0)
    rb = float(river_bluff or 0)
    if rb > 1:           # bazı kaynaklar yüzde olarak verir (12 vs 0.12)
        rb /= 100.0
    gap = v - p          # büyük gap = çok-call az-raise = pasif-preflop (limper/caller)
    fcb = float(fold_to_cbet) if fold_to_cbet is not None else None
    cdn = float(call_down) if call_down is not None else None
    # STATION tespiti (D330): pasif (AF<2) + (büyük preflop-gap ile çok-call) VEYA postflop-öder
    # sinyali (F-cbet düşük / call↓ yüksek). Bunlar 'Lion'dan ÖNCE yakalanır → yanlış-TAG biter.
    station = (a < 2.0) and (
        (gap >= 12 and p <= 12) or
        (fcb is not None and fcb <= 25) or
        (cdn is not None and cdn >= 50))
    if station:
        key = "elephant"
    else:
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
