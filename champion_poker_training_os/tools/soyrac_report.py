"""Soyrac KAPSAMLI rapor: (1) cok-masa MTT degisik boyutlar + cash basari,
(2) accuracy tablosu — street/pozisyon/senaryo(pot-tipi)/stack bazli GTO + ICM
dogru-oynama orani. Memory: varsayma, oynat + olc."""
from __future__ import annotations
import copy, random
from collections import defaultdict

import app.engine.bot_brain as BB
import app.engine.game_loop as GL
import app.simulator.headless_mtt as H
from app.engine.bot_brain import BOT_ARCHETYPES, archetype_skill
from app.simulator.mtt_field import itm_places
from app.poker.gto_ranges import get_action
from app.poker.mtt_ranges import get_ranked_hands
from app.poker.soyrac_advisor import soyrac_advice
from tools.soyrac_bot_sim import SoyracBrain, run_cash

# ── Soyrac'i MTT alanina enjekte et (factory patch, recursion yok) ──
_RealBB = BB.BotBrain
SOY = copy.copy(BOT_ARCHETYPES["GTO Expert"]); SOY.name = "Soyrac"
BOT_ARCHETYPES["Soyrac"] = SOY
def _factory(profile, *a, **k):
    return SoyracBrain() if profile is SOY else _RealBB(profile, *a, **k)
GL.BotBrain = _factory
H.BotBrain = _factory
_orig_mix = H.realistic_mtt_mix
def _inj_mix(n, rng=None, tier=None):
    f = list(_orig_mix(n, rng=rng, tier=tier))
    for i in range(0, n, 9):           # ~1/9 Soyrac (esit pay)
        f[i] = "Soyrac"
    return f
H.realistic_mtt_mix = _inj_mix


def mtt_block(field, seeds):
    agg = defaultdict(lambda: {"ent": 0, "itm": 0, "win": 0, "top3": 0, "pct": 0.0})
    paid = itm_places(field)
    for s in range(seeds):
        r = H.run_mtt(field, seed=7000 + s)
        order = r["finish_1st_to_last"]; n = len(order)
        for rank, arch in enumerate(order, 1):
            a = agg[arch]; a["ent"] += 1; a["pct"] += (rank - 1) / max(n - 1, 1)
            if rank <= paid: a["itm"] += 1
            if rank == 1: a["win"] += 1
            if rank <= 3: a["top3"] += 1
    out = {}
    for arch, a in agg.items():
        e = a["ent"] or 1
        out[arch] = {"ent": a["ent"], "itm": round(100*a["itm"]/e, 1),
                     "win": a["win"], "avgfin": round(100*a["pct"]/e, 1)}
    return paid, out


def accuracy_table():
    """SHCP kararini get_action GTO argmax'i ile karsilastir — street=preflop
    (cok-katmanli), senaryo=pot-tipi, pozisyon, stack. + ICM dogrulugu."""
    hands = get_ranked_hands()
    POS_RFI = ["UTG", "MP", "CO", "BTN", "SB"]
    VS = [("BB", "CO"), ("BTN", "CO"), ("SB", "BTN")]
    res = {"by_pos": defaultdict(lambda: [0, 0]), "by_scn": defaultdict(lambda: [0, 0]),
           "by_stack": defaultdict(lambda: [0, 0]), "overall": [0, 0], "icm": [0, 0]}

    def gto_act(pos, hk, scn, stk, vs=None):
        a = get_action(pos, hk, scenario=scn, stack_depth=stk, mode="cash", vs_position=vs)
        r, c, f = a.get("raise", 0), a.get("call", 0), a.get("fold", 0)
        return "R" if r >= max(c, f) else ("C" if c >= f else "F")

    def soy_act(hk, pos, scn, stk, vs=""):
        act = soyrac_advice(hk, pos, scenario=scn, vs_position=vs, stack_bb=stk)["action"]
        if act in ("RAISE (AÇ)", "3-BET", "4-BET", "JAM"): return "R"
        if act == "CALL": return "C"
        return "F"

    for stk in (100, 40):
        for pos in POS_RFI:
            for hk in hands:
                g = gto_act(pos, hk, "RFI", stk); s = soy_act(hk, pos, "RFI", stk)
                ok = int(g == s)
                res["by_pos"][pos][0]+=ok; res["by_pos"][pos][1]+=1
                res["by_scn"]["RFI (açış)"][0]+=ok; res["by_scn"]["RFI (açış)"][1]+=1
                res["by_stack"][f"{stk}bb"][0]+=ok; res["by_stack"][f"{stk}bb"][1]+=1
                res["overall"][0]+=ok; res["overall"][1]+=1
        for pos, opener in VS:
            for hk in hands:
                g = gto_act(pos, hk, "vs RFI", stk, opener); s = soy_act(hk, pos, "vs RFI", stk, opener)
                ok = int(g == s)
                res["by_pos"][pos][0]+=ok; res["by_pos"][pos][1]+=1
                res["by_scn"]["vs RFI (SRP pot)"][0]+=ok; res["by_scn"]["vs RFI (SRP pot)"][1]+=1
                res["by_stack"][f"{stk}bb"][0]+=ok; res["by_stack"][f"{stk}bb"][1]+=1
                res["overall"][0]+=ok; res["overall"][1]+=1
        # vs 3-bet (3BP pot) — B4 blocker ekseni
        for pos in ("BTN", "CO", "MP"):
            for hk in hands:
                g = gto_act(pos, hk, "vs 3-bet", stk, "BB"); s = soy_act(hk, pos, "vs 3-bet", stk, "BB")
                ok = int(g == s)
                res["by_scn"]["vs 3-bet (3BP pot)"][0]+=ok; res["by_scn"]["vs 3-bet (3BP pot)"][1]+=1
                res["overall_3bet"] = res.get("overall_3bet", [0,0])
    # ICM: bubble eşiği (+1) GTO icm_tighten ile uyumlu mu (RFI)
    from app.poker.icm import icm_tighten
    for pos in POS_RFI:
        for hk in hands:
            base = get_action(pos, hk, "RFI", 100, "cash")
            t = icm_tighten(base, 0.10)
            gr, gc, gf = t.get("raise", 0), t.get("call", 0), t.get("fold", 0)
            g = "R" if gr >= max(gc, gf) else ("C" if gc >= gf else "F")
            act = soyrac_advice(hk, pos, "RFI", stack_bb=100, icm=True)["action"]
            s = "R" if act in ("RAISE (AÇ)","JAM") else ("C" if act=="CALL" else "F")
            res["icm"][0]+=int(g==s); res["icm"][1]+=1
    return res


