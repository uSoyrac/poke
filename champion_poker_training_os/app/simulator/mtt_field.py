"""MTT Field Simulator.

Manages a large tournament field (50–1,000 players) where the hero plays
at a single 9-player table while all other background tables run
statistically in the background.

Algorithm sources:
  - ITM %: industry standard (PokerStars / GGPoker) ~8–18% by field size
  - Elimination model: phase-adjusted Poisson process
  - Prize distribution: exponential decay (1st ~28% of pool)
"""
from __future__ import annotations

import math
import random


# ── ITM place count by field size ─────────────────────────────────────

def itm_places(field: int) -> int:
    """Return standard number of paid places for a given field size."""
    if field <= 2:   return 1
    if field <= 6:   return 2
    if field <= 9:   return 3
    if field <= 18:  return max(3, round(field * 0.18))
    if field <= 50:  return max(5, round(field * 0.18))
    if field <= 100: return max(9, round(field * 0.15))
    if field <= 200: return max(15, round(field * 0.12))
    if field <= 500: return max(27, round(field * 0.10))
    return max(50, round(field * 0.08))


def stack_phase(bb: float) -> tuple[str, str, str]:
    """Efektif stack derinliğinden (bb) strateji fazı: (anahtar, kısa etiket,
    koç metni). Playbook → MTT Stack Derinliği Fazları ile birebir."""
    if bb >= 40:
        return ("deep", "🟢 DERİN",
                "Derin stack (>40bb): cash gibi oyna — postflop avantajını kullan, "
                "suited connector / küçük pair ile set/draw avla, pozisyonu kullan. "
                "(Playbook → MTT Stack Fazları)")
    if bb >= 20:
        return ("mid", "🟡 ORTA",
                "Orta stack (20-40bb): 3-bet'ler genelde commit eder; range'i "
                "sıkılaştır, draw'larla taşma, fold equity'yi koru. SPR farkındalığı kritik.")
    if bb >= 10:
        return ("short", "🟠 KISA",
                "Kısa stack (10-20bb): re-steal jam + open-jam devrede; net preflop "
                "kararlar, marjinal postflop manevra yok — fold equity en güçlü silahın.")
    return ("pushfold", "🔴 PUSH/FOLD",
            "Push/Fold (<10bb): Nash itme/yatma tablosuna göre oyna; pozisyon + "
            "stack'e göre jam range; limp/marjinal call YOK.")


def icm_pressure_for(alive: int, paid: int) -> float:
    """Bubble/ITM yakınlığından ICM baskısı (0..1). Bot'ların marjinal
    calloff'ları sıkılaştırması için. Erken aşama 0; bubble'da en yüksek."""
    if paid <= 0 or alive <= 0:
        return 0.0
    d = alive - paid                      # para'ya uzaklık (>0 = henüz dışında)
    if d <= 0:
        return 0.45                       # ITM — FT ladder baskısı (orta)
    near = max(2, round(paid * 0.10))
    if d <= near:
        return 0.9                        # MONEY BUBBLE — en yüksek
    if d <= paid:
        return 0.5                        # bubble yakını
    return 0.0                            # erken — ICM yok


# ── Prize table builder ────────────────────────────────────────────────

def build_prize_table(prize_pool: float, num_paid: int) -> list[tuple[int, float]]:
    """Return [(place, prize_$), ...] using exponential decay.

    Roughly: 1st ≈ 28%, 2nd ≈ 17%, 3rd ≈ 11%, min-cash ≈ 1–2%.
    """
    if num_paid == 0:
        return []
    if num_paid == 1:
        return [(1, round(prize_pool, 2))]

    # Exponential weight: w_i = exp(-1.8 * i / n)
    weights = [math.exp(-1.8 * i / num_paid) for i in range(num_paid)]
    tw = sum(weights)
    prizes = [round(prize_pool * w / tw, 2) for w in weights]

    # Fix floating-point rounding
    diff = round(prize_pool - sum(prizes), 2)
    prizes[0] = round(prizes[0] + diff, 2)

    return [(i + 1, p) for i, p in enumerate(prizes)]


