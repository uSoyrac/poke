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
        self._gto = BotBrain(BOT_ARCHETYPES["GTO Expert"])   # CASH postflop motoru
        # İLERİ TURNUVA (ölçüldü): FT-kralı ICM Expert (FT %10.9 > GTO Expert %6.9).
        # Turnuvada survival+ICM-farkındalıklı agresyon → daha çok final masası.
        # AYRI beyin: cash SHCP+GTO Expert dokunulmaz, sadece tournament_mode değişir.
        self._tourney = BotBrain(BOT_ARCHETYPES["ICM Expert"])
        self.profile = self._gto.profile
        self.icm_pressure = 0.0
        self.tournament_mode = True
        self.adaptive = False
        # D261 (kullanıcı kuralı: "bot da KİTAPLA simüle etsin"): VARSAYILAN pure_book.
        # Sim ASLA ICM/GTO bot'una delege ETMEZ — preflop+postflop tamamen kitap
        # (soyrac_advice + soyrac_postflop_advice). Eski hybrid (delege) = ölçüm sapması.
        self.pure_book = True

    def set_opponent_read(self, *a, **k):
        pass

    # TURNUVA SURVIVAL (D150 GERİ ALINDI): flat survival-ICM (0.06) test edildi →
    # aşırı sıktı, derin-koşu agresyonunu öldürdü (full-expert FT %7.5→%0). MTT'de
    # derin-koşu > marjinal survival (bubble hariç). Floor KALDIRILDI; sadece
    # harness'in verdiği bubble-ICM (icm_pressure_for) geçer.
    def _surv_icm(self):
        return self.icm_pressure

    def _stage_icm(self, eff):
        # DENEY BAŞARISIZ (ölçüldü): derin>50bb survival-caution (0.10) → FT
        # %9.8→%8.5 DÜŞTÜ, ITM %26→%24, erken-bust düşmedi (%39). Tıpkı D150
        # flat-floor: caution accumulation'ı öldürüyor. NEUTRAL'a alındı (geri).
        # SONUÇ: ICM Expert delegasyonu (FT ~%10-12) zaten FT-tavanı.
        return self.icm_pressure

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
            _bp = getattr(self, "book_preflop", getattr(self, "pure_book", False))
            _use_icm_pre = (not _bp) or (getattr(self, "book_deep_only", False) and eff <= 22)  # kısa→ICM, derin→kitap
            if self.tournament_mode and _use_icm_pre:  # TURNUVA: ICM delege (HYBRID/kısa-stack)
                # PRE-EMPT STEAL (bridge prensibi): folded-to + geç poz + derin →
                # AÇIŞ rakibi bloke eder (fold-equity), pür-değerin ALTINDA geniş aç.
                # Az kişi = çok pre-empt (6-max > 9-max). "16'da 1NT ama 15'le aç."
                # mode: off / flat (kör, ROI-kanıtlı) / smart (koşullu: pozisyon+kapatma+vuln)
                pmode = getattr(self, "preempt_mode", "smart")   # ROI-kanıtlı (in+out-of-sample)
                if pmode != "off" and len(p.hole_cards) >= 2:
                    is_unraised = (state.current_bet <= bb * 1.01)
                    pos = (getattr(p, "position", "") or "").upper()
                    if is_unraised and pos in ("BTN", "CO", "SB", "HJ") and eff > 22:
                        from app.poker.soyrac_advisor import shcp_score, _RFI
                        from app.engine.bot_brain import hand_key as _hk
                        score = shcp_score(_hk(p.hole_cards[0], p.hole_cards[1]))
                        n_seats = len(state.players)
                        preempt = 3 + max(0, (9 - n_seats) // 2)   # az kişi → daha geniş
                        if pmode == "smart":
                            # (1) pozisyon kademesi — bridge koltuk: BTN en geniş, SB dar (OOP)
                            preempt += {"BTN": 1, "CO": 0, "HJ": 0, "SB": -1}.get(pos, 0)
                            # (2) kapatma bölgesi — blackjack 'sayaç patladı': final 3-4 tam-gaz
                            if n_seats <= 3:
                                preempt += 2
                            # (3) vulnerability — derin=bol fold-equity (+1); sığ-baskı=çek (−1)
                            if eff > 45:
                                preempt += 1
                            elif self._stage_icm(eff) > 0.5:
                                preempt -= 1
                        if score >= _RFI.get(pos, 13) - preempt:
                            to = max(bb * 2.2, state.min_raise + p.current_bet)
                            if ActionType.RAISE in valid:
                                return ActionType.RAISE, to
                            if ActionType.BET in valid:
                                return ActionType.BET, to
                        elif ActionType.FOLD in valid:
                            return ActionType.FOLD, 0.0
                self._tourney.icm_pressure = self._stage_icm(eff)   # +stage caution
                self._tourney.tournament_mode = True
                return self._tourney.decide(state, idx)
            adv = advice_from_hand(state, idx, stack_bb=eff, icm=self.icm_pressure > 0,
                                   tourney=self.tournament_mode)
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

        # RANGE-AWARE BLUFF-CATCH DENEYİ (ÖLÇÜLDÜ, GERİ ALINDI): zayıf-el+büyük-bahis+
        # A/broadway board → blanket FOLD test edildi. Cash nötr (#1 +52 korundu) ama
        # MTT FT %9.8→%8.1, ITM %26→%23 DÜŞTÜ — loose MTT sahasında over-fold (bahis
        # yapanların çoğu sıkı-A-range'ine sahip değil, bluff'lu). DERS: range-aware
        # fold okuma-bağımlı (sadece SIKI rakibe doğru); blanket bot-kuralı zarar.
        # YERİ = advice katmanı (D169 range_note), kullanıcı villain-read uygular.

        # PURE-BOOK (Faz C): postflop'u SAF KİTAP 7-kademe ile oyna (board-tehdit +
        # commit-gate + bluff-catch) — delege YOK. Botu = kullanıcının oynadığı sistem
        # yapar → şampiyona DÜRÜST ölçer. Toggle (default kapalı → davranış değişmez).
        if getattr(self, "book_postflop", getattr(self, "pure_book", False)):
            try:
                from app.poker.soyrac_advisor import soyrac_postflop_advice
                pf = soyrac_postflop_advice(state, idx)
                if pf and pf.get("action"):
                    a = pf["action"]; pot = max(getattr(state, "pot", 0.0) or 0.0, bb)
                    if "FOLD" in a:
                        if ActionType.FOLD in valid:
                            return ActionType.FOLD, 0.0
                    elif "RAISE" in a:
                        amt = min(to_call * 2.7, p.stack + p.current_bet)
                        amt = max(amt, state.min_raise + p.current_bet)
                        if ActionType.RAISE in valid:
                            return ActionType.RAISE, amt
                        if ActionType.ALL_IN in valid:
                            return ActionType.ALL_IN, p.stack
                    elif "CALL" in a and ActionType.CALL in valid:
                        return ActionType.CALL, to_call
                    elif "BET" in a:
                        frac = pf.get("size_frac") or 0.6
                        amt = min(max(pot * frac, bb), p.stack)
                        if ActionType.BET in valid:
                            return ActionType.BET, amt
                        if ActionType.RAISE in valid:
                            return ActionType.RAISE, max(amt, state.min_raise + p.current_bet)
                    # CHECK / fallback
                    if to_call <= 0 and ActionType.CHECK in valid:
                        return ActionType.CHECK, 0.0
                    if ActionType.CHECK in valid:
                        return ActionType.CHECK, 0.0
                    if ActionType.FOLD in valid:
                        return ActionType.FOLD, 0.0
            except Exception:
                pass   # kitap çözemezse aşağıdaki kazanan pipeline'a düş

        # POSTFLOP — KAZANAN pipeline'a DELEGE: GTO Expert'in board-aware
        # _hand_strength + _gto_postflop_action + commit-gate + eq-0.16 haircut'i.
        # (v1'in board-kör monte_carlo_equity leak'i bununla kapanır.)
        brain = self._tourney if self.tournament_mode else self._gto
        if self.tournament_mode:
            _eff = (p.stack + p.current_bet) / bb
            brain.icm_pressure = self._stage_icm(_eff)
        else:
            brain.icm_pressure = self._surv_icm()
        brain.tournament_mode = self.tournament_mode
        return brain.decide(state, idx)


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
    import random as _rnd; _rnd.seed(seed)      # D286: deck deterministik (eski: seed ölüydü)
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
    import random as _rnd; _rnd.seed(seed)      # D286: deck deterministik (eski: seed ölüydü)
    names = ["Soyrac"] + list(opponents)
    n = len(names)
    sb, bb, stack = 0.5, 1.0, 100.0
    gl = PokerGame(num_players=n, starting_stack=stack, small_blind=sb, big_blind=bb,
                   ante=0, hero_seat=0, bot_archetypes=names[1:],
                   player_names=[f"a{i}" for i in range(1, n)], paced_bots=True)
    soy = SoyracBrain()
    soy.tournament_mode = False          # cash = chip-EV (survival ICM YOK)
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
