"""$15.000 hedefine EN HIZLI gerçekçi rota: $100 başlangıç (bootstrap sonrası), cash ladder
NL2→NL400, bileşik. Monte-Carlo. Gerçekçi winrate (yukarı çıktıkça edge azalır) + std + 2 config:
GÜVENLİ (35/20 buy-in) vs HIZLI (22/12 buy-in, daha çok ruin riski). Süre = el ÷ aylık-hacim.

PYTHONPATH=. .venv/bin/python tools/soyrac_to_15k.py
"""
from __future__ import annotations
import random
import statistics as st

# (ad, bb_usd) buy-in = 100×bb_usd
STAKES = [("NL2", .02), ("NL5", .05), ("NL10", .10), ("NL25", .25), ("NL50", .50),
          ("NL100", 1.0), ("NL200", 2.0), ("NL400", 4.0)]
# edge yukarı çıktıkça azalır (gerçekçi: micro soft, mid-high sert). base_wr × bu çarpan.
EDGE_MULT = [1.0, 0.90, 0.80, 0.62, 0.48, 0.36, 0.26, 0.18]
STD = 95.0
START, TARGET = 100.0, 15000.0
MAXH = 3_000_000
LIVES = 3000
VOLUMES = {"part-time (~25k/ay)": 25_000, "ciddi (~50k/ay)": 50_000, "grinder (~100k/ay)": 100_000}


def buyin(si):
    return 100 * STAKES[si][1]


def run_life(base_wr, up_bi, down_bi, seed):
    rng = random.Random(seed)
    bank, si = START, 0
    for blk in range(MAXH // 100):
        wr = base_wr * EDGE_MULT[si]
        bank += rng.gauss(wr, STD) * STAKES[si][1]
        if bank < 2.0:
            return None, True                          # ruin
        while si < len(STAKES) - 1 and bank >= up_bi * buyin(si + 1):
            si += 1
        while si > 0 and bank < down_bi * buyin(si):
            si -= 1
        if bank >= TARGET:
            return (blk + 1) * 100, False              # hedefe ulaşan el sayısı
    return None, False                                 # ulaşamadı (süre doldu)


def report(name, base_wr, up_bi, down_bi):
    hands, reached, ruin = [], 0, 0
    for s in range(LIVES):
        h, ruined = run_life(base_wr, up_bi, down_bi, 9000 + s)
        if ruined:
            ruin += 1
        elif h is not None:
            hands.append(h); reached += 1
    print(f"  ▸ {name}  (winrate baz {base_wr:.0f} bb/100, çık {up_bi}× / in {down_bi}×)")
    print(f"      $15k'e ULAŞAN: %{100*reached/LIVES:.0f}   ·   RUİN: %{100*ruin/LIVES:.1f}")
    if hands:
        med = st.median(hands)
        print(f"      medyan el: {med/1000:.0f}k  →  süre:")
        for vn, vol in VOLUMES.items():
            print(f"         {vn:<22}: {med/vol:5.1f} ay  ({med/vol/12:.1f} yıl)")
    print()


def main():
    print("=== $100 → $15.000 EN HIZLI GERÇEKÇİ ROTA (cash ladder NL2→NL400, bileşik) ===")
    print(f"  Edge yukarı azalır: {dict(zip([s[0] for s in STAKES], EDGE_MULT))}")
    print(f"  std {STD:.0f}bb/100 · {LIVES} yaşam · hedef ${TARGET:,.0f}\n")
    print("  --- GERÇEKÇİ winrate (iyi reg, micro net ~15) ---")
    report("GÜVENLİ ladder", 15.0, 35, 20)
    report("HIZLI ladder (agresif move-up)", 15.0, 22, 12)
    print("  --- İYİMSER winrate (çok soft alan, net ~22) ---")
    report("HIZLI ladder", 22.0, 22, 12)
    print("  --- TEMKİNLİ winrate (sert/yüksek-rake, net ~9) ---")
    report("GÜVENLİ ladder", 9.0, 35, 20)
    print("  Not: NL2→NL400. Winrate gerçekçi-ölçeklenmiş (sim soft+60-90 idi; rake+gerçek-saha")
    print("  + yukarı-sertleşme ile düşürüldü). Süre = medyan-el ÷ aylık-hacim. $0→$100 bootstrap")
    print("  (freeroll) BU SÜREYE DAHİL DEĞİL — onu önüne ekle (haftalar-aylar, düşük $/saat).")


if __name__ == "__main__":
    main()
