"""5×200 + 5×1000 GERÇEK turnuva simülasyonu → arketip performans analizi.
Memory kuralı: sonucu varsayma, gerçekten oynat (run_mtt = real BotBrain), ölç.
"""
import os, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from collections import defaultdict
from app.simulator.headless_mtt import run_mtt
from app.engine.bot_brain import archetype_skill
from app.simulator.mtt_field import itm_places


def aggregate(field_size, seeds):
    # per-arch: entrants, itm, top3, wins(1st), sum finish-percentile(0=best,1=last)
    agg = defaultdict(lambda: {"n": 0, "itm": 0, "top3": 0, "win": 0, "pctsum": 0.0})
    paid = itm_places(field_size)
    total_hands = 0
    t0 = time.time()
    for s in seeds:
        r = run_mtt(field_size, seed=s)
        order = r["finish_1st_to_last"]   # [1st, 2nd, ... last]
        total_hands += r["hands"]
        n = len(order)
        for place, arch in enumerate(order, start=1):
            a = agg[arch]
            a["n"] += 1
            a["pctsum"] += (place - 1) / max(1, n - 1)
            if place <= paid:
                a["itm"] += 1
            if place <= 3:
                a["top3"] += 1
            if place == 1:
                a["win"] += 1
    elapsed = time.time() - t0
    field_itm = paid / field_size
    rows = []
    for arch, a in agg.items():
        n = a["n"]
        itm_rate = a["itm"] / n
        rows.append({
            "arch": arch, "skill": archetype_skill(arch), "entrants": n,
            "itm_rate": round(100 * itm_rate, 1),
            "itm_edge": round(itm_rate / field_itm, 2),   # >1 over-performs
            "top3": a["top3"], "wins": a["win"],
            "avg_finish_pct": round(100 * a["pctsum"] / n, 1),  # düşük=iyi
        })
    rows.sort(key=lambda r: r["avg_finish_pct"])   # en iyi finiş üstte
    return {"field": field_size, "paid": paid, "field_itm": round(100*field_itm,1),
            "hands": total_hands, "elapsed": round(elapsed, 1), "rows": rows}


def skill_rollup(rows):
    by = defaultdict(lambda: {"n": 0, "itm": 0.0, "fin": 0.0})
    for r in rows:
        b = by[r["skill"]]
        b["n"] += r["entrants"]
        b["itm"] += r["itm_rate"] * r["entrants"]
        b["fin"] += r["avg_finish_pct"] * r["entrants"]
    return {k: {"entrants": v["n"], "itm_rate": round(v["itm"]/v["n"], 1),
                "avg_finish_pct": round(v["fin"]/v["n"], 1)}
            for k, v in by.items()}


N_SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
out = {}
for fs in (200, 1000):
    res = aggregate(fs, seeds=list(range(1, N_SEEDS + 1)))
    res["skill_rollup"] = skill_rollup(res["rows"])
    out[str(fs)] = res
    print(f"=== {fs}p × 5 ({res['elapsed']}s, {res['hands']} hands) "
          f"paid top {res['paid']} (field ITM {res['field_itm']}%) ===")
    print(f"  skill rollup: {json.dumps(res['skill_rollup'], ensure_ascii=False)}")
    print("  arch                  skill  ent  ITM%  edge  top3 win  avgFin%")
    for r in res["rows"]:
        print(f"  {r['arch']:<20} {r['skill']:<6} {r['entrants']:>4} "
              f"{r['itm_rate']:>5} {r['itm_edge']:>5} {r['top3']:>4} {r['wins']:>3} "
              f"{r['avg_finish_pct']:>7}")

with open("/tmp/sim_results.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("SAVED /tmp/sim_results.json")
