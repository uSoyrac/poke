"""Growth & Edge Lab — pozitif edge'i üstel (geometrik) büyümeye çeviren
matematik motoru. Hem poker bankroll'u hem genel +EV bahis/işlem (kripto bot
dahil) için Kelly, risk-of-ruin ve compounding.

TEMEL FİKİR (kullanıcının sorusuna cevap): üstel büyüme = (1) doğrulanmış
pozitif edge × (2) iflas etmeden hayatta kalma. Edge yoksa compounding seni
aşağı götürür; sizing yanlışsa edge gerçek olsa bile ruin gelir. Bu modül
ikisini de sayısallaştırır.

Saf fonksiyonlar (Qt/DB bağımsız). Formüller:
  • Kelly (genel): f* = (p·g − q·l) / (g·l)        [g=kazanç, l=kayıp oranı]
  • Log-büyüme: G(f) = p·ln(1+f·g) + q·ln(1−f·l)    [çarpımsal getiri/işlem]
  • Risk of ruin (Brownian yaklaşım, poker):
        RoR = exp(−2 · μ · B / σ²)                  [μ,σ: bb/100, B: bb]
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# ── Kelly & log-büyüme (genel +EV bahis / işlem) ─────────────────────
def kelly_fraction(win_prob: float, win_payoff: float, loss_frac: float = 1.0) -> float:
    """Optimal bahis kesri (bankroll'un yüzdesi).

    win_prob  : kazanma olasılığı p ∈ (0,1)
    win_payoff: kazanınca yatırılanın kaçı kadar KÂR (g). b odds = g/l.
    loss_frac : kaybedince yatırılanın kaçı gider (l, varsayılan 1 = hepsi).

    f* = (p·g − q·l) / (g·l). Negatifse 0 (edge yok → bahis yok).
    """
    p = max(0.0, min(1.0, win_prob))
    q = 1.0 - p
    g = max(1e-9, win_payoff)
    l = max(1e-9, loss_frac)
    f = (p * g - q * l) / (g * l)
    return max(0.0, f)


def log_growth_rate(frac: float, win_prob: float, win_payoff: float,
                    loss_frac: float = 1.0) -> float:
    """Bahis başına beklenen log-büyüme G(f). Compounding hızının ölçüsü.

    G>0 → sermaye üstel büyür; G=0 → yatay; G<0 → üstel erir (overbet/edge yok).
    """
    p = max(0.0, min(1.0, win_prob))
    q = 1.0 - p
    f = frac
    up = 1.0 + f * win_payoff
    dn = 1.0 - f * loss_frac
    if up <= 0 or dn <= 0:
        return float("-inf")   # iflas eden boyut (tek kötü sonuçta sıfırlanır)
    return p * math.log(up) + q * math.log(dn)


def expected_value(win_prob: float, win_payoff: float, loss_frac: float = 1.0) -> float:
    """Birim başına aritmetik beklenen değer (edge). >0 olmazsa büyüme yok."""
    p = max(0.0, min(1.0, win_prob))
    return p * win_payoff - (1.0 - p) * loss_frac


def capital_multiple(frac: float, win_prob: float, win_payoff: float,
                     n_trials: int, loss_frac: float = 1.0) -> float:
    """n bağımsız işlemden sonra beklenen sermaye çarpanı (geometrik).

    multiple = exp(n · G(f)). 10 → sermaye 10 katına çıkar (beklenen log)."""
    g = log_growth_rate(frac, win_prob, win_payoff, loss_frac)
    if g == float("-inf"):
        return 0.0
    return math.exp(g * max(0, n_trials))


def trials_to_double(frac: float, win_prob: float, win_payoff: float,
                     loss_frac: float = 1.0) -> float:
    """Sermayeyi 2'ye katlamak için gereken işlem sayısı (ln2 / G)."""
    g = log_growth_rate(frac, win_prob, win_payoff, loss_frac)
    if g <= 0:
        return float("inf")
    return math.log(2.0) / g


# ── Poker bankroll: risk of ruin + önerilen bankroll ─────────────────
def risk_of_ruin(winrate_per100: float, std_per100: float,
                 bankroll_bb: float) -> float:
    """İflas olasılığı (Brownian yaklaşım). winrate/std bb/100, bankroll bb.

    RoR = exp(−2 · μ · B / σ²);  μ=winrate/100·hand? — per-100 formda
    sadeleşir: exp(−2 · winrate · B / std²). winrate≤0 → kesin iflas (1.0).
    """
    if winrate_per100 <= 0:
        return 1.0
    if std_per100 <= 0:
        return 0.0
    exponent = -2.0 * winrate_per100 * bankroll_bb / (std_per100 ** 2)
    return max(0.0, min(1.0, math.exp(exponent)))


def bankroll_for_ror(winrate_per100: float, std_per100: float,
                     target_ror: float = 0.05) -> float:
    """Hedef iflas olasılığı için gereken bankroll (bb).

    B = −ln(hedef) · σ² / (2 · μ). winrate≤0 → sonsuz (hiçbir roll yetmez)."""
    if winrate_per100 <= 0:
        return float("inf")
    target = max(1e-9, min(0.999, target_ror))
    return -math.log(target) * (std_per100 ** 2) / (2.0 * winrate_per100)


# ── Yüksek seviye analiz (UI için) ───────────────────────────────────
@dataclass
class EdgeReport:
    ev: float                 # birim başına aritmetik edge
    kelly: float              # optimal kesir f*
    half_kelly: float         # pratikte önerilen (varyans/2, büyüme ~%75)
    growth_full: float        # G(f*) — full Kelly log-büyüme
    growth_chosen: float      # G(seçilen kesir)
    chosen_frac: float
    multiple_chosen: float    # n işlemde sermaye çarpanı (seçilen kesirle)
    trials_double: float      # 2'ye katlama (seçilen kesirle)
    overbet: bool             # seçilen kesir > full Kelly mi? (tehlike)
    n_trials: int
    has_edge: bool


def analyze_edge(win_prob: float, win_payoff: float, loss_frac: float = 1.0,
                 chosen_frac: float | None = None, n_trials: int = 100) -> EdgeReport:
    """Genel +EV bahis/işlem analizi (bot, poker spot, herhangi karar).

    chosen_frac verilmezse half-Kelly kullanılır (akıllı varsayılan)."""
    ev = expected_value(win_prob, win_payoff, loss_frac)
    k = kelly_fraction(win_prob, win_payoff, loss_frac)
    half = k / 2.0
    cf = half if chosen_frac is None else max(0.0, chosen_frac)
    return EdgeReport(
        ev=ev,
        kelly=k,
        half_kelly=half,
        growth_full=log_growth_rate(k, win_prob, win_payoff, loss_frac),
        growth_chosen=log_growth_rate(cf, win_prob, win_payoff, loss_frac),
        chosen_frac=cf,
        multiple_chosen=capital_multiple(cf, win_prob, win_payoff, n_trials, loss_frac),
        trials_double=trials_to_double(cf, win_prob, win_payoff, loss_frac),
        overbet=cf > k + 1e-9,
        n_trials=n_trials,
        has_edge=ev > 0 and k > 0,
    )


@dataclass
class BankrollReport:
    winrate_per100: float
    std_per100: float
    bankroll_bb: float
    buyin_bb: float
    buyins: float             # bankroll / buy-in
    ror: float                # mevcut roll'la iflas olasılığı
    safe_bankroll_bb: float   # %5 RoR için gereken
    safe_buyins: float        # onun buy-in cinsi
    ev_per100_bb: float       # = winrate
    healthy: bool             # RoR < %5 mı


def analyze_bankroll(winrate_per100: float, std_per100: float,
                     bankroll_bb: float, buyin_bb: float = 100.0,
                     target_ror: float = 0.05) -> BankrollReport:
    """Poker bankroll sağlığı: iflas riski + güvenli roll önerisi."""
    safe = bankroll_for_ror(winrate_per100, std_per100, target_ror)
    ror = risk_of_ruin(winrate_per100, std_per100, bankroll_bb)
    return BankrollReport(
        winrate_per100=winrate_per100,
        std_per100=std_per100,
        bankroll_bb=bankroll_bb,
        buyin_bb=max(1e-9, buyin_bb),
        buyins=bankroll_bb / max(1e-9, buyin_bb),
        ror=ror,
        safe_bankroll_bb=safe,
        safe_buyins=(safe / max(1e-9, buyin_bb)) if math.isfinite(safe) else float("inf"),
        ev_per100_bb=winrate_per100,
        healthy=ror < target_ror,
    )


# Tipik oyun-formatı std referansları (bb/100) — UI'da varsayılan/ipucu
TYPICAL_STD = {
    "Cash 6-max": 90.0,
    "Cash Full Ring": 75.0,
    "MTT": 150.0,      # turnuva varyansı çok yüksek
    "Spin/Hyper": 250.0,
}
