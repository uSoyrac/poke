"""Soyrac'ı KANONIK harness'a (profile_sim) enjekte → apples-to-apples sıra.
Pozisyon-doğru (tek-kalıcı oyun). Memory: varsayma, oynat + ölç."""
from __future__ import annotations
import copy, sys
import app.engine.bot_brain as BB
import app.engine.game_loop as GL
import app.engine.bot_brain as BBmod
import tools.profile_sim as PS
from app.engine.bot_brain import BOT_ARCHETYPES
from tools.soyrac_bot_sim import SoyracBrain

_RealBB = BB.BotBrain
SOY = copy.copy(BOT_ARCHETYPES["GTO Expert"]); SOY.name = "Soyrac"
BOT_ARCHETYPES["Soyrac"] = SOY
def _factory(profile, *a, **k):
    if profile is SOY:
        b = SoyracBrain()
        b.tournament_mode = False      # CASH = SHCP (chip-EV); harness default True'ydu
        return b
    return _RealBB(profile, *a, **k)
GL.BotBrain = _factory
PS.BotBrain = _factory                       # run_cash hero_brain
PS.ARCHS = PS.ARCHS + ["Soyrac"]             # havuza ekle
_origskill = BBmod.archetype_skill
def _skill(a):
    return "strong" if a == "Soyrac" else _origskill(a)
BBmod.archetype_skill = _skill
PS.archetype_skill = _skill

if __name__ == "__main__":
    import time; t0 = time.time()
    NT = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    print(f"=== KANONIK CASH-6max + Soyrac (28. arketip) · {NT} masa × 250 el ===", flush=True)
    res = PS.run_cash(n_tables=NT, hands_per=250, depth_bb=100)
    rows = res["rows"]
    board = sorted(rows.items(), key=lambda x: -x[1]["bb_per_100"])
    print(f"\n  CASH-6max LEADERBOARD (bb/100, {NT} masa):")
    print(f"  {'#':>3} {'ARKETİP':<18}{'tier':<8}{'bb/100':>9}{'el':>8}")
    for i, (a, d) in enumerate(board, 1):
        mark = "  ◀ SOYRAC" if a == "Soyrac" else ""
        print(f"  {i:>3} {a:<18}{d['skill']:<8}{d['bb_per_100']:>+9.1f}{d['hands']:>8}{mark}")
    srank = next(i for i, (a, _) in enumerate(board, 1) if a == "Soyrac")
    print(f"\n  → Soyrac sırası: {srank}/{len(board)}")
    print(f"DONE {time.time()-t0:.0f}s")
