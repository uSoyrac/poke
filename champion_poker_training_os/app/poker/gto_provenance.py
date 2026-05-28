"""GTO accuracy provenance — her range'in NE kadar güvenilir olduğunu etiketler.

Amaç: kullanıcı yanlış öğrenmesin. Her spot için bir "accuracy tier"
döndürür; UI bunu bir rozetle gösterir. Böylece neyin solver-exact,
neyin yaklaşık, neyin kavramsal olduğu HER ZAMAN şeffaf olur.

Tier'lar:
  EXACT   (✅) — solver-exact veya matematiksel kesin
                  (push/fold Nash, RFI curated, equity, ICM)
  APPROX  (🟡) — prensip-temelli heuristic; doğru SHAPE, yaklaşık frekans
                  (vs-RFI/vs-3bet/MTT-depth heuristic ranges)
  CONCEPT (🟠) — gerçek ama basitleştirilmiş; strateji dersi doğru,
                  kesin frekans değil (river solver: tek bet size, raise yok)
  GAP     (❌) — kapsanmıyor; varsayma (full postflop multi-street, multiway)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── TIER DEFINITIONS ──────────────────────────────────────────────────

@dataclass(frozen=True)
class AccuracyTier:
    key: str
    label: str
    color: str        # hex
    icon: str
    explanation: str   # Türkçe, kullanıcıya gösterilir


EXACT = AccuracyTier(
    "EXACT", "Solver-Exact", "#10B981", "✅",
    "Bu range solver-exact veya matematiksel olarak kesin. "
    "Güvenle ezberleyebilirsin.",
)
APPROX = AccuracyTier(
    "APPROX", "Yaklaşık (Heuristic)", "#F59E0B", "🟡",
    "Prensip-temelli heuristic. Doğru SHAPE (hangi el oynanır, kabaca "
    "ne sıklıkta) ama kesin solver frekansı değil. Kavramı öğren, "
    "tam % ezberleme.",
)
CONCEPT = AccuracyTier(
    "CONCEPT", "Kavramsal (Basitleştirilmiş)", "#FB923C", "🟠",
    "Gerçek CFR ama basitleştirilmiş (tek bet size, raise yok, "
    "heads-up). Strateji DERSİ doğru (value/bluff/polarization); "
    "kesin frekanslar full solver'dan farklı.",
)
GAP = AccuracyTier(
    "GAP", "Kapsam Dışı", "#EF4444", "❌",
    "Bu alan henüz tam kapsanmıyor. Buradaki çıktıyı GTO gerçeği "
    "olarak varsayma.",
)


# ── PROVENANCE LOOKUP ─────────────────────────────────────────────────

def range_provenance(
    scenario: str,
    position: str,
    stack_depth: int = 100,
    mode: str = "cash",
    vs_position: Optional[str] = None,
) -> AccuracyTier:
    """Bir preflop range spot'unun accuracy tier'ını döndür."""
    # Push/Fold → Nash-kalibre, EXACT
    if scenario in ("Push/Fold", "Jam", "Call vs Jam"):
        return EXACT

    # RFI → curated 5 pozisyon (cash 100bb) EXACT, gerisi APPROX
    if scenario == "RFI":
        curated_positions = {"UTG", "MP", "CO", "BTN", "SB"}
        if mode == "cash" and stack_depth >= 60 and position in curated_positions:
            return EXACT
        # MTT mode veya farklı stack → heuristic/ante-aware
        return APPROX

    # vs RFI, vs 3-bet, Squeeze → heuristic (APPROX)
    if scenario in ("vs RFI", "vs 3-bet", "Squeeze"):
        return APPROX

    # ICM-adjusted / Bounty → APPROX (matematik EXACT ama range uygulaması yaklaşık)
    if scenario in ("ICM Push/Fold", "PKO Jam"):
        return APPROX

    return APPROX


def equity_provenance() -> AccuracyTier:
    """Monte Carlo equity her zaman EXACT (sampling hatası hariç)."""
    return EXACT


def solver_provenance(streets: int = 1) -> AccuracyTier:
    """River/postflop solver. 1 street = CONCEPT (basitleştirilmiş)."""
    return CONCEPT


def postflop_play_provenance() -> AccuracyTier:
    """Bot postflop oyunu / heuristic hand strength = GAP (GTO değil)."""
    return GAP


# ── ALL TIERS (legend için) ───────────────────────────────────────────
ALL_TIERS = [EXACT, APPROX, CONCEPT, GAP]
