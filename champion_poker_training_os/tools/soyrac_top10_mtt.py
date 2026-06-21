"""TOP-%10 MTT başarı ölçümü — çeşitlendirilmiş gerçekçi alanlar (kullanıcı tanımı: ITM = top %10).
Çeşitlilik: 4 saha-tier (Mikro→Yüksek, giderek sertleşen profil) × alan-boyutu (180/500/1000)
× yapı/derinlik (turbo 25bb / regular 50bb / deep 100bb). pure_book Soyrac, deterministik.
SOY_FRAC=0.12 (alanın %12'si Soyrac) → her turnuva çok bağımsız giriş = oran hızlı stabilize.

Metrik: TOP10% (rank ≤ %10×alan, rastgele taban %10) · TOP5% (taban %5) · WIN · avgF% (düşük=iyi).
PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_top10_mtt.py
"""
from __future__ import annotations
import math

import tools.soyrac_realistic_mtt as RM   # factory injection (pure_book) + makine
PS = RM.PS
H = RM.H


def run_cell(field, tier, depth_bb, seeds, base_seed=4000):
    H._START_CHIPS = int(depth_bb * PS._BB0)
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = RM._make_field_fn(tier)
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    ent = t10 = t5 = win = 0
    pct_sum = 0.0
    try:
        for s in range(seeds):
            r = PS.run_mtt(field, seed=base_seed + s)
            order = r.get("finish_1st_to_last", [])
            n = len(order)
            cut10 = max(1, math.ceil(0.10 * n))
            cut5 = max(1, math.ceil(0.05 * n))
            for rank, arch in enumerate(order, start=1):
                if arch != "Soyrac":
                    continue
                ent += 1
                pct_sum += (rank - 1) / max(n - 1, 1)
                if rank <= cut10:
                    t10 += 1
                if rank <= cut5:
                    t5 += 1
                if rank == 1:
                    win += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000
    e = max(ent, 1)
    return {"ent": ent, "t10": 100 * t10 / e, "t5": 100 * t5 / e, "win": win,
            "avgpct": 100 * pct_sum / e}


CELLS = [
    # (etiket, tier, alan, derinlik_bb, seed) — bol çeşitlilik
    ("Mikro·180·turbo",   "Mikro ($1-5)",   180, 25, 12),
    ("Mikro·500·reg",     "Mikro ($1-5)",   500, 50, 5),
    ("Mikro·1000·deep",   "Mikro ($1-5)",   1000, 100, 3),
    ("Düşük·180·turbo",   "Düşük ($11-33)", 180, 25, 12),
    ("Düşük·500·reg",     "Düşük ($11-33)", 500, 50, 5),
    ("Düşük·1000·deep",   "Düşük ($11-33)", 1000, 100, 3),
    ("Orta·180·turbo",    "Orta ($55-215)", 180, 25, 12),
    ("Orta·500·reg",      "Orta ($55-215)", 500, 50, 5),
    ("Orta·1000·deep",    "Orta ($55-215)", 1000, 100, 3),
    ("Yüksek·180·turbo",  "Yüksek ($530+)", 180, 25, 12),
    ("Yüksek·500·reg",    "Yüksek ($530+)", 500, 50, 5),
    ("Yüksek·1000·deep",  "Yüksek ($530+)", 1000, 100, 3),
]


def main():
    print("=== TOP-%10 MTT BAŞARI (çeşitlendirilmiş gerçekçi alan, pure_book Soyrac) ===")
    print(f"{'CELL':<20}{'giriş':>6}{'TOP10%':>8}{'TOP5%':>7}{'WIN':>5}{'avgF%':>7}")
    print("-" * 53)
    by_tier = {}
    A = {"ent": 0, "t10": 0.0, "t5": 0.0, "win": 0, "pct": 0.0}
    for label, tier, field, depth, seeds in CELLS:
        m = run_cell(field, tier, depth, seeds)
        print(f"{label:<20}{m['ent']:>6}{m['t10']:>7.1f}{m['t5']:>7.1f}{m['win']:>5}{m['avgpct']:>7.1f}",
              flush=True)
        e = m["ent"]
        A["ent"] += e; A["t10"] += m["t10"] * e / 100; A["t5"] += m["t5"] * e / 100
        A["win"] += m["win"]; A["pct"] += m["avgpct"] * e / 100
        tk = tier.split(" ")[0]
        d = by_tier.setdefault(tk, {"ent": 0, "t10": 0.0, "t5": 0.0, "win": 0})
        d["ent"] += e; d["t10"] += m["t10"] * e / 100; d["t5"] += m["t5"] * e / 100; d["win"] += m["win"]
    print("-" * 53)
    print("  TIER ÖZETİ:")
    for tk, d in by_tier.items():
        e = max(d["ent"], 1)
        print(f"    {tk:<8} giriş={d['ent']:>5}  TOP10%={100*d['t10']/e:5.1f}  TOP5%={100*d['t5']/e:5.1f}  win={d['win']}")
    e = max(A["ent"], 1)
    print("-" * 53)
    print(f"{'GENEL':<20}{A['ent']:>6}{100*A['t10']/e:>7.1f}{100*A['t5']/e:>7.1f}{A['win']:>5}{100*A['pct']/e:>7.1f}")
    print("\nNot: TOP10% rastgele taban %10, TOP5% taban %5. >taban = sistem edge'i. avgF% düşük=iyi.")


if __name__ == "__main__":
    main()
