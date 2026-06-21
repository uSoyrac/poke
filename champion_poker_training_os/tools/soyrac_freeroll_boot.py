"""$0→$100 FREEROLL BOOTSTRAP sim. DÜRÜSTLÜK: hero'nun finish-DAĞILIMI motordan GERÇEK ölçülür
(soft büyük-alan MTT); yalnız FREEROLL ÖDÜL-YAPISI varsayımdır (tipik site değerleri, açıkça
etiketli). 3 ödül-havuzu senaryosu ($25/$50/$100). Çıktı: $100'e medyan turnuva sayısı + süre.

PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_freeroll_boot.py
"""
from __future__ import annotations
import math
import random

import tools.soyrac_realistic_mtt as RM   # factory injection (pure_book) + makine
PS = RM.PS
H = RM.H

COLLECT_FIELD = 500     # finish-yüzdesi toplama alanı (Mikro=en soft mevcut; freeroll daha da soft olabilir → muhafazakâr)
COLLECT_SEEDS = 12
TIER = "Mikro ($1-5)"


def collect_finish_pcts():
    """Motordan GERÇEK hero finish-yüzdesi dağılımı (0=1.lik, 1=son)."""
    H._START_CHIPS = int(50 * PS._BB0)     # ~50bb turbo-ish freeroll derinliği
    H.realistic_mtt_mix = RM._make_field_fn(TIER)
    if hasattr(PS, "realistic_mtt_mix"):
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    pcts = []
    for s in range(COLLECT_SEEDS):
        r = PS.run_mtt(COLLECT_FIELD, seed=12000 + s)
        order = r.get("finish_1st_to_last", [])
        n = len(order)
        for rank, arch in enumerate(order, start=1):
            if arch == "Soyrac":
                pcts.append((rank - 1) / max(n - 1, 1))
    H._START_CHIPS = 5000
    return pcts


def freeroll_payout(pct, field, pool, paid_frac=0.12):
    """VARSAYIM: top-heavy freeroll ödemesi. paid_frac paid, power-law, 1.lik şişirilmiş."""
    paid = max(1, int(paid_frac * field))
    rank = int(round(pct * (field - 1))) + 1
    if rank > paid:
        return 0.0
    raw = [1.0 / (i ** 0.80) for i in range(1, paid + 1)]
    raw[0] *= 2.5
    if paid > 1:
        raw[1] *= 1.5
    s = sum(raw)
    return pool * raw[rank - 1] / s


def main():
    print("=== $0 → $100 FREEROLL BOOTSTRAP (hero finish=MOTOR-ÖLÇÜM, ödül=VARSAYIM) ===")
    pcts = collect_finish_pcts()
    # ölçülen şekil
    t10 = 100 * sum(1 for p in pcts if p <= 0.10) / len(pcts)
    t1 = 100 * sum(1 for p in pcts if p <= 0.01) / len(pcts)
    print(f"  Motordan ölçülen hero finish ({len(pcts)} giriş, {COLLECT_FIELD}-alan soft):"
          f" top-%10={t10:.0f}%, top-%1={t1:.1f}%, medyan-yer=%{100*sorted(pcts)[len(pcts)//2]:.0f}\n")

    FIELD = 1500            # VARSAYIM: tipik freeroll alanı
    LIVES = 4000
    print(f"  Freeroll VARSAYIMLARI: alan {FIELD} kişi, top-%12 paid, top-heavy power-law.")
    print(f"  {'ödül havuzu':<14}{'1.lik ~$':>10}{'medyan turnuva→$100':>22}{'süre (3/gün)':>16}{'süre (8/gün)':>14}")
    print("  " + "-" * 76)
    for pool in (25.0, 50.0, 100.0):
        first = freeroll_payout(0.0, FIELD, pool)
        counts = []
        for life in range(LIVES):
            rng = random.Random(20000 + life)
            bank = 0.0
            t = 0
            while bank < 100.0 and t < 20000:
                t += 1
                bank += freeroll_payout(rng.choice(pcts), FIELD, pool)
            counts.append(t)
        med = sorted(counts)[len(counts) // 2]
        d3 = med / 3.0
        d8 = med / 8.0
        print(f"  ${pool:<13.0f}{first:>10.2f}{med:>20} tn{d3:>13.0f} gün{d8:>11.0f} gün")
    print("\n  NOT: hero finish-dağılımı GERÇEK motor-ölçümü (skill kanıtlı). Freeroll ödül-havuzu/alan/")
    print("  paid% VARSAYIM (siteye göre değişir → bu sayı 'tahmin', cash-ladder gibi kanıt DEĞİL).")
    print("  Gerçek freeroll alanı bu bottan DAHA ZAYIF olabilir → sonuç muhafazakâr (daha hızlı olabilir).")
    print("  Satellite hariç (o ayrı kaldıraç). Süre = bir freeroll'u deep oynamak saatler sürer.")


if __name__ == "__main__":
    main()
