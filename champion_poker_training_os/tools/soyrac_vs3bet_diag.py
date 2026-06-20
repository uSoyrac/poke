"""VS-3BET LEAK TEŞHİSİ — yüksek-güç. 3-bet'li pota giren ellerde hero'nun NET bb'sini
preflop-AKSİYON (4-bet/call/fold) × ulaşılan-sokak × showdown'a göre kırar → leak NEREDE.
PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_vs3bet_diag.py [el]
"""
from __future__ import annotations
import random, sys
from collections import defaultdict

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Street, ActionType
from app.poker.gto_live_advice import _count_preflop_raises_before_hero
from tools.soyrac_matrix_sim import sample_field, PROFILES
from tools.soyrac_bot_sim import SoyracBrain

HANDS = int(sys.argv[1]) if len(sys.argv) > 1 else 40000


def run(tier, hands, seed=500, stack=100.0):
    random.seed(seed)
    field = sample_field(tier, 5, 7000)
    n = 1 + len(field)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=field,
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain(); soy.tournament_mode = False
    for b in gl.bots.values():
        b.tournament_mode = True

    by_act = defaultdict(lambda: [0.0, 0])     # hero facing-3bet aksiyonu → [net,n]
    by_act_street = defaultdict(lambda: [0.0, 0])
    tot3 = [0.0, 0]
    for h in range(hands):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand()
        hand = gl.current_hand
        faced3 = False; hero_act3 = None
        guard = 0
        while guard < 800:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                hh = gl.current_hand
                if hero_act3 is None and getattr(hh, "street", None) == Street.PREFLOP:
                    nr, _ = _count_preflop_raises_before_hero(hh, hh.hero_idx)
                    if nr >= 2:
                        faced3 = True
                at, amt = soy.decide(hh, hh.hero_idx)
                if faced3 and hero_act3 is None and getattr(hh, "street", None) == Street.PREFLOP:
                    hero_act3 = ("4-BET" if at in (ActionType.RAISE, ActionType.ALL_IN)
                                 else "CALL" if at == ActionType.CALL else "FOLD")
                gl.hero_act(at, amt)
            elif not prog:
                break
        if not faced3:
            continue
        net = gl.players[0].stack - stack
        comm = len(hand.community)
        folded = getattr(gl.players[0], "is_folded", False)
        st = ("preflop" if comm == 0 else {3: "flop", 4: "turn", 5: "river"}.get(comm, "?"))
        st += "-fold" if folded and comm > 0 else ""
        key = hero_act3 or "?"
        by_act[key][0] += net; by_act[key][1] += 1
        by_act_street[f"{key} · {st}"][0] += net; by_act_street[f"{key} · {st}"][1] += 1
        tot3[0] += net; tot3[1] += 1
    return by_act, by_act_street, tot3


def main():
    for prof in ("soft", "orta"):
        ba, bas, t = run(PROFILES[prof], HANDS)
        print(f"\n{'='*60}\n  {prof}: vs-3bet pot {t[1]} el · TOPLAM {100*t[0]/max(t[1],1):+.1f} bb/100\n{'='*60}")
        print("  hero facing-3bet aksiyonu (bb/100 · el · toplam-bb):")
        for k, v in sorted(ba.items(), key=lambda x: x[1][0]):
            print(f"    {k:6} {100*v[0]/max(v[1],1):+8.1f}  n={v[1]:4}  net={v[0]:+8.1f}bb")
        print("  aksiyon × sokak (en çok kaybedenler):")
        for k, v in sorted(bas.items(), key=lambda x: x[1][0])[:6]:
            print(f"    {k:18} net={v[0]:+8.1f}bb  n={v[1]:4}")


if __name__ == "__main__":
    main()
