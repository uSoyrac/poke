"""Gerçekçi saha (az acemi) testi — Soyrac cash + turnuva + detaylı istatistik.
VPIP/PFR/3bet/AF Soyrac oyuncusu için izlenir. Memory: varsayma, oynat + ölç."""
from __future__ import annotations
import random
from collections import defaultdict
from app.engine.game_loop import PokerGame
from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.hand_state import ActionType, Street
from tools.soyrac_bot_sim import SoyracBrain, run_sng

DEC = []
class StatBrain(SoyracBrain):
    def decide(self, state, idx):
        st = str(state.street).split('.')[-1]
        tc = state.to_call(idx); cb = state.current_bet; bb = max(state.big_blind, 0.01)
        act = super().decide(state, idx)
        DEC.append((st, act[0].name, tc, cb, bb))
        return act

def cash_stats(opps, hands, seed=1):
    random.seed(seed)
    names = ['Soyrac'] + list(opps); n = len(names)
    net = defaultdict(float); A = defaultdict(int)
    sb, bb, stack = 0.5, 1.0, 100.0
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f'a{i}' for i in range(1, n)], paced_bots=True)
    soy = StatBrain()
    for b in gl.bots.values(): b.tournament_mode = True
    for h in range(hands):
        DEC.clear()
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand(); guard = 0
        while guard < 800:
            guard += 1; hh = gl.current_hand
            if hh and hh.is_complete: break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                at, amt = soy.decide(gl.current_hand, gl.current_hand.hero_idx); gl.hero_act(at, amt)
            elif not prog: break
        for i in range(n): net[names[i]] += gl.players[i].stack - stack
        A['hands'] += 1
        pf = [d for d in DEC if d[0] == 'PREFLOP']
        if any(d[1] in ('CALL', 'RAISE', 'BET', 'ALL_IN') for d in pf): A['vpip'] += 1
        if any(d[1] in ('RAISE', 'BET', 'ALL_IN') for d in pf): A['pfr'] += 1
        if any(d[1] in ('RAISE', 'ALL_IN') and d[3] > d[4] + 0.001 for d in pf): A['3bet'] += 1
        post = [d for d in DEC if d[0] in ('FLOP', 'TURN', 'RIVER')]
        if post: A['flop'] += 1
        A['pbets'] += sum(1 for d in post if d[1] in ('BET', 'RAISE', 'ALL_IN'))
        A['pcalls'] += sum(1 for d in post if d[1] == 'CALL')
    return names, net, A

if __name__ == "__main__":
    import time; t0 = time.time()
    HANDS = 20000
    print("=" * 60)
    print("CASH — gerçekçi 6-max saha (2 güçlü + 2 reg + 1 balık)")
    print("Soyrac + GTO Expert, Solver Bot, TAG, Balanced Reg, Fish")
    print(f"{HANDS} el · seed 1")
    print("=" * 60, flush=True)
    opps = ["GTO Expert", "Solver Bot", "TAG", "Balanced Reg", "Fish"]
    names, net, A = cash_stats(opps, HANDS, seed=1)
    h = A['hands']
    print(f"\n  bb/100 (kazanç):")
    for nm in names:
        print(f"    {nm:<16} {100*net[nm]/h:+7.1f}")
    af = A['pbets'] / max(A['pcalls'], 1)
    print(f"\n  ── SOYRAC OYUNCU İSTATİSTİKLERİ ({h} el) ──")
    print(f"    VPIP (gönüllü pota giriş)  : %{100*A['vpip']/h:.1f}")
    print(f"    PFR  (preflop raise)       : %{100*A['pfr']/h:.1f}")
    print(f"    3-bet                      : %{100*A['3bet']/h:.1f}")
    print(f"    Flop görme                 : %{100*A['flop']/h:.1f}")
    print(f"    Postflop AF (bet+raise/call): {af:.2f}")
    print(f"    Kazanan profil hedef        : VPIP~22-23 / PFR~19 / 3bet~10 / AF~3", flush=True)

    print("\n" + "=" * 60)
    print("TURNUVA — gerçekçi 9-max SNG (4 güçlü + 3 reg + 1 balık)")
    print("rakipler: GTO Expert, Solver Bot, ICM Expert, Shark, TAG, LAG, Reg, Fish")
    N_SNG = 40
    print(f"{N_SNG} SNG", flush=True)
    print("=" * 60, flush=True)
    sopps = ["GTO Expert", "Solver Bot", "ICM Expert", "Shark", "TAG", "LAG", "Reg", "Fish"]
    place = defaultdict(list)
    for s in range(N_SNG):
        res, _ = run_sng(sopps, seed=3000 + s)
        for nm, pl in res.items(): place[nm].append(pl)
    print(f"\n  {N_SNG} SNG — ortalama yer (1=şampiyon, 9=son) · ITM=top3 · win:")
    for nm in ['Soyrac'] + sopps:
        pls = place[nm]; itm = sum(1 for p in pls if p <= 3)
        print(f"    {nm:<14} ort {sum(pls)/len(pls):.2f} · ITM {itm}/{N_SNG} (%{100*itm/N_SNG:.0f}) · win {pls.count(1)}")
    print(f"\nDONE {time.time()-t0:.0f}s")
