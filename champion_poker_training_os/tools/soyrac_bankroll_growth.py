"""BANKROLL-MERDİVENİ BİLEŞİK BÜYÜME projeksiyonu: $100 kasa, NL2'den başla, kasa büyüdükçe
stake yükselt (move-up/down kuralı) → her bb daha çok $ = bileşik faiz. Monte-Carlo (winrate
motordan-ölçülen aralık + yukarı çıktıkça edge azalır + std gerçekçi). 3 senaryo: iyimser/
gerçekçi/temkinli winrate. Çıktı: kasa eğrisi, $1000/$5000'e ulaşma %, ruin %, el-cinsinden süre.

PYTHONPATH=. .venv/bin/python tools/soyrac_bankroll_growth.py
"""
from __future__ import annotations
import random
import statistics as st

# (ad, bb_usd) — buy-in($) = 100 × bb_usd
STAKES = [("NL2", 0.02), ("NL5", 0.05), ("NL10", 0.10), ("NL25", 0.25), ("NL50", 0.50), ("NL100", 1.00)]
EDGE_MULT = [1.00, 1.00, 0.80, 0.70, 0.55, 0.45]   # yukarı çıkınca alan sertleşir → edge azalır
UP_BI = 35        # kasa ≥ 35 × ÜST stake buy-in → çık (temkinli)
DOWN_BI = 20      # kasa < 20 × MEVCUT stake buy-in → in (kasayı koru)
STD = 90.0        # bb/100 std (6-max cash tipik varyans)
START = 100.0
MAXH = 300_000    # üst sınır el
LIVES = 3000
HPM = 25_000      # ay başına el (ciddi grinder ~25k/ay) — süre tahmini için


def buyin(si):
    return 100 * STAKES[si][1]


def run_life(base_wr, seed):
    rng = random.Random(seed)
    bank = START
    si = 0
    hit = {500: None, 1000: None, 5000: None}
    for blk in range(MAXH // 100):
        hands = (blk + 1) * 100
        wr = base_wr * EDGE_MULT[si]
        net_bb = rng.gauss(wr, STD)
        bank += net_bb * STAKES[si][1]
        if bank < 2.0:                       # < 1 NL2 buy-in → ruin
            return bank, hands, si, hit, True
        while si < len(STAKES) - 1 and bank >= UP_BI * buyin(si + 1):
            si += 1
        while si > 0 and bank < DOWN_BI * buyin(si):
            si -= 1
        for g in (500, 1000, 5000):
            if hit[g] is None and bank >= g:
                hit[g] = hands
    return bank, MAXH, si, hit, False


def main():
    print("=== BANKROLL MERDİVENİ — BİLEŞİK BÜYÜME ($100 başlangıç, NL2→NL100) ===")
    print(f"  Kural: kasa ≥ {UP_BI}×üst-buy-in → ÇIK · kasa < {DOWN_BI}×mevcut-buy-in → İN · std {STD:.0f}bb/100")
    print(f"  Edge yukarı çıktıkça azalır: {dict(zip([s[0] for s in STAKES], EDGE_MULT))}")
    print(f"  Süre: ~{HPM//1000}k el/ay varsayımı · {LIVES} bankroll-yaşamı/senaryo\n")
    SCEN = [("İYİMSER (soft alan)", 30.0), ("GERÇEKÇİ (iyi reg)", 12.0), ("TEMKİNLİ (sert/rake)", 5.0)]
    for name, wr in SCEN:
        finals, ruins, stakes_reached = [], 0, []
        h1000, h5000, r1000, r5000 = [], [], 0, 0
        for s in range(LIVES):
            bank, hands, si, hit, ruined = run_life(wr, 7000 + s)
            finals.append(bank); stakes_reached.append(si)
            if ruined:
                ruins += 1
            if hit[1000]:
                h1000.append(hit[1000]); r1000 += 1
            if hit[5000]:
                h5000.append(hit[5000]); r5000 += 1
        med = st.median(finals)
        print(f"  ▸ {name}  (winrate {wr:.0f} bb/100 baz)")
        print(f"      300k el sonu kasa: medyan ${med:,.0f}  (ort ${st.mean(finals):,.0f}, en kötü ${min(finals):.0f})")
        print(f"      $1000'e ulaşan: %{100*r1000/LIVES:.0f}"
              + (f"  (medyan ~{st.median(h1000)/1000:.0f}k el ≈ {st.median(h1000)/HPM:.1f} ay)" if h1000 else ""))
        print(f"      $5000'e ulaşan: %{100*r5000/LIVES:.0f}"
              + (f"  (medyan ~{st.median(h5000)/1000:.0f}k el ≈ {st.median(h5000)/HPM:.1f} ay)" if h5000 else ""))
        print(f"      RUİN ($100 battı): %{100*ruins/LIVES:.1f}  ·  medyan ulaşılan stake: {STAKES[int(st.median(stakes_reached))][0]}")
        print()
    print("  Not: winrate motordan-ölçülen aralık (soft alan +60-90 idi; rake+gerçek-saha için")
    print("  iyimser→temkinli ölçeklendi). std=90 bb/100 (gerçekçi cash varyansı). Monte-Carlo 3000 yaşam.")


if __name__ == "__main__":
    main()
