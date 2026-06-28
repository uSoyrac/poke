"""Kullanıcı: 200/500/1000 alan × 90/120/150/200bb karma stack'lerle ONLARCA turnuva GERÇEKTEN oyna,
sonra sistemin EN ÇOK KAZANDIĞI/KAYBETTİĞİ elleri pozisyon-pozisyon, el-el, aşama-aşama, preflop-bağlam
(RFI / vs-RFI call / squeeze / 3-bet jam / vs-3bet 4-bet ...) ile listele.

H._play_one_hand'i loglayan sürümle değiştirir → H.run_mtt el-el oynar → her Soyrac-eli kaydedilir.
Soyrac injection + field_fn soyrac_realistic_mtt'ten gelir (GL.BotBrain=_factory, %12 Soyrac)."""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.soyrac_realistic_mtt as RM        # injection + _make_field_fn + _payout
import app.simulator.headless_mtt as H
from app.engine.bot_brain import BOT_ARCHETYPES, BotBrain
from app.engine.game_loop import PokerGame
from app.engine.hand_state import ActionType, Street
from app.engine.bot_brain import hand_key

_LOG = []
_CTX = {"field": 0, "depth": 0}


def _preflop_situation(h, seat):
    """h.actions → (bağlam, hero_aksiyon) → 'vs-RFI call' gibi insan-okunur durum."""
    raises = calls = 0
    my = None
    for a in h.actions:
        if getattr(a, "street", None) != Street.PREFLOP:
            continue
        if a.player_idx == seat:
            if a.action_type in (ActionType.RAISE, ActionType.ALL_IN, ActionType.CALL,
                                 ActionType.FOLD, ActionType.BET, ActionType.CHECK):
                my = a.action_type
                break
        elif a.action_type in (ActionType.RAISE, ActionType.ALL_IN, ActionType.BET):
            raises += 1
        elif a.action_type == ActionType.CALL:
            calls += 1
    A = ActionType
    # hero aksiyon etiketi
    if my in (A.ALL_IN,):
        ha = "JAM"
    elif my == A.RAISE:
        ha = "RAISE"
    elif my == A.CALL:
        ha = "CALL"
    elif my in (A.CHECK,):
        ha = "CHECK"
    else:
        ha = "FOLD"
    # bağlam
    if raises == 0 and calls == 0:
        ctx = "RFI"            # ilk giren
        sit = {"RAISE": "RFI-aç", "JAM": "RFI-jam", "CALL": "limp", "CHECK": "BB-bedava",
               "FOLD": "fold"}.get(ha, ha)
    elif raises == 0 and calls >= 1:
        ctx = f"limp×{calls}"
        sit = {"RAISE": "iso-raise", "JAM": "iso-jam", "CALL": "over-limp",
               "CHECK": "BB-check", "FOLD": "fold"}.get(ha, ha)
    elif raises == 1 and calls == 0:
        ctx = "vs-RFI"
        sit = {"CALL": "vs-RFI call", "RAISE": "3-bet", "JAM": "3-bet-jam", "FOLD": "fold"}.get(ha, ha)
    elif raises == 1 and calls >= 1:
        ctx = f"vs-RFI+call×{calls}"
        sit = {"CALL": "over-call", "RAISE": "squeeze", "JAM": "squeeze-jam", "FOLD": "fold"}.get(ha, ha)
    elif raises == 2:
        ctx = "vs-3bet"
        sit = {"CALL": "vs-3bet call", "RAISE": "4-bet", "JAM": "4-bet-jam", "FOLD": "fold"}.get(ha, ha)
    else:
        ctx = "vs-4bet+"
        sit = {"CALL": "vs-4bet call", "JAM": "5-bet-jam", "RAISE": "5-bet", "FOLD": "fold"}.get(ha, ha)
    return ctx, sit, ha


