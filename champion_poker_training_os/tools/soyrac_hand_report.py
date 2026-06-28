"""soyrac_hand_logger.json → en-çok-kazanan/kaybeden eller + durum/pozisyon/aşama dağılımları.
Kullanıcı: pozisyon-pozisyon, el-el, aşama-aşama, preflop-bağlam (RFI/vs-RFI call/squeeze/3bet-jam) listele."""
import json
import os
import sys
from collections import defaultdict


def _stage(icm):
    if icm <= 0:
        return "1-early/mid (ICM yok)"
    if icm < 0.4:
        return "2-yaklaşan"
    return "3-bubble/FT"


def main(path):
    d = json.load(open(path))
    n = len(d)
    print(f"=== TOPLAM {n:,} Soyrac-eli (gerçekten oynatıldı) ===\n")

    # ---- EN ÇOK KAZANILAN tekil eller ----
    sw = sorted(d, key=lambda r: -r["profit_bb"])
    print("🏆 EN ÇOK KAZANILAN 15 EL (tekil)")
    print(f"  {'poz':5}{'el':5}{'stack':>7} {'durum':16}{'aşama':20}{'kâr':>9}")
    for r in sw[:15]:
        print(f"  {r['pos']:5}{r['hand']:5}{r['stack_bb']:>6.0f}b {r['sit']:16}{_stage(r['icm']):20}{r['profit_bb']:>+8.1f}bb")
    print("\n💸 EN ÇOK KAYBEDİLEN 15 EL (tekil)")
    print(f"  {'poz':5}{'el':5}{'stack':>7} {'durum':16}{'aşama':20}{'kâr':>9}")
    for r in sw[-15:][::-1]:
        print(f"  {r['pos']:5}{r['hand']:5}{r['stack_bb']:>6.0f}b {r['sit']:16}{_stage(r['icm']):20}{r['profit_bb']:>+8.1f}bb")

    def agg(keyfn, title, top=14):
        net = defaultdict(float); cnt = defaultdict(int)
        for r in d:
            k = keyfn(r); net[k] += r["profit_bb"]; cnt[k] += 1
        rows = sorted(net.items(), key=lambda kv: -kv[1])
        print(f"\n=== {title} (net bb · el-sayısı · bb/el) ===")
        for k, v in rows[:top]:
            c = cnt[k]
            print(f"  {str(k):26} {v:>+9.0f}bb  {c:>6}×  {v/max(c,1):>+6.2f}/el")
        if len(rows) > top:
            print("  ...")
            for k, v in rows[-4:]:
                c = cnt[k]
                print(f"  {str(k):26} {v:>+9.0f}bb  {c:>6}×  {v/max(c,1):>+6.2f}/el")

    # ---- DURUM (preflop bağlam) ----
    agg(lambda r: r["sit"], "PREFLOP DURUMA göre (RFI/vs-RFI call/squeeze/3bet-jam...)", top=18)
    # ---- POZİSYON ----
    agg(lambda r: r["pos"], "POZİSYONA göre")
    # ---- AŞAMA ----
    agg(lambda r: _stage(r["icm"]), "AŞAMAYA göre")
    # ---- EL ----
    agg(lambda r: r["hand"], "EL'e göre (en kârlı/zararlı holdingler)", top=16)
    # ---- ALAN × DERİNLİK ----
    agg(lambda r: f"{r['field']}k·{r['depth']}bb", "ALAN × BAŞLANGIÇ-DERİNLİK")
    # ---- POZİSYON × DURUM (en kârlı kombinasyonlar) ----
    agg(lambda r: f"{r['pos']}·{r['sit']}", "POZİSYON × DURUM (en kârlı/zararlı kombinasyonlar)", top=16)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/soyrac_matrix_log.json")
