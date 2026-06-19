"""SOYRAC MATRIX SIM — kapsamlı gerçek-oynatma: cash (masa-boyutu × stack × profil) +
SNG (profil), hepsi SoyracBrain pure_book (bot=kitap). Çıktı: /tmp/soyrac_matrix_results.json.

Kullanıcı kuralı: SİMÜLASYON = GERÇEK OYNATMA (varsayma). Bu tool gerçek motoru koşturur.
Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_matrix_sim.py [hizli]
"""
from __future__ import annotations
import json, random, sys, time
from collections import defaultdict

from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType
from app.engine.bot_brain import FIELD_TIERS, _SKILL_TIER
from tools.soyrac_bot_sim import SoyracBrain, run_sng

FAST = len(sys.argv) > 1 and sys.argv[1] == "hizli"

# Profil havuzları (saha kompozisyonu) — FIELD_TIERS'ten örneklenir
PROFILES = {
    "soft":  "Mikro ($1-5)",      # ~%74 zayıf
    "orta":  "Orta ($55-215)",    # ~%45 zayıf
    "elit":  "Yüksek ($530+)",    # ~%25 zayıf (en zor)
}


def sample_field(tier_key: str, n: int, seed: int) -> list:
    """FIELD_TIERS ağırlıklarından n rakip örnekle (deterministik/seed)."""
    w = FIELD_TIERS[tier_key]
    names = list(w.keys()); wts = list(w.values())
    rng = random.Random(seed)
    return rng.choices(names, weights=wts, k=n)


def field_strong_frac(field: list) -> float:
    s = sum(1 for a in field if _SKILL_TIER.get(a) == "strong")
    return round(100 * s / max(len(field), 1), 0)


def cash_table(opponents, hands_n, seed, stack_bb):
    """run_cash'in stack-parametreli hali (masa-boyutu = 1+len(opponents))."""
    names = ["Soyrac"] + list(opponents)
    n = len(names)
    sb, bb, stack = 0.5, 1.0, float(stack_bb)
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain(); soy.tournament_mode = False
    assert soy.pure_book, "bot=kitap DEĞİL — pure_book kapalı!"
    for b in gl.bots.values():
        b.tournament_mode = True
    net = defaultdict(float)
    for h in range(hands_n):
        for p in gl.players:
            p.stack = stack; p.is_eliminated = False
        gl.start_hand()
        guard = 0
        while guard < 800:
            guard += 1
            hh = gl.current_hand
            if hh and hh.is_complete:
                break
            prog = gl.step_action()
            if gl.is_waiting_for_hero:
                at, amt = soy.decide(gl.current_hand, gl.current_hand.hero_idx)
                gl.hero_act(at, amt)
            elif not prog:
                break
        for i in range(n):
            net[names[i]] += gl.players[i].stack - stack
    return round(100 * net["Soyrac"] / hands_n, 2)


def main():
    t0 = time.time()
    hands = 250 if FAST else 500
    seeds = 3 if FAST else 5
    sng_n = 10 if FAST else 20
    table_sizes = {"HU(2)": 1, "6-max(6)": 5, "9-max(9)": 8}
    stacks = [40, 100, 200]
    results = {"meta": {"hands_per_cell": hands, "seeds": seeds, "sng_per_cell": sng_n,
                        "bot": "SoyracBrain pure_book (bot=kitap)"}, "cash": [], "sng": []}

    # ---- CASH MATRIX ----
    print("=== CASH MATRIX ===", flush=True)
    for prof, tier in PROFILES.items():
        for tname, nopp in table_sizes.items():
            for st in stacks:
                vals = []
                for s in range(seeds):
                    fld = sample_field(tier, nopp, 7000 + s * 13 + nopp + st)
                    vals.append(cash_table(fld, hands, 500 + s, st))
                avg = round(sum(vals) / len(vals), 2)
                cell = {"profil": prof, "masa": tname, "stack_bb": st,
                        "bb_per_100": avg, "seeds": vals,
                        "alan_elit_%": field_strong_frac(sample_field(tier, max(nopp, 8), 7000))}
                results["cash"].append(cell)
                print(f"  {prof:5} {tname:9} {st:3}bb → {avg:+.1f} bb/100  (seeds {vals})", flush=True)

    # ---- SNG MATRIX (9-handed) ----
    print("\n=== SNG MATRIX (9-handed) ===", flush=True)
    for prof, tier in PROFILES.items():
        places = []
        for s in range(sng_n):
            fld = sample_field(tier, 8, 9000 + s * 7)
            place, _ = run_sng(fld, seed=200 + s)
            places.append(place["Soyrac"])
        itm = sum(1 for p in places if p <= 3)
        win = places.count(1)
        cell = {"profil": prof, "n": sng_n, "ort_yer": round(sum(places) / len(places), 2),
                "ITM_top3": itm, "win": win, "ITM_%": round(100 * itm / len(places), 0)}
        results["sng"].append(cell)
        print(f"  {prof:5} → ort.yer {cell['ort_yer']}/9 · ITM {itm}/{sng_n} (%{cell['ITM_%']:.0f}) · win {win}",
              flush=True)

    results["meta"]["duration_s"] = round(time.time() - t0, 1)
    with open("/tmp/soyrac_matrix_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nKAYDEDİLDİ: /tmp/soyrac_matrix_results.json ({results['meta']['duration_s']}s)")


if __name__ == "__main__":
    main()