def _play_one_hand_logged(table, sb, bb, ante, button, icm=0.0):
    n = len(table)
    if n < 2:
        return
    archs = [p.arch for p in table]
    gl = PokerGame(num_players=n, starting_stack=H._START_CHIPS, small_blind=sb, big_blind=bb,
                   ante=ante, hero_seat=0, bot_archetypes=archs[1:],
                   player_names=[f"p{p.pid}" for p in table[1:]], paced_bots=True)
    for i, p in enumerate(table):
        gl.players[i].stack = p.stack
    gl.dealer_idx = button % n
    hero_brain = BotBrain(BOT_ARCHETYPES.get(archs[0], BOT_ARCHETYPES["Balanced Reg"]))
    hero_brain.tournament_mode = True
    for b in gl.bots.values():
        b.tournament_mode = True
    if icm > 0:
        hero_brain.icm_pressure = icm
        for b in gl.bots.values():
            b.icm_pressure = icm
    sb_before = [p.stack for p in table]
    gl.start_hand()
    guard = 0
    while guard < 600:
        guard += 1
        hh = gl.current_hand
        if hh and hh.is_complete:
            break
        prog = gl.step_action()
        if gl.is_waiting_for_hero:
            cur = gl.current_hand
            at, amt = hero_brain.decide(cur, cur.hero_idx)
            gl.hero_act(at, amt)
        elif not prog:
            break
    h = gl.current_hand
    for i, p in enumerate(table):
        if p.arch != "Soyrac":
            continue
        try:
            profit = gl.players[i].stack - sb_before[i]
            hole = h.players[i].hole_cards
            hk = hand_key(hole[0], hole[1]) if hole and len(hole) >= 2 else "?"
            ctx, sit, ha = _preflop_situation(h, i)
            stk_bb = sb_before[i] / bb if bb else 0
            # voluntary olmayan (BB-bedava-fold yok ama fold-preflop kâr ~ -kör) elleri de tut;
            # ama profit≈0 ve fold-preflop'u gürültü → yalnız |profit|≥0.5bb VEYA gönüllü aksiyon
            if abs(profit / bb) < 0.5 and ha == "FOLD":
                continue
            _LOG.append({
                "field": _CTX["field"], "depth": _CTX["depth"],
                "stack_bb": round(stk_bb, 1), "pos": h.players[i].position,
                "hand": hk, "ctx": ctx, "sit": sit, "act": ha,
                "icm": round(icm, 2), "profit_bb": round(profit / bb, 2),
            })
        except Exception:
            pass
    for i, p in enumerate(table):
        p.stack = max(0.0, gl.players[i].stack)


def run_matrix(fields, depths, seeds, out_path):
    H._play_one_hand = _play_one_hand_logged          # HOOK
    H.realistic_mtt_mix = RM._make_field_fn("Düşük ($11-33)")
    if hasattr(__import__("tools.profile_sim", fromlist=["x"]), "realistic_mtt_mix"):
        import tools.profile_sim as PS
        PS.realistic_mtt_mix = H.realistic_mtt_mix
    total_t = 0
    for field in fields:
        for depth in depths:
            H._START_CHIPS = int(depth * 20)          # BB0=20 (PS._BB0)
            _CTX["field"], _CTX["depth"] = field, depth
            for s in range(seeds):
                H.run_mtt(field, seed=7000 + s)
                total_t += 1
            print(f"  field={field} depth={depth}bb: {seeds} turnuva ({len(_LOG)} el toplam)", flush=True)
    json.dump(_LOG, open(out_path, "w"))
    print(f"TOPLAM {total_t} turnuva, {len(_LOG)} Soyrac-eli → {out_path}", flush=True)


if __name__ == "__main__":
    FIELDS = [int(x) for x in os.environ.get("FIELDS", "200,500,1000").split(",")]
    DEPTHS = [int(x) for x in os.environ.get("DEPTHS", "90,120,150,200").split(",")]
    SEEDS = int(os.environ.get("SEEDS", "8"))
    OUT = os.environ.get("OUT", "/tmp/soyrac_hands_log.json")
    run_matrix(FIELDS, DEPTHS, SEEDS, OUT)