# ── Poisson sampler ────────────────────────────────────────────────────

def _poisson(lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 25:
        # Normal approximation for large lambda
        return max(0, round(random.gauss(lam, math.sqrt(lam))))
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


# ── Main class ────────────────────────────────────────────────────────

class MTTField:
    """Large MTT field manager.

    Hero always plays at their own 9-player table (tracked externally by
    TournamentSimulatorScreen).  Background players are eliminated
    statistically: each call to `tick()` simulates one hand across all
    background tables and eliminates the expected number of players using
    a phase-adjusted Poisson model.

    Usage::

        field = MTTField(field_size=200, buyin=22.0, structure="regular")
        field.update_hero_table(9)   # hero table starts with 9 players

        # Every hand hero plays:
        eliminated = field.tick()          # simulate background tables
        field.update_hero_table(n_alive)   # tell field how many survive
    """

    def __init__(
        self,
        field_size: int = 200,
        buyin: float = 22.0,
        structure: str = "regular",   # "regular" | "turbo" | "hyper"
        hero_table_size: int = 9,
        tier: "str | None" = None,    # stake tier → gerçekçi skill kompozisyonu
        hero_archetypes: "list[str] | None" = None,  # hero masasındaki gerçek botlar
    ) -> None:
        self.field_size      = field_size
        self.buyin           = buyin
        self.structure       = structure
        self.hero_table_size = hero_table_size
        self.tier            = tier

        # Hero masasındaki gerçek arketiplerin 'strong' (elit) oranı. Kullanıcı
        # GTO/ICM expert, Negreanu gibi oyuncular eklediğinde zorluk bunu
        # yansıtmalı — yoksa alan-geneli soft olduğu için 'KOLAY' diyordu (C bug).
        self._hero_strong_frac = 0.0
        if hero_archetypes:
            try:
                from app.engine.bot_brain import archetype_skill
                n = len(hero_archetypes)
                if n:
                    strong = sum(1 for a in hero_archetypes
                                 if archetype_skill(a) == "strong")
                    self._hero_strong_frac = strong / n
            except Exception:
                self._hero_strong_frac = 0.0

        # Economics
        self.prize_pool  = round(buyin * field_size, 2)
        self.paid_places = itm_places(field_size)
        self.prizes      = build_prize_table(self.prize_pool, self.paid_places)

        # State — arka plan oyuncuları SKILL kovalarında tutulur (gerçekçi
        # alan dağılımı: ~%62 zayıf, %26 orta, %12 güçlü). Zayıflar daha hızlı
        # patlar (spew) → derin aşamada alan gerçekçi şekilde GÜÇLÜYE kayar
        # (skill-korelasyonlu hayatta kalma). Toplam eleme sayısı (Poisson)
        # değişmez; sadece HANGİ kovadan elendiği ağırlıklıdır.
        bg = max(0, field_size - hero_table_size)
        # Skill kompozisyonu seçili stake tier'ından (yoksa varsayılan düşük-stake)
        try:
            from app.engine.bot_brain import tier_skill_fractions
            fr = tier_skill_fractions(tier)
        except Exception:
            fr = {"weak": 0.62, "mid": 0.26, "strong": 0.12}
        self._bg = {
            "weak":   round(bg * fr["weak"]),
            "mid":    round(bg * fr["mid"]),
            "strong": 0,   # kalan → strong (yuvarlama farkını massetir)
        }
        self._bg["strong"] = max(0, bg - self._bg["weak"] - self._bg["mid"])
        self._hero_table_remaining  = hero_table_size
        self._hand_count            = 0
        self._total_bg_eliminated   = 0

        # Recent elimination log for UI display
        # Each entry: (hand_no, eliminated_count)
        self._log: list[tuple[int, int]] = []

        # Per-hand bust probability (base rate, adjusted each tick)
        _rates = {"regular": 0.025, "turbo": 0.048, "hyper": 0.095}
        self._base_rate = _rates.get(structure, 0.025)

    # Kovaların per-capita kırılganlığı (bust olasılığı çarpanı) — sınıf sabiti.
    _FRAGILITY = {"weak": 1.5, "mid": 1.0, "strong": 0.55}

    # ── properties ────────────────────────────────────────────────────

    @property
    def _bg_remaining(self) -> int:
        """Arka plan toplam (kovaların toplamı) — tek doğru kaynak."""
        return sum(self._bg.values())

    @property
    def players_remaining(self) -> int:
        return max(0, self._bg_remaining + self._hero_table_remaining)

    @property
    def bg_players_remaining(self) -> int:
        return self._bg_remaining

    @property
    def bg_composition(self) -> dict:
        """Arka plan skill kompozisyonu: {'weak':%, 'mid':%, 'strong':%} (oran)."""
        tot = max(1, self._bg_remaining)
        return {k: v / tot for k, v in self._bg.items()}

    @property
    def strong_fraction(self) -> float:
        """Hayatta kalan arka-plan alanında güçlü oyuncu oranı (derinleştikçe artar)."""
        return self.bg_composition["strong"]

    @property
    def hero_strong_fraction(self) -> float:
        """Hero masasındaki elit oyuncu oranı (sabit — masa kompozisyonu)."""
        return self._hero_strong_frac

    def toughness(self) -> tuple[float, str]:
        """Turnuva 'zorluk' skoru (0..1) + etiket: alan sertliği (strong oranı)
        + ICM/bubble baskısı birleşik. Hero'ya 'bu turnuva ne kadar zor' der.

        Strong oranı = max(alan-geneli, hero-masası) — hero kendi masasındaki
        elit oyuncuları HER EL hisseder; masası shark doluysa alan soft olsa
        bile turnuva zordur."""
        strong = max(self.strong_fraction, self.hero_strong_fraction)
        d = self.bubble_distance
        # Bubble yakınlığı baskısı (0..1)
        if d <= 0:
            bub = 0.5
        elif d <= max(2, round(self.paid_places * 0.10)):
            bub = 0.9
        elif d <= self.paid_places:
            bub = 0.5
        else:
            bub = 0.1
        score = min(1.0, 0.6 * min(1.0, strong / 0.30) + 0.4 * bub)
        if score < 0.33:
            tag = "🟢 KOLAY"
        elif score < 0.6:
            tag = "🟡 ORTA"
        elif score < 0.8:
            tag = "🟠 ZOR"
        else:
            tag = "🔴 ÇOK ZOR"
        return score, tag

    def field_strength_label(self) -> str:
        """Alan sertliği için kısa etiket (UI/koç). Arka plan boşsa '' döner."""
        if self._bg_remaining <= 0:
            return ""
        s = self.strong_fraction
        if s < 0.14:
            tag = "soft"
        elif s < 0.24:
            tag = "sertleşiyor"
        else:
            tag = "reg-ağır"
        return f"{tag} (%{s * 100:.0f} güçlü)"

    def _remove_from_buckets(self, n: int, fragility_weighted: bool) -> int:
        """Arka plandan n oyuncu çıkar. fragility_weighted=True → eleme (zayıf
        daha çok patlar); False → masaya taşıma (hayatta kalanlar arası rastgele).
        Döner: gerçekten çıkarılan sayı."""
        removed = 0
        buckets = ("weak", "mid", "strong")
        for _ in range(n):
            if self._bg_remaining <= 0:
                break
            if fragility_weighted:
                wts = [self._bg[b] * self._FRAGILITY[b] for b in buckets]
            else:
                wts = [self._bg[b] for b in buckets]
            if sum(wts) <= 0:
                break
            b = random.choices(buckets, weights=wts, k=1)[0]
            self._bg[b] -= 1
            removed += 1
        return removed

    @property
    def bubble_distance(self) -> int:
        """> 0 → N from bubble.  0 / negative → ITM or on bubble."""
        return self.players_remaining - self.paid_places

    @property
    def is_itm(self) -> bool:
        return self.players_remaining <= self.paid_places

    @property
    def tables_active(self) -> int:
        """Estimated active tables (hero's + background), rounded up."""
        return max(1, math.ceil(self.players_remaining / self.hero_table_size))

    @property
    def total_eliminated(self) -> int:
        return self.field_size - self.players_remaining

    # ── prize helpers ──────────────────────────────────────────────────

    def prize_for_place(self, place: int) -> float:
        for pos, prize in self.prizes:
            if pos == place:
                return prize
        return 0.0

    def min_cash(self) -> float:
        return self.prizes[-1][1] if self.prizes else 0.0

    def prize_summary(self, n: int = 5) -> str:
        """Return a compact prize string for the UI strip."""
        ordinals = {1: "1st", 2: "2nd", 3: "3rd"}
        parts = []
        for pos, prize in self.prizes[:n]:
            label = ordinals.get(pos, f"{pos}th")
            parts.append(f"{label}: ${prize:,.0f}")
        if len(self.prizes) > n:
            parts.append(f"Min-cash: ${self.min_cash():,.0f}")
        return "  ·  ".join(parts)

    # ── simulation ────────────────────────────────────────────────────

    def tick(self, hands: int = 1) -> int:
        """Simulate `hands` hands across background tables.

        Returns total background players eliminated this call.
        Should be called once per hand hero plays.
        """
        if self._bg_remaining <= 0:
            return 0

        eliminated = 0
        for _ in range(hands):
            if self._bg_remaining <= 0:
                break
            self._hand_count += 1

            # Phase-adjusted bust rate
            remaining_pct = self.players_remaining / max(self.field_size, 1)
            if remaining_pct > 0.80:
                rate = self._base_rate * 0.55    # early: tight play, low busts
            elif remaining_pct > 0.20:
                rate = self._base_rate            # mid: normal
            else:
                rate = self._base_rate * 1.45    # bubble / FT: aggression spikes

            # Expected eliminations = rate × bg_players (Poisson draw)
            expected = rate * self._bg_remaining
            n = _poisson(expected)
            n = min(n, self._bg_remaining)

            if n > 0:
                # Eleme kovalara KIRILGANLIK ağırlıklı dağıtılır (zayıf daha çok
                # patlar) → toplam n aynı, ama alan derinleştikçe güçlüye kayar.
                n = self._remove_from_buckets(n, fragility_weighted=True)
                self._total_bg_eliminated += n
                eliminated += n
                self._log.append((self._hand_count, n))
                # Keep log short
                if len(self._log) > 60:
                    self._log = self._log[-40:]

        return eliminated

    def update_hero_table(self, n_alive: int) -> None:
        """Notify field when a player is eliminated at hero's table."""
        self._hero_table_remaining = max(0, n_alive)

    @property
    def is_final_table(self) -> bool:
        """Alan tek masaya indi mi (≤ hero_table_size)? FT'de masa dengeleme
        durur — masa kazanana kadar oynanır."""
        return self.players_remaining <= self.hero_table_size

    @property
    def avg_stack_chips(self) -> float:
        """Sahadaki ortalama stack (chip). Yeni oturan oyuncuların stack'i
        için — toplam chip = field_size * starting_chips (≈100bb varsayımı yok;
        chip değeri çağıran tarafından ölçeklenebilir)."""
        rem = max(1, self.players_remaining)
        # field başına 100bb başlangıç kabulü → toplam chip sabit
        total_chips = self.field_size * 10000.0
        return total_chips / rem

    def move_into_hero_table(self, n: int) -> int:
        """Kırılan masalardan hero'nun masasına n oyuncu taşı (table balancing).

        Toplam saha sayısı DEĞİŞMEZ — arka plandan hero masasına aktarır.
        Gerçek MTT'de kısa masalar kırılıp oyuncular dağıtılır. Döner: taşınan.
        """
        n = max(0, min(int(n), self._bg_remaining))
        # Masaya taşınanlar hayatta kalanlar arasından RASTGELE (kompozisyona
        # orantılı) — kırılganlık ağırlığı yok (eleme değil, dengeleme).
        moved = self._remove_from_buckets(n, fragility_weighted=False)
        self._hero_table_remaining += moved
        return moved

    def hero_finish(self) -> tuple[int, float]:
        """Call when hero busts.  Returns (finish_place, prize_$)."""
        place = self.players_remaining
        return place, self.prize_for_place(place)
