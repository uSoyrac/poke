"""DERİN-STACK vs ELİT tanı: Soyrac %100-kitap'ın postflop chip-EV leak'ini İZOLE eder.

MTT'de derin+elit alanda zayıftı. Cash bb/100 vs SADECE-ELİT (ICM/survival gürültüsü
yok → saf chip-EV) + derinlik gradyanı (25/50/100bb) + GTO Expert KONTROLÜ (aynı koltukta
elit ne yapardı) → leak derinlikle büyüyor mu, ve kitap elitten ne kadar geride?

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_deep_diag.py [hands] [seeds]
"""
from __future__ import annotations
import sys, time
from app.engine.game_loop import PokerGame
from app.engine.bot_brain import BotBrain, BOT_ARCHETYPES
from tools.soyrac_bot_sim import SoyracBrain

ELITES = ["GTO Expert", "Solver Bot", "ICM Expert", "Shark", "Exploit Expert"]


def _seat0(kind):
    if kind == "Soyrac":
        b = SoyracBrain(); b.pure_book = True; b.tournament_mode = False
    else:
        b = BotBrain(BOT_ARCHETYPES[kind]); b.tournament_mode = False
    return b


def run_cash(kind, depth_bb, hands_n, seed=0):
    sb, bb = 0.5, 1.0
    stack = float(depth_bb)
    n = 1 + len(ELITES)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=ELITES,
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    s0 = _seat0(kind)
    for b in gl.bots.values():
        b.tournament_mode = False
    net = 0.0
    for h in range(hands_n):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand(); guard = 0
        while guard < 800:
            guard += 1; hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                at, amt = s0.decide(gl.current_hand, gl.current_hand.hero_idx)
                gl.hero_act(at, amt)
            elif not prog:
                break
        net += gl.players[0].stack - stack
    return round(100 * net / hands_n, 2)


if __name__ == "__main__":
    HANDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    SEEDS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    DEPTHS = [25, 50, 100]
    BRAINS = ["Soyrac", "GTO Expert", "Shark"]
    print("\n" + "═" * 60)
    print(f"  DERİN-vs-ELİT TANI · 6-max cash · sadece-elit alan")
    print(f"  {HANDS} el × {SEEDS} seed/hücre · bb/100 (taban: hepsi ≈0 toplam)")
    print(f"  Rakipler: {', '.join(ELITES)}")
    print("═" * 60)
    print(f"\n  {'KOLTUK(seat0)':<14}" + "".join(f"{str(d)+'bb':>10}" for d in DEPTHS))
    res = {}
    t0 = time.time()
    for brain in BRAINS:
        row = []
        for depth in DEPTHS:
            vals = [run_cash(brain, depth, HANDS, seed=s) for s in range(SEEDS)]
            avg = round(sum(vals) / len(vals), 2)
            res[(brain, depth)] = avg
            row.append(avg)
        print(f"  {brain:<14}" + "".join(f"{v:>+10.2f}" for v in row), flush=True)
    print(f"\n  → KİTAP AÇIĞI (Soyrac − GTO Expert), derinliğe göre:")
    for depth in DEPTHS:
        gap = round(res[("Soyrac", depth)] - res[("GTO Expert", depth)], 2)
        print(f"      {depth}bb: {gap:+.2f} bb/100")
    print(f"\n  Süre: {time.time()-t0:.0f}s")
