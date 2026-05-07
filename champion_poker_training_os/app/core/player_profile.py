from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PlayerProfile:
    """Comprehensive personal poker profile built from play data."""

    # HUD stats
    total_hands: int = 0
    vpip: float = 0.0
    pfr: float = 0.0
    three_bet: float = 0.0
    wtsd: float = 0.0        # Went to showdown
    wsd: float = 0.0         # Won at showdown
    af: float = 0.0          # Aggression factor
    profit_bb: float = 0.0
    bb_per_100: float = 0.0
    win_rate: float = 0.0

    # Positional stats
    position_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Strengths and weaknesses
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    # Session history
    sessions: int = 0
    best_session: float = 0.0
    worst_session: float = 0.0

    def update_from_stats(self, stats: dict) -> None:
        """Update profile from DB stats dict."""
        self.total_hands = stats.get("total_hands", 0)
        self.vpip = stats.get("vpip", 0)
        self.pfr = stats.get("pfr", 0)
        self.wtsd = stats.get("wtsd", 0)
        self.wsd = stats.get("wsd", 0)
        self.af = stats.get("af", 0)
        self.profit_bb = stats.get("profit_bb", 0)
        self.bb_per_100 = stats.get("bb_per_100", 0)
        self.win_rate = stats.get("win_rate", 0)
        self._analyze_strengths_weaknesses()

    def _analyze_strengths_weaknesses(self) -> None:
        """Auto-detect strengths and weaknesses from stats."""
        self.strengths.clear()
        self.weaknesses.clear()

        if self.total_hands < 20:
            return

        # VPIP analysis
        if 20 <= self.vpip <= 28:
            self.strengths.append(f"Preflop range discipline (VPIP {self.vpip}%)")
        elif self.vpip > 35:
            self.weaknesses.append(f"Too loose preflop (VPIP {self.vpip}%)")
        elif self.vpip < 16:
            self.weaknesses.append(f"Too tight preflop (VPIP {self.vpip}%)")

        # PFR analysis
        if self.pfr > 0 and abs(self.vpip - self.pfr) < 8:
            self.strengths.append("Good VPIP/PFR gap — aggressive preflop")
        elif self.vpip - self.pfr > 12:
            self.weaknesses.append("Too much cold-calling — tighten or 3bet more")

        # Showdown stats
        if self.wsd > 55:
            self.strengths.append(f"Strong showdown results (W$SD {self.wsd}%)")
        elif self.wsd < 45 and self.wtsd > 20:
            self.weaknesses.append(f"Losing at showdown (W$SD {self.wsd}%)")

        if self.wtsd > 35:
            self.weaknesses.append(f"Going to showdown too often (WTSD {self.wtsd}%)")

        # Profitability
        if self.bb_per_100 > 5:
            self.strengths.append(f"Winning player ({self.bb_per_100:+.1f}bb/100)")
        elif self.bb_per_100 < -10:
            self.weaknesses.append(f"Significant losses ({self.bb_per_100:+.1f}bb/100)")

        # Aggression
        if 2.0 <= self.af <= 3.5:
            self.strengths.append(f"Balanced aggression (AF {self.af:.1f})")
        elif self.af > 4.0:
            self.weaknesses.append(f"Over-aggressive (AF {self.af:.1f})")
        elif self.af < 1.5:
            self.weaknesses.append(f"Too passive (AF {self.af:.1f})")

    def get_coaching_summary(self) -> str:
        """Generate AI coaching summary from profile."""
        if self.total_hands < 20:
            return (
                "Henüz yeterli el oynamadın. En az 20 el oyna ki profilini analiz edebilelim. "
                "Şu an odaklan: pozisyon bazlı range disiplini ve pot odds hesaplama."
            )

        parts = [f"📊 {self.total_hands} el analizi:"]

        if self.strengths:
            parts.append("✅ Güçlü yönlerin:")
            for s in self.strengths:
                parts.append(f"  • {s}")

        if self.weaknesses:
            parts.append("⚠️ Geliştirilecek alanlar:")
            for w in self.weaknesses:
                parts.append(f"  • {w}")

        # Specific recommendations
        parts.append("📋 Öneriler:")
        if self.vpip > 35:
            parts.append("  1. Range trainer'da preflop disiplini çalış")
        if self.wsd < 45 and self.wtsd > 20:
            parts.append("  2. River trainer'da blocker analizi ve MDF çalış")
        if self.af < 1.5:
            parts.append("  3. Postflop trainer'da aggression drills yap")
        if self.bb_per_100 < -10:
            parts.append("  4. Leak finder'dan en büyük leak'leri belirle ve combat pack ile düzelt")

        parts.append(f"\n💰 Toplam: {self.profit_bb:+.1f}bb | {self.bb_per_100:+.1f}bb/100")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "total_hands": self.total_hands,
            "vpip": self.vpip,
            "pfr": self.pfr,
            "wtsd": self.wtsd,
            "wsd": self.wsd,
            "af": self.af,
            "profit_bb": self.profit_bb,
            "bb_per_100": self.bb_per_100,
            "win_rate": self.win_rate,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }
