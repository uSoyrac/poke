"""KAYIP-KARAR ANALİZİ: Soyrac %100-kitap hangi KARAR tipleri yüzünden çip kaybediyor?
Cash (her el reset → temiz el-başı P/L). Her el Soyrac'ın aksiyon dizisi + net sonucu
kaydedilir; kaybeden eller karar-tipi kovasına ayrılır. Hangi kova en çok ÇİP sızdırıyor
(sadece sayı değil, hacim) raporlanır → gerçek leak orada.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_loss_analysis.py [hands]
"""
from __future__ import annotations
import sys, time
from collections import defaultdict
from app.engine.game_loop import PokerGame
from app.engine.hand_state import Street, ActionType
from tools.soyrac_bot_sim import SoyracBrain

FIELD = ["Fish", "Calling Station", "TAG", "Reg", "LAG"]   # tipik 6-max karışık alan


def classify_loss(actions):
    """actions: [(street, action_type)] — kaybeden el için karar-kovası."""
    ats = [a for (_, a) in actions]
    streets = set(s for (s, _) in actions)
    postflop = any(s != Street.PREFLOP for (s, _) in actions)
    last = ats[-1] if ats else None
    if ActionType.ALL_IN in ats:
        return "Stack-off / all-in kaybı (cooler/commit)"
    if last == ActionType.FOLD:
        if not postflop:
            return "Preflop fold (sadece kör/ante)"
        return "Postflop el-bırakma (yatırım + fold)"
    if last in (ActionType.BET, ActionType.RAISE):
        return "Agresyon kaybı (bet/raise → call yedi / SD kaybetti)"
    if last == ActionType.CALL:
        return "Call-down / payoff (ikinci-en-iyi ödedi)"
    return "Check-down / showdown kaybı"


def run(hands_n, seed=0):
    sb, bb, stack = 0.5, 1.0, 100.0
    n = 1 + len(FIELD)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=FIELD,
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain(); soy.pure_book = True; soy.tournament_mode = False
    for b in gl.bots.values():
        b.tournament_mode = False
    loss_cnt = defaultdict(int); loss_chips = defaultdict(float)
    win_chips = 0.0; total_loss = 0.0; nwin = nloss = nzero = 0
    for h in range(hands_n):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand()
        acts = []
        guard = 0
        while guard < 800:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                hh = gl.current_hand
                st = getattr(hh, "street", Street.PREFLOP)
                at, amt = soy.decide(hh, hh.hero_idx)
                acts.append((st, at))
                gl.hero_act(at, amt)
            elif not prog:
                break
        net = gl.players[0].stack - stack
        if net > 0.01:
            nwin += 1; win_chips += net
        elif net < -0.01:
            nloss += 1; total_loss += -net
            b = classify_loss(acts)
            loss_cnt[b] += 1; loss_chips[b] += -net
        else:
            nzero += 1
    return {"hands": hands_n, "nwin": nwin, "nloss": nloss, "nzero": nzero,
            "win_chips": win_chips, "total_loss": total_loss,
            "net_bb_per_100": 100 * (win_chips - total_loss) / hands_n,
            "loss_cnt": dict(loss_cnt), "loss_chips": dict(loss_chips)}


if __name__ == "__main__":
    H = int(sys.argv[1]) if len(sys.argv) > 1 else 30000
    t0 = time.time()
    r = run(H)
    print("\n" + "═" * 70)
    print(f"  SOYRAC KAYIP-KARAR ANALİZİ · {H} el · 6-max (Fish/Station/TAG/Reg/LAG)")
    print("═" * 70)
    print(f"  Kazanan el: {r['nwin']}  ·  Kaybeden el: {r['nloss']}  ·  ~breakeven: {r['nzero']}")
    print(f"  Net: {r['net_bb_per_100']:+.1f} bb/100  (kazanılan {r['win_chips']:.0f} − kaybedilen {r['total_loss']:.0f} bb)")
    print(f"\n  ── KAYIPLAR HANGİ KARARDAN (çip-hacmine göre) ──")
    print(f"  {'KARAR TİPİ':<48}{'el':>6}{'kayıp-bb':>10}{'%pay':>7}")
    tl = r['total_loss'] or 1
    for b in sorted(r['loss_chips'], key=lambda k: -r['loss_chips'][k]):
        print(f"  {b:<48}{r['loss_cnt'][b]:>6}{r['loss_chips'][b]:>10.0f}{100*r['loss_chips'][b]/tl:>6.0f}%")
    print(f"\n  (Not: 'Preflop fold' = kör/ante, kaçınılmaz disiplin — leak değil.")
    print(f"   Asıl bakılacak: call-down/payoff + agresyon + stack-off kovaları.)")
    print(f"  Süre: {time.time()-t0:.0f}s")
