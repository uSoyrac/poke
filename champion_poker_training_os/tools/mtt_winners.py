"""Kim büyük MTT kazanıyor? — pozisyon-fix'li, tüm arketip karışık sahada
win/final-masa/ITM oranları arketip + skill-tier bazlı. (Kazanan turnuva-DNA'sı
→ Soyrac turnuva katmanını buna göre inşa edeceğiz.) Memory: varsayma, oynat."""
from __future__ import annotations
import random
from collections import defaultdict
import app.simulator.headless_mtt as H
from app.engine.game_loop import PokerGame
from app.engine.bot_brain import BOT_ARCHETYPES, archetype_skill

# pozisyon-FIX'li _play_one_hand (hand_count hile → buton döner)
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
    gl.hand_count = 2
    gl.dealer_idx = (button - 1) % n
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

if __name__ == "__main__":
    import time, sys
    t0 = time.time()
    FSIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    print(f"=== KİM KAZANIYOR · {FSIZE} kişi · {N} turnuva · 9-max · pozisyon-fix'li ===", flush=True)
    S = defaultdict(lambda: {"ent": 0, "win": 0, "ft": 0, "t3": 0, "itm": 0, "pct": 0.0})
    for s in range(N):
        r = H.run_mtt(FSIZE, seed=s)
        order = r["finish_1st_to_last"]; n = len(order)
        paid = max(1, int(n * 0.15))
        for rank, arch in enumerate(order, 1):
            d = S[arch]; d["ent"] += 1; d["pct"] += (rank - 1) / max(n - 1, 1)
            if rank == 1: d["win"] += 1
            if rank <= 9: d["ft"] += 1
            if rank <= 3: d["t3"] += 1
            if rank <= paid: d["itm"] += 1
        if (s + 1) % 3 == 0:
            print(f"   {s+1}/{N} turnuva · {time.time()-t0:.0f}s", flush=True)
    print(f"\n  ARKETİP (entrant≥20) — win% · FT% · ITM% · ort.percentil (düşük=iyi), FT%'e göre sıralı:")
    rows = [(a, d) for a, d in S.items() if d["ent"] >= 20]
    rows.sort(key=lambda x: -x[1]["ft"] / x[1]["ent"])
    print(f"    {'ARKETİP':<18}{'tier':<8}{'ent':>5}{'win%':>7}{'FT%':>7}{'ITM%':>7}{'ortP':>7}")
    for a, d in rows:
        e = d["ent"]
        print(f"    {a:<18}{archetype_skill(a):<8}{e:>5}{100*d['win']/e:>7.2f}{100*d['ft']/e:>7.1f}{100*d['itm']/e:>7.0f}{100*d['pct']/e:>7.0f}")
    # tier özet
    print("\n  SKILL-TIER ÖZET (win% · FT% · ITM%):")
    T = defaultdict(lambda: [0, 0, 0, 0])
    for a, d in S.items():
        t = archetype_skill(a); T[t][0] += d["ent"]; T[t][1] += d["win"]; T[t][2] += d["ft"]; T[t][3] += d["itm"]
    for t in ("strong", "mid", "weak"):
        e, w, f, i = T[t]
        if e: print(f"    {t:<8} ent {e:>5} · win %{100*w/e:.2f} · FT %{100*f/e:.1f} · ITM %{100*i/e:.0f}")
    print(f"\nDONE {time.time()-t0:.0f}s")