def pct(pair): return round(100*pair[0]/max(pair[1],1), 1)

if __name__ == "__main__":
    import time
    t0 = time.time()
    print("=== ÇOK-MASA MTT (Soyrac ~1/9 esit pay, degisik boyutlar) ===", flush=True)
    for field, seeds in [(18, 6), (45, 4), (90, 3)]:
        paid, out = mtt_block(field, seeds)
        so = out.get("Soyrac", {})
        # Soyrac'i skill-tier ortalamalariyla kiyasla
        strong = [v for a, v in out.items() if archetype_skill(a) == "strong" and a != "Soyrac"]
        s_itm = round(sum(v["itm"] for v in strong)/max(len(strong),1), 1)
        print(f"  {field:>3} kisi ({seeds} sim, paid top {paid}): Soyrac ITM {so.get('itm')}% "
              f"win {so.get('win')} avgFin {so.get('avgfin')}% (n={so.get('ent')}) | strong-tier ort ITM {s_itm}%", flush=True)
    print("\n=== CASH (6-max, 5 masa × 400 el) ===", flush=True)
    cagg = defaultdict(list)
    for s in range(5):
        r = run_cash(["GTO Expert","Solver Bot","ICM Expert","Fish","Calling Station"], 400, seed=900+s)
        for k, v in r.items(): cagg[k].append(v)
    for nm in ["Soyrac","GTO Expert","Solver Bot","ICM Expert","Fish","Calling Station"]:
        print(f"  {nm:<16} {sum(cagg[nm])/len(cagg[nm]):+.1f} bb/100", flush=True)
    print(f"\n  (MTT+cash {time.time()-t0:.0f}s)\n", flush=True)
    print("=== ACCURACY TABLOSU — SHCP vs gerçek GTO motoru (get_action argmax) ===", flush=True)
    a = accuracy_table()
    print(f"\n  GENEL GTO DOĞRULUK: {pct(a['overall'])}%  ·  ICM DOĞRULUK (bubble): {pct(a['icm'])}%")
    print("\n  POZİSYON bazlı:")
    for p in ["UTG","MP","CO","BTN","SB","BB"]:
        if p in a["by_pos"]: print(f"    {p:<4} {pct(a['by_pos'][p])}%")
    print("\n  SENARYO/POT-TİPİ bazlı:")
    for scn in ["RFI (açış)","vs RFI (SRP pot)","vs 3-bet (3BP pot)"]:
        if scn in a["by_scn"]: print(f"    {scn:<20} {pct(a['by_scn'][scn])}%")
    print("\n  STACK bazlı:")
    for st in ["100bb","40bb"]:
        if st in a["by_stack"]: print(f"    {st:<6} {pct(a['by_stack'][st])}%")
    print(f"\nDONE {time.time()-t0:.0f}s")
