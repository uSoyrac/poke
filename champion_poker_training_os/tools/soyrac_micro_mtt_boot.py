"""$5→$100 MICRO-MTT BOOTSTRAP: freeroll-tohum sonrası gerçek-ödüllü micro MTT merdiveni.
Hero finish-dağılımı = MOTOR-ÖLÇÜM (soft 150-alan); MTT ödül/fee = etiketli varsayım (tipik).
Bankroll: stake'i ≥50 buy-in tutacak şekilde seç (MTT yüksek varyans). Çıktı: $100'e medyan turnuva + süre.

PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_micro_mtt_boot.py
"""
from __future__ import annotations
import random

import tools.soyrac_realistic_mtt as RM
PS = RM.PS
H = RM.H

FIELD = 150
TIER = "Düşük ($11-33)"      # micro MTT alanı (soft ama freeroll'dan biraz dişli)
COLLECT_SEEDS = 16
BUYINS = [0.10, 0.25, 0.50, 1.00]   # micro MTT buy-in merdiveni ($)
FEE = 0.10                          # %10 rake (buy-in üstüne)
PAID_FRAC = 0.15
UP_BI = 50                          # üst stake'in 50 buy-in'i → çık (MTT yüksek varyans)


def collect():
    H._START_CHIPS = int(50 * PS._BB0)
    H.realistic_mtt_mix = RM._make_field_fn(TIER)
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    pcts = []
    for s in range(COLLECT_SEEDS):
        r = PS.run_mtt(FIELD, seed=14000 + s)
        order = r.get("finish_1st_to_last", [])
        n = len(order)
        for rank, arch in enumerate(order, start=1):
            if arch == "Soyrac":
                pcts.append((rank - 1) / max(n - 1, 1))
    H._START_CHIPS = 5000
    return pcts


def payout(pct, buyin):
    pool = FIELD * buyin                       # ödül havuzu (fee hariç)
    paid = max(1, int(PAID_FRAC * FIELD))
    rank = int(round(pct * (FIELD - 1))) + 1
    if rank > paid:
        return 0.0
    raw = [1.0 / (i ** 0.80) for i in range(1, paid + 1)]
    raw[0] *= 2.3
    s = sum(raw)
    return pool * raw[rank - 1] / s


def stake_for(bank):
    best = BUYINS[0]
    for bi in BUYINS:
        if bank >= UP_BI * bi:
            best = bi
    return best


def main():
    print("=== $5 → $100 MICRO-MTT BOOTSTRAP (finish=MOTOR-ÖLÇÜM, ödül/fee=varsayım) ===")
    pcts = collect()
    t10 = 100 * sum(1 for p in pcts if p <= 0.10) / len(pcts)
    print(f"  Motor finish ({len(pcts)} giriş, {FIELD}-alan {TIER}): top-%10={t10:.0f}%, "
          f"medyan-yer=%{100*sorted(pcts)[len(pcts)//2]:.0f}\n")
    LIVES = 5000
    counts, ruins = [], 0
    for life in range(LIVES):
        rng = random.Random(30000 + life)
        bank = 5.0
        t = 0
        while bank < 100.0 and t < 50000:
            bi = stake_for(bank)
            entry = bi * (1 + FEE)
            if bank < entry:
                break
            t += 1
            bank -= entry
            bank += payout(rng.choice(pcts), bi)
        if bank >= 100.0:
            counts.append(t)
        else:
            ruins += 1
    med = sorted(counts)[len(counts) // 2] if counts else None
    print(f"  $100'e ULAŞAN: %{100*len(counts)/LIVES:.0f}  ·  ruin(<entry): %{100*ruins/LIVES:.1f}")
    if med:
        print(f"  medyan turnuva ($5→$100): {med}")
        for label, perday in (("rahat 3/gün", 3), ("ciddi 6/gün", 6), ("yoğun 12/gün", 12)):
            print(f"     {label:<14}: {med/perday:5.0f} gün ({med/perday/30:.1f} ay)")
    print(f"\n  Merdiven: bankroll ≥ {UP_BI}×buy-in → üst stake. $5→$0.10 MTT → $12.5→$0.25 →")
    print(f"  $25→$0.50 → $50→$1 → $100. Ödül top-%{PAID_FRAC*100:.0f}, fee %{FEE*100:.0f} (VARSAYIM).")
    print("  NOT: finish GERÇEK motor-ölçüm; ödül-yapısı/fee/alan varsayım (site'ye göre değişir).")


if __name__ == "__main__":
    main()
