"""GTO ADVICE INVARIANT SWEEP — bütün (pozisyon × senaryo × stack × mod)
uzayını gezip SAĞLAM poker gerçeklerine karşı denetler. Tek tek screenshot'la
bug aramak yerine bütün sınıfı tek seferde yakalar.

Çalıştır:  .venv/bin/python tools/advice_sweep.py
Çıktı: ihlal listesi (tip · spot · detay). 0 ihlal = temiz yüzey.
"""
from __future__ import annotations
import sys
from app.poker.mtt_ranges import get_ranked_hands
from app.poker.gto_ranges import get_action

HANDS = get_ranked_hands()
POS_OPEN = ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB"]   # BB ayrı (iso)
STACKS = [20, 30, 40, 60, 87, 100, 150]
MODES = ["cash", "MTT"]
# vs RFI için temsili açan (defender -> opener)
VS_OPENER = {"BB": "CO", "SB": "BTN", "BTN": "CO", "CO": "MP", "HJ": "MP",
             "LJ": "UTG", "MP": "UTG", "UTG+1": "UTG"}

violations: list[tuple[str, str, str]] = []
def flag(kind, spot, detail): violations.append((kind, spot, detail))

def grid(pos, scen, stack, mode, vs=None):
    out = {}
    for hk in HANDS:
        try:
            out[hk] = get_action(pos, hk, scenario=scen, stack_depth=stack,
                                 mode=mode, vs_position=vs)
        except Exception as e:
            out[hk] = {"raise": 0, "call": 0, "fold": 100}
            flag("EXCEPTION", f"{pos} {scen} {stack}bb {mode}", f"{hk}: {e}")
    return out

def n_raise(g, thr=90): return sum(1 for a in g.values() if a.get("raise", 0) >= thr)
def n_play(g):  # raise veya call ile oynanan
    return sum(1 for a in g.values()
               if a.get("raise", 0) >= 50 or a.get("call", 0) >= 50)

# ── INVARIANT taraması ────────────────────────────────────────────────
for mode in MODES:
    for stack in STACKS:
        for pos in POS_OPEN + ["BB"]:
            scen = "RFI"
            vs = None
            g = grid(pos, scen, stack, mode, vs)
            spot = f"{pos} {scen} {stack}bb {mode}"
            nr = n_raise(g)
            # INV1: ALL-RED — hiçbir grid ~%100 pure-raise olmamalı
            if nr >= 152:  # 169'un %90'ı
                flag("ALL_RAISE", spot, f"{nr}/169 hücre pure-raise (>=90%)")
            # INV2: ALL-FOLD — gerçek karar spotunda hiç oynanan el yok
            if stack > 15 and n_play(g) == 0:
                flag("ALL_FOLD", spot, "hiçbir el raise/call değil")
            # INV3: PREMIUM FOLD — AA/KK açışta fold etmemeli
            for prem in ("AA", "KK"):
                if g[prem].get("fold", 0) >= 50:
                    flag("PREMIUM_FOLD", spot, f"{prem} fold={g[prem].get('fold',0)}")
            # INV4: TRASH RAISE — erken/orta pozisyon RFI'da 72o/32o pure-raise olmamalı
            if pos in ("UTG", "UTG+1", "MP", "LJ", "HJ", "CO"):
                for trash in ("72o", "32o", "82o", "62o"):
                    if g[trash].get("raise", 0) >= 90:
                        flag("TRASH_RAISE", spot, f"{trash} raise={g[trash].get('raise',0)}")

        # INV5: MONOTONIC — UTG açış genişliği <= CO <= BTN (aynı stack/mod)
        gu = grid("UTG", "RFI", stack, mode)
        gc = grid("CO", "RFI", stack, mode)
        gb = grid("BTN", "RFI", stack, mode)
        ru, rc, rb = n_raise(gu, 60), n_raise(gc, 60), n_raise(gb, 60)
        if not (ru <= rc + 8):
            flag("NON_MONOTONIC", f"RFI {stack}bb {mode}", f"UTG({ru}) > CO({rc}) açış")
        if not (rc <= rb + 8):
            flag("NON_MONOTONIC", f"RFI {stack}bb {mode}", f"CO({rc}) > BTN({rb}) açış")

        # ── vs RFI (defans) taraması ──
        for pos in ["BB", "SB", "BTN", "CO", "HJ", "MP"]:
            vs = VS_OPENER.get(pos)
            g = grid(pos, "vs RFI", stack, mode, vs)
            spot = f"{pos} vs RFI(opener {vs}) {stack}bb {mode}"
            if n_raise(g) >= 152:
                flag("ALL_RAISE", spot, f"{n_raise(g)}/169 pure-raise")
            if stack > 15 and n_play(g) == 0:
                flag("ALL_FOLD", spot, "hiçbir el defend edilmiyor")
            # AA vs RFI'da fold etmemeli (raise/call olmalı)
            if g["AA"].get("fold", 0) >= 50:
                flag("PREMIUM_FOLD", spot, f"AA fold={g['AA'].get('fold',0)}")

# ── RAPOR ──────────────────────────────────────────────────────────────
from collections import Counter
by_kind = Counter(k for k, _, _ in violations)
print(f"\n{'='*70}\nADVICE SWEEP — {len(violations)} ihlal "
      f"({len(MODES)*len(STACKS)*(len(POS_OPEN)+1)} RFI + vs-RFI spot tarandı)\n{'='*70}")
for kind, cnt in by_kind.most_common():
    print(f"  {kind:<15} {cnt}")
print("-"*70)
for kind, spot, detail in violations[:80]:
    print(f"[{kind}] {spot}\n        {detail}")
if len(violations) > 80:
    print(f"... +{len(violations)-80} daha")
print("="*70)
sys.exit(1 if violations else 0)
