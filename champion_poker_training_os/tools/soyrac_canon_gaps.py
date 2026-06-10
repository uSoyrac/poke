"""Eksik 2 kadran: cash-9max + MTT-6max kanonik leaderboard + Soyrac enjekte.
Pozisyon-doğru. Memory: varsayma, oynat."""
from __future__ import annotations
import copy, sys, random
from collections import defaultdict
import app.engine.bot_brain as BB
import app.engine.bot_brain as BBmod
import app.engine.game_loop as GL
import app.simulator.headless_mtt as H
import tools.profile_sim as PS
from app.engine.bot_brain import BOT_ARCHETYPES, archetype_skill as _os
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from tools.soyrac_bot_sim import SoyracBrain

_RealBB = BB.BotBrain
SOY = copy.copy(BOT_ARCHETYPES["GTO Expert"]); SOY.name = "Soyrac"
BOT_ARCHETYPES["Soyrac"] = SOY
def _factory(profile, *a, **k):
    return SoyracBrain() if profile is SOY else _RealBB(profile, *a, **k)
GL.BotBrain = _factory; PS.BotBrain = _factory; H.BotBrain = _factory
def _skill(a): return "strong" if a == "Soyrac" else _os(a)
BBmod.archetype_skill = _skill; PS.archetype_skill = _skill; H.archetype_skill = _skill
ARCHS = PS.ARCHS + ["Soyrac"]
PS.ARCHS = ARCHS

# MTT pozisyon-fix
def _play_fixed(table, sb, bb, ante, button, icm=0.0):
    n = len(table)
    if n < 2: return
    archs = [p.arch for p in table]
    gl = PokerGame(num_players=n, starting_stack=H._START_CHIPS, small_blind=sb, big_blind=bb,
                   ante=ante, hero_seat=0, bot_archetypes=archs[1:],
                   player_names=[f"p{p.pid}" for p in table[1:]], paced_bots=True)
    for i, p in enumerate(table): gl.players[i].stack = p.stack
    gl.hand_count = 2; gl.dealer_idx = (button - 1) % n
    hb = H.BotBrain(BOT_ARCHETYPES.get(archs[0], BOT_ARCHETYPES["Balanced Reg"])); hb.tournament_mode = True
    for b in gl.bots.values(): b.tournament_mode = True
    if icm > 0:
        hb.icm_pressure = icm
        for b in gl.bots.values(): b.icm_pressure = icm
    gl.start_hand(); g = 0
    while g < 600:
        g += 1; h = gl.current_hand
        if h and h.is_complete: break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            hh = gl.current_hand; at, amt = hb.decide(hh, hh.hero_idx); gl.hero_act(at, amt)
        elif not prog: break
    for i, p in enumerate(table): p.stack = max(0.0, gl.players[i].stack)
H._play_one_hand = _play_fixed
PS.archetype_skill = _skill

def cash9(n_tables=500, hands_per=250):
    rng = random.Random(7); net = defaultdict(float); seen = defaultdict(int)
    SB, BB_, stack = 0.5, 1.0, 100.0
    pool = []
    def draw9():
        nonlocal pool
        while len(pool) < 9:
            e = ARCHS[:]; rng.shuffle(e); pool += e
        s, pool = pool[:9], pool[9:]; return s
    for t in range(n_tables):
        seats = draw9()
        game = PokerGame(num_players=9, starting_stack=stack, small_blind=SB, big_blind=BB_,
                         hero_seat=0, bot_archetypes=seats[1:], paced_bots=False)
        hero = PS.BotBrain(BOT_ARCHETYPES.get(seats[0], BOT_ARCHETYPES["Balanced Reg"]))
        for h in range(hands_per):
            for p in game.players: p.stack = stack; p.is_eliminated = False
            game.start_hand(); guard = 0
            while game.current_hand and not game.current_hand.is_complete and guard < 400:
                if game.is_waiting_for_hero:
                    try: act, amt = hero.decide(game.current_hand, game.hero_seat); game.hero_act(act, amt)
                    except Exception: game.hero_act(ActionType.FOLD, 0)
                else: game.step_action()
                guard += 1
            for i, p in enumerate(game.players):
                net[seats[i]] += p.stack - stack; seen[seats[i]] += 1
    return {a: {"bb": round(100 * net[a] / max(seen[a], 1), 1), "h": seen[a], "sk": _skill(a)} for a in ARCHS}

if __name__ == "__main__":
    import time; t0 = time.time()
    mode = sys.argv[1] if len(sys.argv) > 1 else "cash9"
    if mode == "cash9":
        print(f"=== CASH-9max + Soyrac · 500 masa × 250 el ===", flush=True)
        rows = cash9(500, 250)
        board = sorted(rows.items(), key=lambda x: -x[1]["bb"])
        print(f"  {'#':>3} {'ARKETİP':<18}{'tier':<7}{'bb/100':>9}")
        for i, (a, d) in enumerate(board, 1):
            m = "  ◀ SOYRAC" if a == "Soyrac" else ""
            print(f"  {i:>3} {a:<18}{d['sk']:<7}{d['bb']:>+9.1f}{m}")
        sr = next(i for i, (a, _) in enumerate(board, 1) if a == "Soyrac")
        print(f"\n  → Soyrac cash-9max sırası: {sr}/{len(board)}")
    elif mode == "mtt6":
        print(f"=== MTT-6max + Soyrac · 100 kişi × 25 turnuva ===", flush=True)
        H._TABLE_MAX = 6
        res = PS.run_mtt_block(100, 25, 100); rows = res["rows"]
        board = sorted(rows.items(), key=lambda x: x[1]["avg_fin_pct"])
        print(f"  {'#':>3} {'ARKETİP':<18}{'tier':<7}{'avgF':>7}{'ITM%':>7}{'win':>5}")
        for i, (a, d) in enumerate(board, 1):
            m = "  ◀" if a == "Soyrac" else ""
            print(f"  {i:>3} {a:<18}{d['skill']:<7}{d['avg_fin_pct']:>7}{d['itm_pct']:>7}{d['win']:>5}{m}")
        sr = next(i for i, (a, _) in enumerate(board, 1) if a == "Soyrac")
        print(f"\n  → Soyrac MTT-6max sırası: {sr}/{len(board)}")
    print(f"DONE {time.time()-t0:.0f}s")
