"""KAPSAMLI profil başarı simülasyonu (kullanıcı talebi).

Memory kuralı: sonucu VARSAYMA — gerçekten oynat (run_mtt + PokerGame = real
BotBrain), ölç. EŞİT profil dağıtımı; turnuva 50/100/200bb derinlik; alan
1000(×10)/500/200/100; + cash bb/100. Çıktı: per-profil tablo + JSON.

Çalıştır:  PYTHONPATH=. .venv/bin/python tools/profile_sim.py
"""
from __future__ import annotations
import json, time, random
from collections import defaultdict

import app.simulator.headless_mtt as H
from app.simulator.headless_mtt import run_mtt
from app.simulator.mtt_field import itm_places
from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain, archetype_skill
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType, Street

# 27 arketip (Karma=meta wrapper hariç) — eşit dağıtım için
ARCHS = [a for a in BOT_ARCHETYPES if a != "Karma (Mixed)"]
_BB0 = H._LEVELS[0][1]          # ilk level big blind (=50 chip)
RESULTS = {"mtt": {}, "cash": {}, "meta": {}}
OUT = "/tmp/profile_sim_results.json"


def _save():
    with open(OUT, "w") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)


def equal_field(n, rng=None):
    """n koltuğa 27 arketibi EŞİT (artık dengeli) dağıt + karıştır."""
    rng = rng or random
    base = (ARCHS * (n // len(ARCHS) + 1))[:n]
    rng.shuffle(base)
    return base


# ── MTT: derinlik × alan, eşit profil ───────────────────────────────
def run_mtt_block(field, seeds, depth_bb):
    """field kişilik turnuvayı `seeds` kez (eşit profil, depth_bb derinlik) oynat."""
    H._START_CHIPS = int(depth_bb * _BB0)        # derinlik = chip / bb0
    _orig = H.realistic_mtt_mix
    H.realistic_mtt_mix = lambda nn, rng=None, tier=None: equal_field(nn, rng)
    agg = defaultdict(lambda: {"ent": 0, "itm": 0, "win": 0, "top3": 0, "pctsum": 0.0})
    paid = itm_places(field)
    hands = 0
    try:
        for s in range(seeds):
            r = run_mtt(field, seed=1000 + s)
            order = r["finish_1st_to_last"]
            hands += r.get("hands", 0)
            n = len(order)
            for rank, arch in enumerate(order, start=1):
                a = agg[arch]
                a["ent"] += 1
                a["pctsum"] += (rank - 1) / max(n - 1, 1)   # 0=1st .. 1=last
                if rank <= paid:
                    a["itm"] += 1
                if rank == 1:
                    a["win"] += 1
                if rank <= 3:
                    a["top3"] += 1
    finally:
        H.realistic_mtt_mix = _orig
        H._START_CHIPS = 5000
    rows = {}
    for arch, a in agg.items():
        e = a["ent"] or 1
        rows[arch] = {
            "ent": a["ent"], "itm_pct": round(100 * a["itm"] / e, 1),
            "win": a["win"], "top3": a["top3"],
            "avg_fin_pct": round(100 * a["pctsum"] / e, 1),
            "skill": archetype_skill(arch),
        }
    return {"field": field, "seeds": seeds, "depth_bb": depth_bb,
            "paid": paid, "hands": hands, "rows": rows}


# ── CASH: 6-max, TÜM koltuklar bot (hero da arketip), bb/100 ──────────
def run_cash(n_tables=360, hands_per=250, depth_bb=100):
    rng = random.Random(7)
    net = defaultdict(float)      # arch → toplam bb
    seen = defaultdict(int)       # arch → toplam el (koltuk-el)
    SB, BB = 0.5, 1.0
    stack = float(depth_bb)
    # FIX: 6<27 olduğu için equal_field(6) yalnız ilk 6 arketibi alıyordu →
    # 27'nin TAMAMI masaya otursun diye dönen (shuffle'lı) bir havuzdan 6'şar çek.
    _pool = []
    def _draw6():
        nonlocal _pool
        while len(_pool) < 6:
            extra = ARCHS[:]; rng.shuffle(extra); _pool += extra
        s, _pool = _pool[:6], _pool[6:]
        return s
    for t in range(n_tables):
        seats = _draw6()                     # 6 arketip (27 arasından dönen)
        game = PokerGame(num_players=6, starting_stack=stack, small_blind=SB,
                         big_blind=BB, hero_seat=0, bot_archetypes=seats[1:],
                         paced_bots=False)
        hero_brain = BotBrain(BOT_ARCHETYPES.get(seats[0], BOT_ARCHETYPES["Balanced Reg"]))
        for h in range(hands_per):
            for p in game.players:
                p.stack = stack
                p.is_eliminated = False
            game.start_hand()
            guard = 0
            while game.current_hand and not game.current_hand.is_complete and guard < 300:
                if game.is_waiting_for_hero:
                    try:
                        act, amt = hero_brain.decide(game.current_hand, game.hero_seat)
                        game.hero_act(act, amt)
                    except Exception:
                        game.hero_act(ActionType.FOLD, 0)
                else:
                    game.step_action()
                guard += 1
            for i, p in enumerate(game.players):
                net[seats[i]] += (p.stack - stack)
                seen[seats[i]] += 1
        if t % 60 == 0:
            RESULTS["meta"]["cash_progress"] = f"{t}/{n_tables}"
            _save()
    rows = {}
    for arch in ARCHS:
        hh = seen[arch] or 1
        rows[arch] = {"hands": seen[arch],
                      "bb_per_100": round(100 * net[arch] / hh, 2),
                      "skill": archetype_skill(arch)}
    return {"tables": n_tables, "hands_per": hands_per, "depth_bb": depth_bb, "rows": rows}


if __name__ == "__main__":
    t0 = time.time()
    # field, seeds (küçük alanda daha çok seed → dengeli örnek)
    FIELDS = [(1000, 10), (500, 10), (200, 15), (100, 25)]
    DEPTHS = [50, 100, 200]
    for depth in DEPTHS:
        for field, seeds in FIELDS:
            key = f"{field}p_{depth}bb"
            print(f"[MTT] {key} ({seeds} seed)…", flush=True)
            RESULTS["mtt"][key] = run_mtt_block(field, seeds, depth)
            RESULTS["meta"]["elapsed"] = round(time.time() - t0, 1)
            _save()
            print(f"   done ({RESULTS['mtt'][key]['hands']} hands, "
                  f"{RESULTS['meta']['elapsed']}s total)", flush=True)
    print("[CASH] 6-max bb/100…", flush=True)
    RESULTS["cash"]["100bb"] = run_cash(depth_bb=100)
    RESULTS["meta"]["elapsed"] = round(time.time() - t0, 1)
    RESULTS["meta"]["done"] = True
    _save()
    print(f"ALL DONE in {RESULTS['meta']['elapsed']}s → {OUT}", flush=True)
