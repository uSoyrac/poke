"""SOYRAC EV-ATIF SİM — 'nerede kazandık / nerede kaybettik' kırılımı.
Cash motorunu oynatır (deterministik), her el hero'nun NET bb'sini BAĞLAMA göre etiketler:
pozisyon · preflop-senaryo · ulaşılan-sokak · showdown-sonucu. → net bb/100 her kategoride.

Kullanıcı kuralı: SİMÜLASYON = GERÇEK OYNATMA. Çalıştır:
PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python tools/soyrac_attribution_sim.py [el_sayısı]
"""
from __future__ import annotations
import random, sys
from collections import defaultdict

from app.engine.game_loop import PokerGame
from app.engine.hand_state import Street
from app.poker.soyrac_advisor import (_committed_opponents, _limpers_before_hero)
from app.poker.gto_live_advice import _count_preflop_raises_before_hero
from tools.soyrac_matrix_sim import sample_field, PROFILES
from tools.soyrac_bot_sim import SoyracBrain

HANDS = int(sys.argv[1]) if len(sys.argv) > 1 else 12000


def scenario_of(hand, hero_idx):
    try:
        nr, _ = _count_preflop_raises_before_hero(hand, hero_idx)
        nl = _limpers_before_hero(hand, hero_idx)
        if nr == 0:
            return "RFI (açış)" if nl == 0 else "limp'li pot"
        if nr == 1:
            return "vs-RFI (tek raise)"
        return "vs-3bet+ (şişmiş)"
    except Exception:
        return "?"


def run(profile_tier, hands, seed=500, stack=100.0):
    random.seed(seed)
    field = sample_field(profile_tier, 5, 7000)   # 6-max
    names = ["Soyrac"] + field
    n = len(names)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=0.5, big_blind=1.0,
                   ante=0, hero_seat=0, bot_archetypes=field,
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain(); soy.tournament_mode = False
    for b in gl.bots.values():
        b.tournament_mode = True

    by_pos = defaultdict(lambda: [0.0, 0])      # pos → [net, hands]
    by_scn = defaultdict(lambda: [0.0, 0])
    by_street = defaultdict(lambda: [0.0, 0])
    by_outcome = defaultdict(lambda: [0.0, 0])
    total = [0.0, 0]

    for h in range(hands):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand()
        hand = gl.current_hand
        hero = hand.players[0]
        hero_pos = hero.position
        scn = None
        guard = 0
        while guard < 800:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                hh = gl.current_hand
                if scn is None and getattr(hh, "street", None) == Street.PREFLOP:
                    scn = scenario_of(hh, hh.hero_idx)
                at, amt = soy.decide(hh, hh.hero_idx)
                gl.hero_act(at, amt)
            elif not prog:
                break
        net = gl.players[0].stack - stack
        if scn is None:
            scn = scenario_of(hand, 0)
        comm = len(hand.community)
        hero_folded = getattr(gl.players[0], "is_folded", False)
        # ulaşılan sokak
        if hero_folded and comm == 0:
            street = "preflop-fold"
        elif hero_folded:
            street = {3: "flop-fold", 4: "turn-fold", 5: "river-fold"}.get(comm, "postflop-fold")
        else:
            street = {0: "preflop-sonu", 3: "flop", 4: "turn", 5: "river/showdown"}.get(comm, "?")
        # sonuç
        if abs(net) < 0.01:
            outcome = "sıfır (walk/fold)"
        elif not hero_folded and comm == 5:
            outcome = "showdown KAZANÇ" if net > 0 else "showdown KAYIP"
        elif net > 0:
            outcome = "showdown'suz KAZANÇ (fold aldı)"
        else:
            outcome = "showdown'suz KAYIP"

        for d, k in ((by_pos, hero_pos), (by_scn, scn), (by_street, street), (by_outcome, outcome)):
            d[k][0] += net; d[k][1] += 1
        total[0] += net; total[1] += 1

    def fmt(d):
        return sorted(((k, round(100 * v[0] / max(v[1], 1), 1), v[1]) for k, v in d.items()),
                      key=lambda x: -x[1])
    return {"toplam_bb100": round(100 * total[0] / max(total[1], 1), 1), "el": total[1],
            "pozisyon": fmt(by_pos), "senaryo": fmt(by_scn),
            "sokak": fmt(by_street), "sonuç": fmt(by_outcome)}


def main():
    for prof in ("soft", "orta"):
        r = run(PROFILES[prof], HANDS, seed=500)
        print(f"\n{'='*64}\n  PROFİL: {prof}  ·  {r['el']} el  ·  TOPLAM {r['toplam_bb100']:+.1f} bb/100\n{'='*64}")
        for dim in ("pozisyon", "senaryo", "sokak", "sonuç"):
            print(f"  — {dim} (bb/100 · el):")
            for k, v, nn in r[dim]:
                bar = "█" * min(20, int(abs(v) / 8)) if v >= 0 else "▒" * min(20, int(abs(v) / 8))
                print(f"      {k:24} {v:+7.1f}  (n={nn:5})  {bar}")


if __name__ == "__main__":
    main()
