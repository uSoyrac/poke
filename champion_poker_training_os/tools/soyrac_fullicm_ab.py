"""A/B: ICM-ORANTILI dereceli eşik (full_icm, D231) MTT'de kitabı daha sadık oynatıp
laddering'i (ITM/ROI) artırıyor mu? OFF = mevcut ikili +1 · ON = bubble'da +2 (orantılı).
Paired (aynı seed). KURAL: kazanmazsa (veya ROI/win'i bozarsa) GERİ AL.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_fullicm_ab.py [seeds_mult]
"""
from __future__ import annotations
import sys, time
import tools.soyrac_realistic_mtt as R
import app.engine.game_loop as GL
import tools.profile_sim as PS
import app.simulator.headless_mtt as H
from tools.soyrac_bot_sim import SoyracBrain

SOY = R.SOY
_RealBB = R._RealBB
_F = {"on": False}


def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain(); b.pure_book = True; b.full_icm = _F["on"]; return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory

CELLS = [
    ("Düşük · 200 · 100bb",  "Düşük ($11-33)", 200, 100, 30),
    ("Mikro · 500 · 50bb",   "Mikro ($1-5)",   500, 50,  12),
]

if __name__ == "__main__":
    t0 = time.time()
    print("\nICM-ORANTILI eşik A/B (full_icm) · paired · OFF=ikili+1 / ON=orantılı+2\n")
    print(f"  {'HÜCRE':<22}{'ITM% OFF→ON':>16}{'ROI% OFF→ON':>18}{'WIN':>8}{'FT% OFF→ON':>16}")
    for label, tier, field, depth, seeds in CELLS:
        _F["on"] = False
        a = R.run_cell(field, tier, depth, seeds, base_seed=7000)
        _F["on"] = True
        b = R.run_cell(field, tier, depth, seeds, base_seed=7000)
        c_itm = "%.1f->%.1f (%+.1f)" % (a["itm"], b["itm"], b["itm"] - a["itm"])
        c_roi = "%+.0f->%+.0f (%+.0f)" % (a["roi"], b["roi"], b["roi"] - a["roi"])
        c_win = "%d->%d" % (a["win"], b["win"])
        c_ft = "%.1f->%.1f" % (a["ft"], b["ft"])
        print("  %-22s%16s%18s%8s%16s" % (label, c_itm, c_roi, c_win, c_ft), flush=True)
    print("\n  ITM% ↑ + ROI% korunur/↑ + WIN düşmez → KAZANÇ (kitap-sadık + iyi). Aksi → geri al.")
    print(f"  Süre: {time.time()-t0:.0f}s")
