"""Board-texture-aware postflop GTO heuristik beyni (Phase D3).

Mevcut canlı postflop önerisi yalnızca equity + pot-odds kullanıyordu; bu
modül buna **board dokusu, inisiyatif ve pozisyon** ekleyerek frekansların
GTO-ŞEKLİNİ doğru üretir (solver-exact değil — dürüst CONCEPT tier):

  - Kuru/yüksek board (A72r) → yüksek c-bet frekansı, küçük size (range avantajı)
  - Islak/dinamik board (JT9ss) → düşük c-bet, büyük/polarize size, daha çok semi-bluff
  - Paired board → orta-yüksek c-bet, küçük size
  - OOP / inisiyatifsiz → daha çok check
  - Bahis karşısında: MDF + equity + dokuya göre fold/call/raise (ıslakta value+semibluff raise)

Saf fonksiyon (Qt/DB bağımsız), kolay test edilir.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BoardTexture:
    paired: bool
    monotone: bool          # 3+ aynı suit
    two_tone: bool          # flush draw mümkün
    connected: bool         # düz çekme yoğun
    high_card: int          # 0(2)..12(A)
    wetness: float          # 0(kuru) .. 1(çok ıslak/dinamik)
    label: str


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def classify_board(community: list) -> BoardTexture:
    """``community``: en az 3 Card (.value 0-12, .suit). Doku sınıflandır."""
    cards = [c for c in (community or []) if c is not None]
    if len(cards) < 3:
        return BoardTexture(False, False, False, False, 0, 0.0, "preflop")

    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]

    # Pairing
    counts: dict = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    paired = any(n >= 2 for n in counts.values())

    # Suitedness
    suit_counts: dict = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    max_suit = max(suit_counts.values())
    monotone = max_suit >= 3
    two_tone = max_suit == 2

    # Connectedness — en yakın 3 kartın yayılımı (düz potansiyeli)
    uniq = sorted(set(values), reverse=True)
    connected = False
    min_span = 99
    for i in range(len(uniq) - 1):
        # ardışık iki benzersiz rank arası boşluk
        gap = uniq[i] - uniq[i + 1]
        min_span = min(min_span, gap)
    # 3 kart bir 5'lik pencere içindeyse bağlı say
    if len(uniq) >= 3:
        window = uniq[0] - uniq[2]
        if window <= 4:
            connected = True
    elif len(uniq) == 2 and min_span <= 2:
        connected = True

    high_card = values[0]

    # ── Wetness skoru ──
    wet = 0.0
    if monotone:
        wet += 0.55
    elif two_tone:
        wet += 0.30
    if connected:
        wet += 0.35
    # orta kartlar (5-T arası) düz/iki yönlü çekme zenginliği
    middling = sum(1 for v in values if 3 <= v <= 8)  # 5..T
    wet += 0.06 * middling
    # paired board biraz statiktir (çekme azalır) ama set/trips dinamiği
    if paired:
        wet *= 0.8
    wetness = _clamp(wet)

    if paired:
        label = "paired"
    elif monotone:
        label = "monotone"
    elif wetness >= 0.55:
        label = "wet/dynamic"
    elif wetness <= 0.3:
        label = "dry"
    else:
        label = "semi-wet"
    return BoardTexture(paired, monotone, two_tone, connected,
                        high_card, wetness, label)


def cbet_strategy(equity: float, tex: BoardTexture, in_position: bool,
                  has_initiative: bool) -> tuple[float, float]:
    """Bahis YOKKEN (hero aksiyonu): (bet_freq, size_frac).

    bet_freq → BET slotu, (1-bet_freq) → CHECK slotu.
    """
    wet = tex.wetness
    # Baz c-bet frekansı: kuru→yüksek, ıslak→düşük
    base = 0.78 - 0.42 * wet
    if tex.paired:
        base = max(base, 0.62)
    if not in_position:
        base *= 0.72            # OOP daha çok check
    if not has_initiative:
        base *= 0.45            # inisiyatif yoksa donk-lead nadir

    # Size: kuru küçük, ıslak büyük; paired küçük
    if wet < 0.35:
        size = 0.33
    elif wet < 0.6:
        size = 0.55
    else:
        size = 0.75
    if tex.paired:
        size = min(size, 0.45)

    # Equity modülasyonu
    if equity >= 0.62:
        bet_freq = min(0.92, base + 0.18)              # value bölgesi
    elif equity <= 0.30:
        bet_freq = base * (0.95 - 0.55 * wet)          # bluff (kuruda daha çok)
    else:
        # Orta/showdown-value: KURU board'da range-bet (yine çok bahis, küçük
        # size), ISLAK board'da polarize ol → check. Dokuya bağlı.
        bet_freq = base * (0.85 - 0.65 * wet)
    return _clamp(bet_freq, 0.0, 0.95), size


def defend_strategy(equity: float, tex: BoardTexture, pot: float,
                    to_call: float) -> tuple[float, float, float]:
    """Bahis KARŞISINDA: (fold, call, raise) frekansları (toplam ~1)."""
    be = to_call / max(pot + to_call, 1e-9)     # break-even equity
    wet = tex.wetness

    # Value raise: yüksek equity
    raise_freq = _clamp((equity - 0.66) * 1.7, 0.0, 0.5)
    # Semi-bluff raise: düşük equity + ıslak board (çekmeler)
    if equity < 0.36:
        raise_freq = max(raise_freq, 0.05 + 0.13 * wet)

    # Fold: equity break-even altındaysa
    if equity < be:
        fold_freq = _clamp((be - equity) / max(be, 1e-9) * 1.25, 0.0, 0.9)
    else:
        fold_freq = _clamp((be - equity + 0.08) * 0.5, 0.0, 0.9)

    call_freq = _clamp(1.0 - raise_freq - fold_freq, 0.0, 1.0)
    return fold_freq, call_freq, raise_freq
