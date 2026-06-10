"""SOYRAC BOT testi — sistemi GERÇEKTEN oynayan bir bot kurup eşit alanda ölç.
Memory: sonucu VARSAYMA, oynat. SoyracBrain kararlarını soyrac_advisor (preflop)
+ equity/cbet-defend (postflop) ile verir. 10 SNG (9-max) + 5 cash (6-max),
elitlerle (GTO Expert/Solver Bot) yan yana.

Çalıştır: PYTHONPATH=. .venv/bin/python tools/soyrac_bot_sim.py
"""
from __future__ import annotations
import random
from collections import defaultdict

from app.engine.game_loop import PokerGame
from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
from app.engine.hand_state import ActionType, Street
from app.poker.soyrac_advisor import advice_from_hand


class SoyracBrain:
    """Soyrac v2 — preflop SHCP (soyrac_advice, kazanıyor) + postflop KAZANAN
    GTO pipeline'ına delege (board-aware _hand_strength + _gto_postflop_action +
    commit-gate + eq-0.16 haircut). v1 board-kör monte_carlo_equity kullanıp
    -165 sızdırıyordu; kök neden buydu (ordu teşhisi)."""
    def __init__(self):
        self._gto = BotBrain(BOT_ARCHETYPES["GTO Expert"])   # kazanan postflop motoru
        self.profile = self._gto.profile
        self.icm_pressure = 0.0
        self.tournament_mode = True
        self.adaptive = False

    def set_opponent_read(self, *a, **k):
        pass

    def _equity(self, p, state):
        try:
            from app.poker.equity import monte_carlo_equity
            hole = [c.code for c in p.hole_cards[:2]]
            board = [c.code for c in state.community]
            # FIX: rastgele range equity'yi ŞİŞİRİYORDU (postflop leak kaynağı).
            # Gerçekçi devam-range'ine (top ~%45) karşı ölç → cbet/defend doğru input.
            return monte_carlo_equity(hole, board, villain_range_width=0.45,
                                      simulations=160)
        except Exception:
            return 0.45

    def decide(self, state, idx):
        p = state.players[idx]
        valid = {t for (t, _, _) in state.get_valid_actions(idx)}
        to_call = state.to_call(idx)
        bb = max(state.big_blind, 0.01)
        eff = (p.stack + p.current_bet) / bb
        commit_all = (p.stack, )

        if state.street == Street.PREFLOP:
            # TURNUVA SHORT-STACK (D149): <22bb + tournament → kanıtlı push/fold'a
            # DELEGE (Nash jam çok daha geniş; SHCP score≥16 jam ÇOK sıkıydı → körler
            # yiyip MTT geç-aşamada bust). Derin (≥22bb) oyun SHCP kalır.
            if self.tournament_mode and eff < 22:
                self._gto.icm_pressure = self.icm_pressure
                self._gto.tournament_mode = True
                return self._gto.decide(state, idx)
            adv = advice_from_hand(state, idx, stack_bb=eff, icm=self.icm_pressure > 0)
            act = (adv or {}).get("action", "FOLD")
            if act == "JAM" and ActionType.ALL_IN in valid:
                return ActionType.ALL_IN, p.stack
            if act in ("RAISE (AÇ)", "3-BET", "4-BET"):
                if eff <= 12 and ActionType.ALL_IN in valid:
                    return ActionType.ALL_IN, p.stack
                if act == "RAISE (AÇ)":
                    to = max(bb * 2.3, state.min_raise + p.current_bet)
                else:                                   # 3bet/4bet
                    to = min(state.current_bet * 3.0, p.stack + p.current_bet)
                    to = max(to, state.min_raise + p.current_bet)
                if ActionType.RAISE in valid:
                    return ActionType.RAISE, to
                if ActionType.BET in valid:
                    return ActionType.BET, to
            if act == "CALL" and ActionType.CALL in valid:
                return ActionType.CALL, to_call
            if to_call <= 0 and ActionType.CHECK in valid:
                return ActionType.CHECK, 0.0
            return (ActionType.FOLD, 0.0) if ActionType.FOLD in valid else (ActionType.CHECK, 0.0)

        # POSTFLOP — KAZANAN pipeline'a DELEGE: GTO Expert'in board-aware
        # _hand_strength + _gto_postflop_action + commit-gate + eq-0.16 haircut'i.
        # (v1'in board-kör monte_carlo_equity leak'i bununla kapanır.)
        self._gto.icm_pressure = self.icm_pressure
        self._gto.tournament_mode = self.tournament_mode
        return self._gto.decide(state, idx)


