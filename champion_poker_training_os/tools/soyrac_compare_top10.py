"""KIYAS: AYNI turnuvalarda Soyrac vs GTO Expert vs Solver Bot vs diğer profiller — top-%10 oranı.
Her oyuncu-tipi alana EŞİT oranda (~%10) enjekte edilir → aynı sahalara karşı eşit örneklem =
adil head-to-head. "100 turnuvada kaç kez ilk %10'a girer?" (rastgele şans = 10).
Çeşitli tier (Düşük/Orta/Yüksek) × alan boyutu. pure_book Soyrac, diğerleri kendi motoru.

PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_compare_top10.py
"""
from __future__ import annotations
import math
import random

import tools.soyrac_realistic_mtt as RM   # factory injection (Soyrac=pure_book, diğerleri kendi)
PS = RM.PS
H = RM.H
from app.engine.bot_brain import realistic_mtt_mix

# Kıyaslanan oyuncu tipleri (her biri eşit enjekte)
CONTENDERS = ["Soyrac", "GTO Expert", "Solver Bot", "Shark", "TAG", "Reg", "Fish", "Maniac"]


def _field_fn(tier):
    def fn(n, rng=None, tier=None):
        rng = rng or random
        base = realistic_mtt_mix(n, rng=rng, tier=tier)   # gerçekçi zayıf zemin
        frac = 0.10                                        # her tip alanın ~%10'u
        slots = rng.sample(range(n), min(int(n * frac * len(CONTENDERS)), n))
        for i, slot in enumerate(slots):
            base[slot] = CONTENDERS[i % len(CONTENDERS)]
        return base
    return fn


def run_cell(field, tier, depth_bb, seeds, acc, base_seed=5000):
    H._START_CHIPS = int(depth_bb * PS._BB0)
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = _field_fn(tier)
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    try:
        for s in range(seeds):
            r = PS.run_mtt(field, seed=base_seed + s)
            order = r.get("finish_1st_to_last", [])
            n = len(order)
            cut10 = max(1, math.ceil(0.10 * n))
            cut5 = max(1, math.ceil(0.05 * n))
            for rank, arch in enumerate(order, start=1):
                if arch not in CONTENDERS:
                    continue
                d = acc.setdefault(arch, {"ent": 0, "t10": 0, "t5": 0, "win": 0})
                d["ent"] += 1
                if rank <= cut10:
                    d["t10"] += 1
                if rank <= cut5:
                    d["t5"] += 1
                if rank == 1:
                    d["win"] += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000


CELLS = [
    # (tier, alan, derinlik_bb, seed)
    ("Düşük ($11-33)", 400, 50, 7),
    ("Orta ($55-215)", 500, 60, 6),
    ("Orta ($55-215)", 1000, 80, 3),
    ("Yüksek ($530+)", 400, 50, 7),
    ("Yüksek ($530+)", 800, 75, 4),
]


def main():
    print("=== KIYAS: AYNI sahalarda top-%10 oranı (Soyrac vs GTO vs Solver vs profiller) ===")
    print("    (her tip alana eşit ~%10 enjekte; rastgele taban = %10)\n")
    acc = {}
    for tier, field, depth, seeds in CELLS:
        run_cell(field, tier, depth, seeds, acc)
        print(f"  [koştu] {tier:<16} {field}-kişi {depth}bb × {seeds} seed", flush=True)
    print()
    rows = []
    for arch, d in acc.items():
        e = max(d["ent"], 1)
        rows.append((arch, d["ent"], 100 * d["t10"] / e, 100 * d["t5"] / e, d["win"]))
    rows.sort(key=lambda x: -x[2])   # top-%10'a göre sırala
    print(f"  {'SIRA  OYUNCU':<22}{'giriş':>6}{'TOP10%':>8}{'TOP5%':>7}{'WIN':>5}{'  edge(×taban)':>14}")
    print("  " + "-" * 60)
    for i, (arch, ent, t10, t5, win) in enumerate(rows, 1):
        star = "  ⭐SEN" if arch == "Soyrac" else ""
        print(f"  {i:<2} {arch:<18}{ent:>6}{t10:>7.1f}{t5:>7.1f}{win:>5}{t10/10:>10.2f}×{star}", flush=True)
    print("\n  Not: TOP10% = top-%10 bitirme oranı. edge = TOP10% ÷ 10 (rastgele taban). 1.0× = şans; >1 = beceri.")


if __name__ == "__main__":
    main()
