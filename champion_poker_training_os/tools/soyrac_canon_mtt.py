"""Soyrac'ı KANONIK MTT (profile_sim.run_mtt_block) + cash-9max + MTT-6max'a
enjekte → apples-to-apples per-format sıra. run_mtt POZISYON-FIX'li (_play_fixed)."""
from __future__ import annotations
import copy, sys
import app.engine.bot_brain as BB
import app.engine.bot_brain as BBmod
import app.engine.game_loop as GL
import app.simulator.headless_mtt as H
import tools.profile_sim as PS
from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.game_loop import PokerGame
from tools.soyrac_bot_sim import SoyracBrain

_RealBB = BB.BotBrain
SOY = copy.copy(BOT_ARCHETYPES["GTO Expert"]); SOY.name = "Soyrac"
BOT_ARCHETYPES["Soyrac"] = SOY
def _factory(profile, *a, **k):
    return SoyracBrain() if profile is SOY else _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory
PS.ARCHS = PS.ARCHS + ["Soyrac"]
_os = BBmod.archetype_skill
def _skill(a): return "strong" if a == "Soyrac" else _os(a)
BBmod.archetype_skill = _skill; PS.archetype_skill = _skill; H.archetype_skill = _skill

# run_mtt POZISYON-FIX (hand_count hile → buton döner)
def _play_fixed(table, sb, bb, ante, button, icm=0.0):
    n = len(table)
    if n < 2: return
    archs = [p.arch for p in table]
    gl = PokerGame(num_players=n, starting_stack=H._START_CHIPS, small_blind=sb,
                   big_blind=bb, ante=ante, hero_seat=0, bot_archetypes=archs[1:],
                   player_names=[f"p{p.pid}" for p in table[1:]], paced_bots=True)
    for i, p in enumerate(table): gl.players[i].stack = p.stack
    gl.hand_count = 2; gl.dealer_idx = (button - 1) % n
    hb = H.BotBrain(BOT_ARCHETYPES.get(archs[0], BOT_ARCHETYPES["Balanced Reg"]))
    hb.tournament_mode = True
    for b in gl.bots.values(): b.tournament_mode = True
    if icm > 0:
        hb.icm_pressure = icm
        for b in gl.bots.values(): b.icm_pressure = icm
    gl.start_hand(); guard = 0
    while guard < 600:
        guard += 1; h = gl.current_hand
        if h and h.is_complete: break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            hh = gl.current_hand; at, amt = hb.decide(hh, hh.hero_idx); gl.hero_act(at, amt)
        elif not prog: break
    for i, p in enumerate(table): p.stack = max(0.0, gl.players[i].stack)
H._play_one_hand = _play_fixed

if __name__ == "__main__":
    import time; t0 = time.time()
    mode = sys.argv[1] if len(sys.argv) > 1 else "mtt9"
    if mode == "mtt9":
        print("=== KANONIK MTT-9max + Soyrac · 100 kişi × 25 turnuva × 100bb ===", flush=True)
        H._TABLE_MAX = 9
        res = PS.run_mtt_block(100, 25, 100)
    elif mode == "mtt6":
        print("=== MTT-6max + Soyrac · 100 kişi × 25 turnuva × 100bb ===", flush=True)
        H._TABLE_MAX = 6
        res = PS.run_mtt_block(100, 25, 100)
    elif mode == "cash9":
        print("=== CASH-9max + Soyrac · 400 masa × 250 el ===", flush=True)
        # run_cash 6-max hardcoded; 9-max icin num_players=9 patch
        import tools.profile_sim as P
        _orig = P.PokerGame
        res = None
        # basit: run_cash'i 9-max'e cevir (gecici)
        src = P.run_cash
        # monkeypatch: num_players=9, _draw6->_draw9
        print("(cash9 ayri ele alinacak)"); res = {"rows": {}}
    rows = res["rows"]
    if mode.startswith("mtt"):
        board = sorted(rows.items(), key=lambda x: (x[1]["avg_fin_pct"]))
        print(f"\n  {mode} LEADERBOARD (avg_fin_pct düşük=iyi · ITM% · win):")
        print(f"  {'#':>3} {'ARKETİP':<18}{'tier':<7}{'avgF':>7}{'ITM%':>7}{'win':>5}")
        for i, (a, d) in enumerate(board, 1):
            mark = "  ◀" if a == "Soyrac" else ""
            print(f"  {i:>3} {a:<18}{d['skill']:<7}{d['avg_fin_pct']:>7}{d['itm_pct']:>7}{d['win']:>5}{mark}")
        sr = next(i for i, (a, _) in enumerate(board, 1) if a == "Soyrac")
        print(f"\n  → Soyrac sırası: {sr}/{len(board)}")
    print(f"DONE {time.time()-t0:.0f}s")
