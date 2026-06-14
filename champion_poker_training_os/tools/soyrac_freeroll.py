"""FREEROLL senaryosu: 500 kişi, bedava giriş, DÜZ top-10 = $5. Soyrac %100-kitap.
Freeroll alanı = EN YUMUŞAK (bedava → rekreasyonel/AFK/umursamaz çok). Çıktı: bir
girişin top-10'a girme oranı → "100 turnuva oynarsan" projeksiyonu + $ beklentisi.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_freeroll.py [seeds]
"""
from __future__ import annotations
import sys, time, random
import tools.soyrac_big_mtt as BIG
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from tools.soyrac_bot_sim import SoyracBrain

SOY = BIG.SOY
_RealBB = BIG._RealBB

def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain(); b.pure_book = True; return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory

# ORTALAMA POKER OYUNCULARI alanı: HİÇ solver/GTO/shark/elit YOK (strong-tier=0).
# Karışım = orta-seviye reg (mid) + rekreasyonel (weak), ~%50/%50 — tipik "ortalama" kalabalık.
_FREEROLL = (
    # MID (ortalama-competent reg'ler) ~%52
    ["TAG"] * 6 + ["Reg"] * 6 + ["LAG"] * 4 + ["Balanced Reg"] * 4 +
    ["Weak Reg"] * 4 + ["Overfolder"] * 2 + ["Overbluffer"] * 2 +
    # WEAK (rekreasyonel) ~%48
    ["Fish"] * 5 + ["Calling Station"] * 4 + ["Loose Rec"] * 4 +
    ["Tight Passive"] * 3 + ["Nit"] * 3 + ["Aggro Fish"] * 2 + ["Rock"] * 1)
SOY_FRAC = 0.10   # ölçüm gücü; kalan %90 ortalama-oyuncu (elit YOK)


def _field_fn(n, rng=None, tier=None):
    rng = rng or random
    base = [rng.choice(_FREEROLL) for _ in range(n)]
    for i in rng.sample(range(n), max(1, int(n * SOY_FRAC))):
        base[i] = "Soyrac"
    return base


def run(field, seeds, depth_bb=75, paid=10, prize=5.0, base_seed=9000):
    H._START_CHIPS = int(depth_bb * PS._BB0)
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = _field_fn
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = _field_fn
    ent = itm = ft = win = 0
    pct_sum = 0.0
    best = 999
    try:
        for s in range(seeds):
            r = PS.run_mtt(field, seed=base_seed + s)
            order = r.get("finish_1st_to_last", [])
            n = len(order)
            for rank, arch in enumerate(order, start=1):
                if arch != "Soyrac":
                    continue
                ent += 1
                pct_sum += (rank - 1) / max(n - 1, 1)
                best = min(best, rank)
                if rank <= paid:
                    itm += 1
                if rank <= 9:
                    ft += 1
                if rank == 1:
                    win += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000
    e = max(ent, 1)
    cash_rate = itm / e
    return {"ent": ent, "cash_rate": 100 * cash_rate, "ft": 100 * ft / e,
            "win": win, "best": best, "avgpct": 100 * pct_sum / e,
            "exp_cashes_100": cash_rate * 100, "exp_usd_100": cash_rate * 100 * prize}


if __name__ == "__main__":
    SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 35
    FIELD = 500
    print("\n" + "★" * 64)
    print(f"  FREEROLL · {FIELD} kişi · DÜZ top-10 = $5 · Soyrac %100-kitap")
    print(f"  Alan: ORTALAMA oyuncular (mid+weak) · HİÇ solver/GTO/shark YOK · {SEEDS} turnuva")
    print("★" * 64)
    r = run(FIELD, SEEDS)
    base = 100 * 10 / FIELD     # rastgele oyuncunun top-10 oranı = %2
    print(f"\n  Soyrac giriş (ölçüm): {r['ent']}")
    print(f"  TOP-10 oranı (cash):  %{r['cash_rate']:.1f}   (rastgele taban: %{base:.0f})")
    print(f"  Final-table (top-9):  %{r['ft']:.1f}")
    print(f"  Galibiyet:            {r['win']}  ·  en iyi sıra: {r['best']}/{FIELD}")
    print(f"  Ortalama bitiş:       üst %{r['avgpct']:.0f}")
    print(f"\n  ── 100 FREEROLL OYNARSAN (1 giriş/turnuva) ──")
    print(f"  Beklenen para-girme:  ~{r['exp_cashes_100']:.0f} / 100 turnuva")
    print(f"  Beklenen kazanç:      ~${r['exp_usd_100']:.0f}  (bedava giriş → hepsi kâr)")
    print(f"  (taban rastgele oyuncu: ~2/100 = $10)")
