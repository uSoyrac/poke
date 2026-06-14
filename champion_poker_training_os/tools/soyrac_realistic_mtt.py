"""GERÇEKÇİ çeşitlendirilmiş çok-turnuva sim: Soyrac %100-kitap, GERÇEK online MTT gibi.

- Alan: realistic_mtt_mix (zayıf-ağırlıklı, gerçek stake-tier dağılımı) + Soyrac ölçüm-payı.
- Çeşitlilik: stake tier (Mikro/Düşük/Orta) × alan boyutu (45/180/200/500/1000) × yapı (turbo/regular/deep).
- Metrik: ITM% (gerçek ~%15 paid), FinalTable% (top-9), Win%, avg-finish-pct, ve GERÇEK ROI
  (top-heavy ödeme eğrisi + %10 rake → kârlılık).

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_realistic_mtt.py
"""
from __future__ import annotations
import sys, time, random
import tools.soyrac_big_mtt as BIG          # factory injection + _play_fixed (poz-fix)
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from app.engine.bot_brain import realistic_mtt_mix
from tools.soyrac_bot_sim import SoyracBrain

SOY = BIG.SOY
_RealBB = BIG._RealBB

# ── pure_book Soyrac factory ──
def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain(); b.pure_book = True; return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory

SOY_FRAC = 0.12   # alanın %12'si Soyrac (ölçüm gücü; her giriş bağımsız kayıt)


def _make_field_fn(tier):
    def fn(n, rng=None, tier=None):
        rng = rng or random
        base = realistic_mtt_mix(n, rng=rng, tier=tier)
        soy_n = max(1, int(n * SOY_FRAC))
        for i in rng.sample(range(n), min(soy_n, n)):
            base[i] = "Soyrac"
        return base
    return fn


def _payout(field):
    """Top-heavy gerçekçi MTT ödeme: ~%15 paid, power-law, %10 rake."""
    paid = max(1, round(0.15 * field))
    raw = [1.0 / (i ** 0.85) for i in range(1, paid + 1)]
    raw[0] *= 2.2
    if paid > 1:
        raw[1] *= 1.5
    s = sum(raw)
    pool = 0.90 * field                      # %10 rake
    return [pool * w / s for w in raw], paid  # prize[0]=1.lik ... buy-in=1


def run_cell(field, tier, depth_bb, seeds, base_seed=3000):
    H._START_CHIPS = int(depth_bb * PS._BB0)
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = _make_field_fn(tier)
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    prizes, paid = _payout(field)
    ent = itm = ft = win = 0
    pct_sum = 0.0
    prize_sum = 0.0
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
                if rank <= paid:
                    itm += 1
                    prize_sum += prizes[rank - 1]
                if rank <= 9:
                    ft += 1
                if rank == 1:
                    win += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000
    e = max(ent, 1)
    return {"ent": ent, "itm": 100 * itm / e, "ft": 100 * ft / e, "win": win,
            "avgpct": 100 * pct_sum / e, "roi": 100 * (prize_sum / e - 1.0), "paid": paid}


if __name__ == "__main__":
    # (etiket, tier, alan, derinlik_bb, seed)
    CELLS = [
        ("Mikro · 45 kişi · 50bb (küçük alan)",   "Mikro ($1-5)",   45,   50,  60),
        ("Mikro · 180 · 25bb (TURBO)",            "Mikro ($1-5)",   180,  25,  35),
        ("Mikro · 500 · 50bb (büyük-turbo)",      "Mikro ($1-5)",   500,  50,  12),
        ("Düşük · 200 · 100bb (DEEP/regular)",    "Düşük ($11-33)", 200,  100, 32),
        ("Düşük · 1000 · 75bb (DEVASA alan)",     "Düşük ($11-33)", 1000, 75,  6),
        ("Orta · 180 · 100bb (zor tier)",         "Orta ($55-215)", 180,  100, 32),
    ]
    print("\n" + "★" * 70)
    print("  SOYRAC %100 KİTAP · GERÇEKÇİ ÇEŞİTLENDİRİLMİŞ ÇOK-TURNUVA SİM")
    print("  Alan: gerçek zayıf-ağırlıklı (stake-tier) · ROI: top-heavy ödeme + %10 rake")
    print("★" * 70)
    print(f"\n  {'TURNUVA':<40}{'giriş':>6}{'ITM%':>7}{'FT%':>6}{'WIN':>5}{'avgF%':>7}{'ROI%':>8}")
    t0 = time.time()
    for label, tier, field, depth, seeds in CELLS:
        r = run_cell(field, tier, depth, seeds)
        print(f"  {label:<40}{r['ent']:>6}{r['itm']:>7.1f}{r['ft']:>6.1f}"
              f"{r['win']:>5}{r['avgpct']:>7.1f}{r['roi']:>+8.1f}", flush=True)
    print(f"\n  (ITM%: gerçek ~%15 paid · FT%: top-9 · avgF%: düşük=iyi · ROI%: buy-in başı net kâr)")
    print(f"  Süre: {time.time()-t0:.0f}s")
