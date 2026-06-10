"""Çok-masa MTT testi — TEK Soyrac, 6-max, 90bb start, büyük alan. Kaç kere
final/top3/win? Pozisyon-bug FIX'li (hand_count hile), custom saha (yarı-expert
veya full-expert). Memory: varsayma, oynat + ölç."""
from __future__ import annotations
import copy, random
from collections import defaultdict
import app.engine.bot_brain as BB
import app.engine.game_loop as GL
import app.simulator.headless_mtt as H
from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from tools.soyrac_bot_sim import SoyracBrain

# ── Soyrac brain factory (recursion yok: SoyracBrain içi gerçek BotBrain) ──
_RealBB = BB.BotBrain
SOY = copy.copy(BOT_ARCHETYPES["GTO Expert"]); SOY.name = "Soyrac"
BOT_ARCHETYPES["Soyrac"] = SOY
def _factory(profile, *a, **k):
    return SoyracBrain() if profile is SOY else _RealBB(profile, *a, **k)
GL.BotBrain = _factory
H.BotBrain = _factory

# ── pozisyon-FIX'li _play_one_hand (hand_count hile → buton döner) ──
def _play_fixed(table, sb, bb, ante, button, icm=0.0):
    n = len(table)
    if n < 2:
        return
    archs = [p.arch for p in table]
    gl = PokerGame(num_players=n, starting_stack=H._START_CHIPS, small_blind=sb,
                   big_blind=bb, ante=ante, hero_seat=0, bot_archetypes=archs[1:],
                   player_names=[f"p{p.pid}" for p in table[1:]], paced_bots=True)
    for i, p in enumerate(table):
        gl.players[i].stack = p.stack
    gl.hand_count = 2                      # FIX: hand_count>1 → _advance_dealer döndürür
    gl.dealer_idx = (button - 1) % n       # advance sonrası = button
    hero_brain = H.BotBrain(BOT_ARCHETYPES.get(archs[0], BOT_ARCHETYPES["Balanced Reg"]))
    hero_brain.tournament_mode = True
    for b in gl.bots.values():
        b.tournament_mode = True
    if icm > 0:
        hero_brain.icm_pressure = icm
        for b in gl.bots.values():
            b.icm_pressure = icm
    gl.start_hand()
    guard = 0
    while guard < 600:
        guard += 1
        h = gl.current_hand
        if h and h.is_complete:
            break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            hh = gl.current_hand
            at, amt = hero_brain.decide(hh, hh.hero_idx)
            gl.hero_act(at, amt)
        elif not prog:
            break
    for i, p in enumerate(table):
        p.stack = max(0.0, gl.players[i].stack)
H._play_one_hand = _play_fixed
H._TABLE_MAX = 6                            # 6-max masalar
H._START_CHIPS = 4500                       # 90bb @ 25/50 ilk level

# ── custom saha enjeksiyonu (1 Soyrac + kompozisyon) ──
STRONG = ["GTO Expert","Solver Bot","ICM Expert","Shark","Phil Ivey",
          "Doyle Brunson","Daniel Negreanu","Exploit Expert","Phil Hellmuth"]
MID    = ["TAG","LAG","Reg","Balanced Reg","Weak Reg"]
WEAK   = ["Fish","Calling Station","Loose Rec","Aggro Fish","Nit","Rock","Maniac","Tight Passive"]
_FIELD = []
def _inj_mix(n, rng=None, tier=None):
    return list(_FIELD)
H.realistic_mtt_mix = _inj_mix

def build_field(fsize, comp, rng):
    f = ["Soyrac"]
    if comp == "full":
        pool = STRONG
        f += [rng.choice(pool) for _ in range(fsize - 1)]
    else:  # yarı-expert / yarı orta-acemi: %50 strong, %25 mid, %25 weak
        for _ in range(fsize - 1):
            r = rng.random()
            f += [rng.choice(STRONG if r < 0.5 else MID if r < 0.75 else WEAK)]
    rng.shuffle(f)
    return f

def run_block(fsize, comp, n_tourneys, base_seed=0):
    global _FIELD
    import time
    places = []
    t0 = time.time()
    for s in range(n_tourneys):
        rng = random.Random(base_seed + s * 7919)
        _FIELD = build_field(fsize, comp, rng)
        r = H.run_mtt(fsize, seed=base_seed + s)
        order = r["finish_1st_to_last"]
        place = order.index("Soyrac") + 1 if "Soyrac" in order else fsize
        places.append(place)
        if (s + 1) % 5 == 0:
            ft = sum(1 for p in places if p <= min(6, fsize))
            print(f"      [{comp}] {s+1}/{n_tourneys} · FT {ft} · ort {sum(places)/len(places):.0f} · {time.time()-t0:.0f}s", flush=True)
    return places

if __name__ == "__main__":
    import time, sys
    t0 = time.time()
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    FSIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    print(f"=== ÇOK-MASA MTT · 6-max · 90bb · alan {FSIZE} kişi · {N} turnuva ===", flush=True)
    base = 6 if FSIZE >= 9 else FSIZE       # final masa = son min(6,alan)
    for comp, tag in [("half", "Yarı-expert / yarı orta-acemi"), ("full", "Full-expert")]:
        pls = run_block(FSIZE, comp, N, base_seed=1000)
        ft = sum(1 for p in pls if p <= base)
        t3 = sum(1 for p in pls if p <= 3)
        win = sum(1 for p in pls if p == 1)
        itm = sum(1 for p in pls if p <= max(1, int(FSIZE * 0.15)))  # ~ITM %15
        print(f"\n  [{tag}] {N} turnuva, alan {FSIZE}:")
        print(f"    ITM (~%15 = top{max(1,int(FSIZE*0.15))}) : {itm}/{N}  (%{100*itm/N:.0f})")
        print(f"    Final masa (top {base})    : {ft}/{N}  (%{100*ft/N:.1f})")
        print(f"    Top 3                      : {t3}/{N}  (%{100*t3/N:.1f})")
        print(f"    Şampiyon (1.)              : {win}/{N}")
        print(f"    Ortalama bitiş yeri        : {sum(pls)/len(pls):.0f}. / {FSIZE}", flush=True)
    print(f"\nDONE {time.time()-t0:.0f}s")
