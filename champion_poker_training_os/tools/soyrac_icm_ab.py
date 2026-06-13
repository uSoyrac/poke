"""A/B: ICM-postflop survival kaldıracı (D225) deep-MTT ITM'i artırıyor mu, güçlü
hücrelere zarar veriyor mu? Paired (aynı seed) → düşük varyans karşılaştırma.

⚠️ SONUÇ (D225, 24 turnuva/hücre): NET KAZANÇ YOK → lever GERİ ALINDI. HARD 100bb ITM
+2.1 (sınırda) ama TOP3 19→16; HARD 50bb TOP3 18→11 / WIN 4→1 ÇÖKTÜ → büyük skorları
min-cash'e takas ediyor (top-heavy ödemede yanlış yön). "kazanmazsa geri al". Bu araç
artık tarihsel kayıt — bot icm_postflop'u OKUMUYOR (lever kaldırıldı) → OFF==ON çıkar.

OFF = pure_book (mevcut) · ON = pure_book + icm_postflop (ödül-sıçramasında marjinal
büyük stack-off FOLD). KURAL: kazanmazsa (veya güçlü hücreye zarar verirse) GERİ AL.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_icm_ab.py [seeds]
"""
from __future__ import annotations
import sys, time
import tools.soyrac_big_mtt as BIG
import tools.soyrac_purebook_test as PB
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from tools.soyrac_bot_sim import SoyracBrain

SOY = BIG.SOY
_RealBB = BIG._RealBB
_ICM = {"on": False}


def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain()
        b.pure_book = True
        b.icm_postflop = _ICM["on"]
        return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory


def _run(cells, seeds, field):
    out = {}
    for label, comp, depth in cells:
        rows = BIG.run_mtt_custom(field, seeds, depth, field_fn=PB._make_field_fn(comp))
        sr = rows.get("Soyrac", {})
        board = sorted(rows.items(), key=lambda x: x[1]["avg_fin_pct"])
        rank = next((i for i, (a, _) in enumerate(board, 1) if a == "Soyrac"), None)
        out[label] = {"itm": sr.get("itm_pct", 0), "top3": sr.get("top3", 0),
                      "win": sr.get("win", 0), "avgf": sr.get("avg_fin_pct", 0),
                      "rank": rank, "ntot": len(board), "ent": sr.get("ent", 0)}
    return out


if __name__ == "__main__":
    SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    FIELD = 200
    CELLS = [
        ("HARD 100bb (hedef)",  "hard",   100),
        ("HARD 50bb (hedef)",   "hard",   50),
        ("MEDIUM 100bb (zarar?)", "medium", 100),
        ("MEDIUM 25bb (zarar?)",  "medium", 25),
    ]
    t0 = time.time()
    print(f"\nICM-postflop A/B · {FIELD} kişi · {SEEDS} turnuva/hücre (paired)\n")

    _ICM["on"] = False
    print("[A] OFF (mevcut pure_book) koşuyor...", flush=True)
    off = _run(CELLS, SEEDS, FIELD)
    _ICM["on"] = True
    print("[B] ON  (pure_book + icm_postflop) koşuyor...", flush=True)
    on = _run(CELLS, SEEDS, FIELD)

    print("\n" + "═" * 74)
    print(f"  {'HÜCRE':<22}{'ITM% OFF→ON':>16}{'avgF% OFF→ON':>16}{'TOP3':>8}{'WIN':>7}")
    print("═" * 74)
    for label, _, _ in CELLS:
        a, b = off[label], on[label]
        ditm = b["itm"] - a["itm"]
        davg = b["avgf"] - a["avgf"]            # negatif=iyileşme (daha yüksek bitiş)
        c_itm = "%.1f->%.1f (%+.1f)" % (a["itm"], b["itm"], ditm)
        c_avg = "%.1f->%.1f (%+.1f)" % (a["avgf"], b["avgf"], davg)
        c_t3 = "%d->%d" % (a["top3"], b["top3"])
        c_w = "%d->%d" % (a["win"], b["win"])
        print("  %-22s%16s%16s%8s%7s" % (label, c_itm, c_avg, c_t3, c_w))
    print("═" * 74)
    print("  ITM% ↑ ve avgF% ↓ = iyileşme. Güçlü hücrelerde (MEDIUM) düşüş OLMAMALI.")
    print(f"  giriş/hücre ~{off[CELLS[0][0]]['ent']} · Süre: {time.time()-t0:.0f}s")
