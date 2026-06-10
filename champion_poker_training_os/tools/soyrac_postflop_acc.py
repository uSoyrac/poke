"""Postflop accuracy — İNSAN 7-kademe kuralı vs gerçek motor (cbet/defend argmax),
flop/turn/river + 2 bağlam (check-edildi / bahis-karşısında)."""
from __future__ import annotations
import random
from collections import defaultdict
from app.engine.hand_state import Card, RANKS, SUITS
from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
from app.poker.postflop_gto import classify_board, cbet_strategy, defend_strategy

BB = BotBrain(BOT_ARCHETYPES["GTO Expert"])

def human_checked(strength, draws, tex):
    # GELİŞTİRİLMİŞ insan kuralı (masada kolay):
    #  KURU board (gökkuşağı/bağlantısız) + agresör → RANGE-CBET: elin ne olursa
    #  olsun küçük bas (GTO kuru board'da yüksek frekans blöf-cbet yapar).
    #  ISLAK board → polarize: sadece güçlü el / iyi çekme bas, gerisini çek.
    if tex.wetness < 0.30:
        return "bet"
    return "bet" if (strength >= 0.62 or draws >= 0.40) else "check"

def engine_checked(eq, tex, street):
    bet_f, _ = cbet_strategy(eq, tex, True, True, street, 2)
    return "bet" if bet_f >= 0.5 else "check"

def human_facing(strength, eq, be):
    eq_def = max(0.0, eq - 0.16)            # 'bir kademe aşağı say'
    if strength >= 0.72: return "raise"
    return "call" if eq_def >= be - 0.125 else "fold"

def engine_facing(eq, tex, pot, to_call):
    f, c, r = defend_strategy(max(0.0, eq - 0.16), tex, pot, to_call, 2)
    return "raise" if r >= max(f, c) else ("call" if c >= f else "fold")

def run(n_per_street=4000, seed=42):
    rng = random.Random(seed)
    deck0 = [Card(r, s) for r in RANKS for s in SUITS]
    acc = defaultdict(lambda: [0, 0])      # (street,ctx) -> [match,total]
    pot, to_call = 10.0, 5.0; be = to_call / (pot + to_call)
    for street, nb in (("flop", 3), ("turn", 4), ("river", 5)):
        for _ in range(n_per_street):
            d = deck0[:]; rng.shuffle(d)
            hole = d[:2]; board = d[2:2 + nb]
            strength, draws, _lbl = BB._hand_strength(hole, board)
            eq = min(1.0, strength + 0.45 * draws)
            try: tex = classify_board(board)
            except Exception: continue
            # bağlam 1: check-edildi (cbet kararı)
            h1, e1 = human_checked(strength, draws, tex), engine_checked(eq, tex, street)
            acc[(street, "checked→cbet")][0] += int(h1 == e1); acc[(street, "checked→cbet")][1] += 1
            # bağlam 2: yarım-pot bahis karşısında (defend kararı)
            h2, e2 = human_facing(strength, eq, be), engine_facing(eq, tex, pot, to_call)
            acc[(street, "facing→defend")][0] += int(h2 == e2); acc[(street, "facing→defend")][1] += 1
    return acc

if __name__ == "__main__":
    acc = run()
    print("=== POSTFLOP ACCURACY — insan 7-kademe vs motor argmax ===")
    overall = [0, 0]
    for street in ("flop", "turn", "river"):
        for ctx in ("checked→cbet", "facing→defend"):
            m, t = acc[(street, ctx)]
            overall[0] += m; overall[1] += t
            print(f"  {street:<6} {ctx:<16} {100*m/max(t,1):.1f}%  (n={t})")
    print(f"\n  GENEL POSTFLOP DOĞRULUK: {100*overall[0]/max(overall[1],1):.1f}%")