# ── tek-el oynatıcı (seat0 = Soyrac, gerisi arketip) ─────────────────
def _play_hand(stacks, archs, sb, bb, button, soyrac_seat=0):
    n = len(stacks)
    gl = PokerGame(num_players=n, starting_stack=1500, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=soyrac_seat, bot_archetypes=archs[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    for i in range(n):
        gl.players[i].stack = stacks[i]
    gl.dealer_idx = button % n
    soyrac = SoyracBrain()
    for b in gl.bots.values():
        b.tournament_mode = True
    gl.start_hand()
    guard = 0
    while guard < 800:
        guard += 1
        h = gl.current_hand
        if h and h.is_complete:
            break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            hh = gl.current_hand
            at, amt = soyrac.decide(hh, hh.hero_idx)
            gl.hero_act(at, amt)
        elif not prog:
            break
    return [max(0.0, gl.players[i].stack) for i in range(n)]


# ── SNG (9-max tek masa turnuva) ─────────────────────────────────────
# FIX: TEK kalıcı oyun → buton doğal döner + eleme oyun-içi (is_eliminated).
def run_sng(opponents, seed):
    names = ["Soyrac"] + list(opponents)        # seat0 = Soyrac
    n = len(names)
    gl = PokerGame(num_players=n, starting_stack=1500, small_blind=10, big_blind=20,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain()
    for b in gl.bots.values():
        b.tournament_mode = True
    levels = [(10, 20), (15, 30), (25, 50), (40, 80), (60, 120), (100, 200),
              (150, 300), (250, 500), (400, 800), (600, 1200)]
    finish = []                                  # bust sırası (ilk busted = son)
    hands = 0
    while sum(1 for p in gl.players if p.stack > 0) > 1:
        sb, bb = levels[min(hands // 10, len(levels) - 1)]
        gl.small_blind, gl.big_blind = sb, bb
        for p in gl.players:
            if p.stack <= 0:
                p.is_eliminated = True
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
        for i, p in enumerate(gl.players):
            if p.stack <= 0 and i not in finish:
                finish.append(i)
        hands += 1
        if hands > 600:
            break
    survivor = [i for i, p in enumerate(gl.players) if p.stack > 0]
    order_1st_to_last = survivor + finish[::-1]
    place = {idx: rank + 1 for rank, idx in enumerate(order_1st_to_last)}
    return {names[i]: place.get(i, n) for i in range(n)}, hands


# ── CASH (6-max bb/100) ──────────────────────────────────────────────
# FIX: TEK kalıcı oyun + start_hand tekrarı → buton DOĞAL döner (pozisyonlar
# rotasyon yapar). Eskiden her el fresh oyun = hep "hand 1" = dealer hep seat0
# = Soyrac hep BTN sanılıyordu → erken pozisyonda aşırı geniş oynayıp spew.
def run_cash(opponents, hands_n, seed=0):
    names = ["Soyrac"] + list(opponents)
    n = len(names)
    sb, bb, stack = 0.5, 1.0, 100.0
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain()
    for b in gl.bots.values():
        b.tournament_mode = True
    net = defaultdict(float)
    for h in range(hands_n):
        for p in gl.players:                 # cash: her el stack resetle
            p.stack = stack
            p.is_eliminated = False
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
    return {nm: round(100 * net[nm] / hands_n, 2) for nm in names}


if __name__ == "__main__":
    import time, json
    t0 = time.time()
    FIELD = ["GTO Expert", "Solver Bot", "ICM Expert", "Shark", "TAG",
             "Reg", "Nit", "Fish"]          # 8 rakip (elitler dahil) — eşit masada
    # 10 SNG
    sng_place = defaultdict(list)
    for s in range(30):
        place, hh = run_sng(FIELD, seed=100 + s)
        for nm, pl in place.items():
            sng_place[nm].append(pl)
        print(f"SNG {s+1}/30: Soyrac yeri = {place['Soyrac']}/9 ({hh} el)", flush=True)
    print("\n=== 30 SNG ORTALAMA YER (1=şampiyon, 9=son) ===")
    for nm in ["Soyrac"] + FIELD:
        pls = sng_place[nm]
        itm = sum(1 for p in pls if p <= 3)
        print(f"  {nm:<12} ort.yer {sum(pls)/len(pls):.2f}  · top3(ITM) {itm}/30  · win {pls.count(1)}")
    # 5 CASH
    print("\n=== 10 CASH (6-max, 300 el) bb/100 ===")
    cash_agg = defaultdict(list)
    for s in range(10):
        opp = ["GTO Expert", "Solver Bot", "ICM Expert", "Fish", "Calling Station"]
        r = run_cash(opp, 1000, seed=500 + s)
        for nm, v in r.items():
            cash_agg[nm].append(v)
        print(f"  cash {s+1}/10: Soyrac {r['Soyrac']:+.1f}bb/100", flush=True)
    print("\n  PROFİL ort bb/100 (10 masa):")
    for nm in ["Soyrac", "GTO Expert", "Solver Bot", "ICM Expert", "Fish", "Calling Station"]:
        if cash_agg[nm]:
            print(f"    {nm:<16} {sum(cash_agg[nm])/len(cash_agg[nm]):+.2f}")
    print(f"\nDONE in {time.time()-t0:.0f}s")
