"""Vectorized turn+river CFR — numpy, hızlı.  ⚠️ DENEYSEL — UI'ya BAĞLI DEĞİL.

nested_solver.py turn+river'ı saf-Python pair×river döngüsü ile çözer (~27s).
Bu modül AYNI CFR matematiğini numpy tensörlerine taşır → ~28x hızlı:
  - showdown işaretleri [rivers × hero × villain] tensörü Wr,
  - villain value pass'i ZERO-SUM negasyonla kurulur,
  - river chance-node'unun per-pair kart-removal normalizasyonu (1/nlive)
    "efektif reach" tensörüne gömülür.

Aksiyon ağacı nested_solver ile birebir (hero OOP, tek bet size):
  TURN  hero CHECK|BET → villain → (river chance) → RIVER subtree (CHECK|BET ...)
Üç river-context: A=(x,x), B=(x,b,c), C=(b,c). pot/yatırım simetrik (Hr=Pr/2).

⚠️ BİLİNEN HATA (çözülmedi) — ÇOK-EL HERO RANGE'İNDE VALUE DAĞILIMI YANLIŞ:
  - DOĞRU çalışan kısım: tek-villain / küçük spotlar — nested ile oyun-değeri
    eşleşir; nut-el (trip A) trap-check'i doğru, board-collision combo filtresi
    doğru (phantom-combo bug'ı düzeltildi).
  - HATALI: çok-el hero range'inde betting frekansı el-bazında yanlış dağılıyor
    (ör. H=[AA,KK,QQ] vs [JJ,AK], Ah Kc 8d 3s: nested KK %34/QQ %34 verirken
    bu solver KK %0/QQ %66 → trip-kings hiç bet etmiyor, underpair en çok ediyor).
  Kök neden henüz bulunamadı (muhtemelen çok-el villain reach / villain value
  pass tutarlılığı). DÜZELENE KADAR UI'DA KULLANMA — turn için nested_solver
  (yavaş ama doğru) veya TexasSolver (✅ EXACT) kullan.

Algoritma: vanilla CFR + regret-matching (Zinkevich 2007). Kendi implementation.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from app.engine.evaluator import _compare_hands, evaluate_best_hand
from app.engine.hand_state import Card, RANKS, SUITS, cards_from_str
from app.poker.mc_equity import expand_range


@dataclass
class TurnStrategy:
    hand_label: str
    turn_check: float = 0.0
    turn_bet: float = 0.0


@dataclass
class TurnResult:
    hero: List[TurnStrategy]
    iterations: int
    elapsed_ms: int
    exploitability: float = 0.0
    # Solver Sandbox _on_solved uyumluluğu (river_solver.HandStrategy benzeri)
    hero_strategies: list = field(default_factory=list)
    villain_strategies: list = field(default_factory=list)


def _rm(reg: np.ndarray) -> np.ndarray:
    """Regret-matching over last axis (size 2)."""
    pos = np.maximum(reg, 0.0)
    s = pos.sum(axis=-1, keepdims=True)
    return np.where(s > 0, pos / np.where(s > 0, s, 1.0), 0.5)


class VectorTurnRiverSolver:
    """numpy-vectorized turn+river CFR — hızlı + EXACT (HU, hero OOP)."""

    def __init__(self, hero_range, villain_range, board_turn,
                 pot: float = 100.0, bet_frac: float = 0.66):
        if hero_range and isinstance(hero_range[0], str):
            hero_range = expand_range(hero_range)
        if villain_range and isinstance(villain_range[0], str):
            villain_range = expand_range(villain_range)
        if isinstance(board_turn, str):
            board_turn = cards_from_str(board_turn)
        assert len(board_turn) == 4, "Turn board 4 kart olmalı (flop+turn)"

        self.board = board_turn
        self.pot0 = float(pot)
        self.bet_frac = float(bet_frac)
        self.tbet = self.pot0 * self.bet_frac

        board_set = {(c.rank, c.suit) for c in board_turn}
        # KRİTİK: board kartıyla çakışan (imkansız) combo'ları ele — nested_solver
        # gibi. Aksi halde phantom eller stratejiyi ve oyun-değerini bozar.
        hero_range = [h for h in hero_range
                      if not ({(h[0].rank, h[0].suit), (h[1].rank, h[1].suit)} & board_set)]
        villain_range = [v for v in villain_range
                         if not ({(v[0].rank, v[0].suit), (v[1].rank, v[1].suit)} & board_set)]
        self.hero = hero_range
        self.vill = villain_range

        nh, nv = len(hero_range), len(villain_range)
        self.nh, self.nv = nh, nv

        hero_codes = [{(h[0].rank, h[0].suit), (h[1].rank, h[1].suit)} for h in hero_range]
        vill_codes = [{(v[0].rank, v[0].suit), (v[1].rank, v[1].suit)} for v in villain_range]

        # Turn-level collision matrix C0[i,j] = 1 if hero[i] ⟂ villain[j] (no shared card)
        C0 = np.zeros((nh, nv))
        for i in range(nh):
            for j in range(nv):
                if not (hero_codes[i] & vill_codes[j]):
                    C0[i, j] = 1.0
        self.C0 = C0

        # Rivers = tüm board-dışı kartlar
        rivers = [Card(r, s) for r in RANKS for s in SUITS
                  if (r, s) not in board_set]
        self.rivers = rivers
        R = len(rivers)
        self.R = R

        # Wr[r,i,j] ∈ {+1,0,-1} (hero kazanır=+1), Lr[r,i,j] ∈ {0,1} (oynanabilir)
        Wr = np.zeros((R, nh, nv))
        Lr = np.zeros((R, nh, nv))
        for r, rc in enumerate(rivers):
            rkey = (rc.rank, rc.suit)
            full = board_turn + [rc]
            hero_ev = []
            hero_dead = []
            for i, h in enumerate(hero_range):
                if rkey in hero_codes[i]:
                    hero_ev.append(None); hero_dead.append(True)
                else:
                    hero_ev.append(evaluate_best_hand([h[0], h[1]], full))
                    hero_dead.append(False)
            vill_ev = []
            vill_dead = []
            for j, v in enumerate(villain_range):
                if rkey in vill_codes[j]:
                    vill_ev.append(None); vill_dead.append(True)
                else:
                    vill_ev.append(evaluate_best_hand([v[0], v[1]], full))
                    vill_dead.append(False)
            for i in range(nh):
                if hero_dead[i]:
                    continue
                for j in range(nv):
                    if vill_dead[j] or (hero_codes[i] & vill_codes[j]):
                        continue
                    Lr[r, i, j] = 1.0
                    cmp = _compare_hands(hero_ev[i], vill_ev[j])
                    Wr[r, i, j] = 1.0 if cmp < 0 else (-1.0 if cmp > 0 else 0.0)
        self.Wr = Wr
        self.Lr = Lr
        nlive = Lr.sum(axis=0)                       # [nh,nv]
        self._nlive_safe = np.where(nlive > 0, nlive, 1.0)

        # Uniform combo weights
        self.r_h0 = np.ones(nh)
        self.r_v0 = np.ones(nv)

        # Turn-level regret/strategy-sum
        self.reg_h_turn = np.zeros((nh, 2))      # check, bet
        self.reg_h_turn_vb = np.zeros((nh, 2))   # call, fold  (vs villain turn bet)
        self.reg_v_turn_ac = np.zeros((nv, 2))   # check, bet   (after hero check)
        self.reg_v_turn_vb = np.zeros((nv, 2))   # call, fold   (vs hero turn bet)
        self.ss_h_turn = np.zeros((nh, 2))
        self.ss_h_turn_vb = np.zeros((nh, 2))
        self.ss_v_turn_ac = np.zeros((nv, 2))
        self.ss_v_turn_vb = np.zeros((nv, 2))

        # River-level regret per context (A,B,C): [R, hands, 2]
        self.ctx = {}
        for name in ("A", "B", "C"):
            self.ctx[name] = {
                "reg_hR": np.zeros((R, nh, 2)),    # check, bet
                "reg_hRvb": np.zeros((R, nh, 2)),  # call, fold (vs villain river bet)
                "reg_vRac": np.zeros((R, nv, 2)),  # check, bet (after hero river check)
                "reg_vRvb": np.zeros((R, nv, 2)),  # call, fold (vs hero river bet)
            }

    # ── RIVER SUBTREE (vectorized, EXACT) ─────────────────────────────
    def _river_step(self, ctx_name: str, Pr: float, rh: np.ndarray, rv: np.ndarray):
        """Bir river-context için CFR adımı.

        rh[nh], rv[nv]: turn seviyesinden river-girişine reach.
        Döner: (hero_cfv[nh], vill_cfv[nv]) — chance-ortalamalı, reach-ağırlıklı,
        ZERO-SUM hero/villain karşı-olgusal değerleri (yatırım net).
        """
        st = self.ctx[ctx_name]
        Wr, Lr = self.Wr, self.Lr
        half = Pr / 2.0
        rbet = Pr * self.bet_frac

        # showdown net payoff (hero perspektifi) — Wr*amt
        sd_check = Wr * half                      # [R,nh,nv]  pot Pr, hero inv Pr/2
        sd_betcall = Wr * (half + rbet)           # pot Pr+2rbet, hero inv Pr/2+rbet

        # Strategies [R,hands,2]
        shR = _rm(st["reg_hR"])
        shRvb = _rm(st["reg_hRvb"])
        svRac = _rm(st["reg_vRac"])
        svRvb = _rm(st["reg_vRvb"])

        # Efektif reach tensörleri (chance 1/nlive + collision Lr gömülü)
        # Rv_eff[r,i,j] = rv[j]*Lr/nlive   (hero infosetleri için karşı reach)
        # Rh_eff[r,i,j] = rh[i]*Lr/nlive   (villain infosetleri için karşı reach)
        norm = Lr / self._nlive_safe[None, :, :]            # [R,nh,nv]
        Rv_eff = norm * rv[None, None, :]                   # broadcast over i
        Rh_eff = norm * rh[None, :, None]                   # broadcast over j

        # ── HERO river infoset değerleri (vj üzerinden kontraksiyon) ──
        svRac_c = svRac[:, :, 0]; svRac_b = svRac[:, :, 1]  # [R,nv]
        svRvb_c = svRvb[:, :, 0]; svRvb_b = svRvb[:, :, 1]
        # villain check → showdown(Pr)
        chk_vcheck = np.einsum('rij,rj,rij->ri', Rv_eff, svRac_c, sd_check)
        # villain bet → hero call/fold
        call_term = np.einsum('rij,rj,rij->ri', Rv_eff, svRac_b, sd_betcall)
        betmass = np.einsum('rij,rj->ri', Rv_eff, svRac_b)
        hvb_call = call_term
        hvb_fold = -half * betmass
        hvb_node = shRvb[:, :, 0] * hvb_call + shRvb[:, :, 1] * hvb_fold
        check_val = chk_vcheck + hvb_node
        # hero bet → villain call/fold
        bcall = np.einsum('rij,rj,rij->ri', Rv_eff, svRvb_c, sd_betcall)
        bfoldmass = np.einsum('rij,rj->ri', Rv_eff, svRvb_b)
        bet_val = bcall + half * bfoldmass
        node_hR = shR[:, :, 0] * check_val + shR[:, :, 1] * bet_val

        # hero regret + strat-sum
        st["reg_hR"][:, :, 0] += check_val - node_hR
        st["reg_hR"][:, :, 1] += bet_val - node_hR
        st["reg_hRvb"][:, :, 0] += hvb_call - hvb_node
        st["reg_hRvb"][:, :, 1] += hvb_fold - hvb_node

        # ── VILLAIN river infoset değerleri (hi üzerinden, ZERO-SUM negasyon) ──
        shR_c = shR[:, :, 0]; shR_b = shR[:, :, 1]            # [R,nh]
        shRvb_c = shRvb[:, :, 0]; shRvb_b = shRvb[:, :, 1]
        # villain check → showdown(Pr): villain value = -sd_check
        v_check = np.einsum('rij,ri,rij->rj', Rh_eff, shR_c, -sd_check)
        # villain bet → hero call/fold
        v_bet_call = np.einsum('rij,ri,ri,rij->rj', Rh_eff, shR_c, shRvb_c, -sd_betcall)
        v_bet_foldmass = np.einsum('rij,ri,ri->rj', Rh_eff, shR_c, shRvb_b)
        v_bet = v_bet_call + half * v_bet_foldmass            # hero fold → villain +Pr/2
        node_vRac = svRac_c * v_check + svRac_b * v_bet
        st["reg_vRac"][:, :, 0] += v_check - node_vRac
        st["reg_vRac"][:, :, 1] += v_bet - node_vRac
        # villain vs hero bet: call/fold
        v_call = np.einsum('rij,ri,rij->rj', Rh_eff, shR_b, -sd_betcall)
        v_betmass = np.einsum('rij,ri->rj', Rh_eff, shR_b)
        v_fold = -half * v_betmass                            # villain fold → -Pr/2
        node_vRvb = svRvb_c * v_call + svRvb_b * v_fold
        st["reg_vRvb"][:, :, 0] += v_call - node_vRvb
        st["reg_vRvb"][:, :, 1] += v_fold - node_vRvb

        # average-strategy sums (own reach; chance hariç)
        st.setdefault("ss_hR", np.zeros_like(shR))
        st.setdefault("ss_hRvb", np.zeros_like(shRvb))
        st.setdefault("ss_vRac", np.zeros_like(svRac))
        st.setdefault("ss_vRvb", np.zeros_like(svRvb))
        st["ss_hR"] += rh[None, :, None] * shR
        st["ss_hRvb"] += (rh[None, :] * shR_c)[:, :, None] * shRvb
        st["ss_vRac"] += rv[None, :, None] * svRac
        st["ss_vRvb"] += rv[None, :, None] * svRvb

        # ── Turn'e dönen karşı-olgusal değerler (river kökü) ──
        # hero_cfv[i] = Σ_r node_hR  (chance 1/nlive + villain reach zaten gömülü)
        hero_cfv = node_hR.sum(axis=0)
        # vill_cfv[j]: river kökünde HERO ilk konuşur → villain'in tek infoseti yok,
        # bu yüzden hero-kök oyun değeri g'yi (-1) ile hero-reach üzerinden kontrakte
        # ederiz. AYNI iterasyonun (update-öncesi) stratejilerini kullanır — tutarlı.
        # g[r,i,j] = hero river-kök oyun değeri (pair başına)
        hvb_g = shRvb[:, :, None, 0] * sd_betcall + shRvb[:, :, None, 1] * (-half)
        check_part = (svRac[:, None, :, 0] * sd_check + svRac[:, None, :, 1] * hvb_g)
        bet_part = (svRvb[:, None, :, 0] * sd_betcall + svRvb[:, None, :, 1] * half)
        g = shR[:, :, None, 0] * check_part + shR[:, :, None, 1] * bet_part
        vill_cfv = np.einsum('rij,rij->j', Rh_eff, -g)
        return hero_cfv, vill_cfv

    # ── SOLVE ─────────────────────────────────────────────────────────
    def solve(self, iterations: int = 200) -> TurnResult:
        t0 = time.time()
        P = self.pot0; tbet = self.tbet
        half0 = P / 2.0
        r_h0, r_v0 = self.r_h0, self.r_v0
        C0 = self.C0
        self.ev_trace = []   # her iterasyon hero root toplam değeri (yakınsama tanısı)

        for _ in range(iterations):
            sh = _rm(self.reg_h_turn)            # [nh] check,bet
            shvb_T = _rm(self.reg_h_turn_vb)     # call,fold
            svac_T = _rm(self.reg_v_turn_ac)     # check,bet
            svvb_T = _rm(self.reg_v_turn_vb)     # call,fold

            # Reaches into river contexts
            rh_A = r_h0 * sh[:, 0]
            rv_A = r_v0 * svac_T[:, 0]
            rh_B = r_h0 * sh[:, 0] * shvb_T[:, 0]
            rv_B = r_v0 * svac_T[:, 1]
            rh_C = r_h0 * sh[:, 1]
            rv_C = r_v0 * svvb_T[:, 0]

            hcfv_A, vcfv_A = self._river_step("A", P, rh_A, rv_A)
            hcfv_B, vcfv_B = self._river_step("B", P + 2 * tbet, rh_B, rv_B)
            hcfv_C, vcfv_C = self._river_step("C", P + 2 * tbet, rh_C, rv_C)

            # Turn-level collision-based fold/showdown-less terms
            hfold = -half0 * (C0 @ (r_v0 * svac_T[:, 1]))
            bet_fold = half0 * (C0 @ (r_v0 * svvb_T[:, 1]))
            vbet_fold = half0 * (C0.T @ (r_h0 * sh[:, 0] * shvb_T[:, 1]))
            v_fold_turn = -half0 * (C0.T @ (r_h0 * sh[:, 1]))

            # ── HERO turn ──
            hvb_call_T = hcfv_B
            hvb_fold_T = hfold
            hvb_node_T = shvb_T[:, 0] * hvb_call_T + shvb_T[:, 1] * hvb_fold_T
            check_val_T = hcfv_A + hvb_node_T
            bet_val_T = bet_fold + hcfv_C
            node_hT = sh[:, 0] * check_val_T + sh[:, 1] * bet_val_T
            self.ev_trace.append(float((r_h0 * node_hT).sum()))
            self.reg_h_turn[:, 0] += check_val_T - node_hT
            self.reg_h_turn[:, 1] += bet_val_T - node_hT
            self.ss_h_turn += r_h0[:, None] * sh
            self.reg_h_turn_vb[:, 0] += hvb_call_T - hvb_node_T
            self.reg_h_turn_vb[:, 1] += hvb_fold_T - hvb_node_T
            self.ss_h_turn_vb += (r_h0 * sh[:, 0])[:, None] * shvb_T

            # ── VILLAIN turn ──
            v_check_T = vcfv_A
            v_bet_T = vbet_fold + vcfv_B
            node_vac_T = svac_T[:, 0] * v_check_T + svac_T[:, 1] * v_bet_T
            self.reg_v_turn_ac[:, 0] += v_check_T - node_vac_T
            self.reg_v_turn_ac[:, 1] += v_bet_T - node_vac_T
            self.ss_v_turn_ac += r_v0[:, None] * svac_T
            v_call_T = vcfv_C
            node_vvb_T = svvb_T[:, 0] * v_call_T + svvb_T[:, 1] * v_fold_turn
            self.reg_v_turn_vb[:, 0] += v_call_T - node_vvb_T
            self.reg_v_turn_vb[:, 1] += v_fold_turn - node_vvb_T
            self.ss_v_turn_vb += r_v0[:, None] * svvb_T

        # Average hero turn strategy
        s = self.ss_h_turn.sum(axis=1, keepdims=True)
        ah = np.where(s > 0, self.ss_h_turn / np.where(s > 0, s, 1.0), 0.5)
        from app.poker.river_solver import HandStrategy
        hero_strats = []
        hero_compat = []
        for i, (c1, c2) in enumerate(self.hero):
            label = f"{c1.rank}{c1.suit}{c2.rank}{c2.suit}"
            tc = round(100 * ah[i, 0], 1)
            tb = round(100 * ah[i, 1], 1)
            hero_strats.append(TurnStrategy(hand_label=label,
                                            turn_check=tc, turn_bet=tb))
            hero_compat.append(HandStrategy(
                hand_label=label, bet_freq=tb, check_freq=tc,
                call_freq_vs_bet=0.0, fold_freq_vs_bet=0.0))
        return TurnResult(
            hero=hero_strats,
            iterations=iterations,
            elapsed_ms=int((time.time() - t0) * 1000),
            hero_strategies=hero_compat,
            villain_strategies=[],
        )
