"""TOP-%1 hedefi: Soyrac %100-kitap, GERÇEKÇİ-YUMUŞAK insan alanına (gerçek freeroll/
micro: calling-station/limp-her-el/asla-fold ağırlıklı) karşı. Metrik = TOP-%1 oranı
(derin koşu/final masa — paranın olduğu yer), + ITM + win + ROI.

Adım 2 için exploit-hook: SoyracBrain.exploit_reads açılırsa postflop villain_stats geçer.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_top1pct.py [seeds_mult]
"""
from __future__ import annotations
import sys, time, random, math
import tools.soyrac_big_mtt as BIG
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from tools.soyrac_bot_sim import SoyracBrain

SOY = BIG.SOY
_RealBB = BIG._RealBB
_EXPLOIT = {"on": False}


def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain(); b.pure_book = True
        b.exploit_reads = _EXPLOIT["on"]
        return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory

# GERÇEKÇİ-YUMUŞAK İNSAN: gerçek freeroll/micro insanı (sim-fish'ten çok daha sömürülebilir):
# limp-her-el, asla-fold calling station, tilt-maniac ağırlıklı. Strong/mid YOK.
_SOFT = (["Calling Station"] * 8 + ["Fish"] * 7 + ["Loose Rec"] * 5 +
         ["Aggro Fish"] * 4 + ["Maniac"] * 3 + ["Tight Passive"] * 3 + ["Nit"] * 2)
SOY_FRAC = 0.10


def _field_fn(n, rng=None, tier=None):
    rng = rng or random
    base = [rng.choice(_SOFT) for _ in range(n)]
    for i in rng.sample(range(n), max(1, int(n * SOY_FRAC))):
        base[i] = "Soyrac"
    return base


def run(field, depth_bb, seeds, base_seed=11000):
    H._START_CHIPS = int(depth_bb * PS._BB0)
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = _field_fn
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = _field_fn
    top1_n = max(1, math.ceil(0.01 * field))      # top-%1 eşiği (200→2, 500→5, 1000→10)
    paid = max(1, round(0.15 * field))
    ent = itm = top1 = ft = win = 0
    pct_sum = 0.0
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
                if rank <= paid: itm += 1
                if rank <= top1_n: top1 += 1
                if rank <= 9: ft += 1
                if rank == 1: win += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000
    e = max(ent, 1)
    return {"ent": ent, "itm": 100*itm/e, "top1": 100*top1/e, "ft": 100*ft/e,
            "win": win, "avgpct": 100*pct_sum/e, "top1_base": 100*top1_n/field}


if __name__ == "__main__":
    mult = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    CELLS = [
        ("180 · 50bb",  180, 50,  30*mult),
        ("500 · 50bb",  500, 50,  14*mult),
        ("1000 · 75bb", 1000, 75, 7*mult),
    ]
    mode = "EXPLOIT-ON" if _EXPLOIT["on"] else "kitap (exploit-OFF)"
    print("\n" + "★" * 66)
    print(f"  TOP-%1 HEDEFİ · Soyrac %100-kitap · GERÇEKÇİ-YUMUŞAK insan alanı [{mode}]")
    print("★" * 66)
    print(f"\n  {'TURNUVA':<14}{'giriş':>7}{'TOP-1%':>9}{'(taban)':>9}{'ITM%':>7}{'FT%':>6}{'WIN':>5}{'avgF%':>7}")
    t0 = time.time()
    for label, field, depth, seeds in CELLS:
        r = run(field, depth, seeds)
        print(f"  {label:<14}{r['ent']:>7}{r['top1']:>8.1f}%{r['top1_base']:>8.1f}%"
              f"{r['itm']:>7.1f}{r['ft']:>6.1f}{r['win']:>5}{r['avgpct']:>7.1f}", flush=True)
    print(f"\n  (TOP-1% = ilk %1'e girme oranı [hedefin] · taban: rastgele oyuncu %1)")
    print(f"  Süre: {time.time()-t0:.0f}s")
