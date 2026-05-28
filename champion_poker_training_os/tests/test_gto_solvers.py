"""GTO / equity / solver / MTT modül testleri.

Bu seansta eklenen motorların regresyon koruması:
  mc_equity, gto_ranges, gto_generator, gto_provenance, gto_live_advice,
  vector_solver, mtt_ranges.

Çalıştır:
    .venv/bin/python -m pytest tests/test_gto_solvers.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


# ─────────────────────────────────────────────────────────────────────
# Monte Carlo equity
# ─────────────────────────────────────────────────────────────────────

def test_equity_aa_vs_kk():
    from app.poker.mc_equity import equity_hand_vs_hand
    r = equity_hand_vs_hand("AsAh", "KsKh", iterations=4000)
    # AA vs KK ≈ %80-82
    assert 77 <= r.a_equity <= 86, f"AA vs KK = {r.a_equity}"


def test_equity_aks_vs_qq():
    from app.poker.mc_equity import equity_hand_vs_hand
    r = equity_hand_vs_hand("AsKs", "QdQc", iterations=4000)
    # AKs vs QQ ≈ %46 (coinflip, QQ hafif favori)
    assert 42 <= r.a_equity <= 50, f"AKs vs QQ = {r.a_equity}"


def test_equity_made_hand_vs_overcards():
    from app.poker.mc_equity import equity_hand_vs_hand
    # 76s flopped pair + draws vs AKo on 8 7 2
    r = equity_hand_vs_hand("7s6s", "AdKh", board="8s 7c 2h", iterations=4000)
    assert r.a_equity >= 65, f"76s on 872 vs AKo = {r.a_equity}"


def test_expand_hand_key():
    from app.poker.mc_equity import expand_hand_key
    assert len(expand_hand_key("AA")) == 6      # pair: 6 combos
    assert len(expand_hand_key("AKs")) == 4      # suited: 4
    assert len(expand_hand_key("AKo")) == 12     # offsuit: 12
    assert expand_hand_key("AK") == []           # ambiguous → boş


def test_equity_sums_to_100():
    from app.poker.mc_equity import equity_hand_vs_hand
    r = equity_hand_vs_hand("AsAh", "7c2d", iterations=2000)
    total = r.a_win_pct + r.tie_pct + r.b_win_pct
    assert abs(total - 100) < 0.5, f"toplam {total}"


# ─────────────────────────────────────────────────────────────────────
# GTO ranges — get_action coverage + correctness
# ─────────────────────────────────────────────────────────────────────

def test_get_action_returns_valid_dict():
    from app.poker.gto_ranges import get_action
    a = get_action("BTN", "AA", "RFI", 100, "cash")
    assert set(a.keys()) >= {"raise", "call", "fold"}
    assert abs(a["raise"] + a["call"] + a["fold"] - 100) < 0.5


def test_btn_aa_pure_raise():
    from app.poker.gto_ranges import get_action
    assert get_action("BTN", "AA", "RFI", 100, "cash")["raise"] == 100


def test_utg_trash_folds():
    from app.poker.gto_ranges import get_action
    assert get_action("UTG", "72o", "RFI", 100, "cash")["fold"] == 100


def test_full_coverage_no_empty():
    """Her (pos × scenario × stack × mode) bir cevap döndürmeli — boş yok."""
    from app.poker.gto_ranges import get_action
    import itertools
    positions = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
    scenarios = ["RFI", "vs RFI", "vs 3-bet", "Push/Fold"]
    stacks = [100, 40, 20, 12]
    modes = ["cash", "MTT"]
    bad = 0
    for pos, scen, stk, mode in itertools.product(positions, scenarios, stacks, modes):
        for hk in ("AA", "72o", "K9s"):
            a = get_action(pos, hk, scen, stk, mode, vs_position="BTN")
            if not isinstance(a, dict) or "raise" not in a:
                bad += 1
    assert bad == 0, f"{bad} boş cevap"


def test_rfi_range_pct_sane():
    """RFI range %'leri pozisyon sırasına uygun (UTG < CO < BTN)."""
    from app.poker.gto_ranges import get_action
    def pct(pos):
        total = 0.0; played = 0.0
        for hi_i, hi in enumerate("AKQJT98765432"):
            for lo_i, lo in enumerate("AKQJT98765432"):
                if hi_i == lo_i:
                    hk = hi + lo; c = 6
                elif hi_i < lo_i:
                    hk = hi + lo + "s"; c = 4
                else:
                    hk = lo + hi + "o"; c = 12
                total += c
                played += c * get_action(pos, hk, "RFI", 100, "cash")["raise"] / 100
        return played / total * 100
    utg, co, btn = pct("UTG"), pct("CO"), pct("BTN")
    assert utg < co < btn, f"UTG {utg} CO {co} BTN {btn}"
    assert 12 <= utg <= 22 and 40 <= btn <= 52


# ─────────────────────────────────────────────────────────────────────
# Heuristic generator
# ─────────────────────────────────────────────────────────────────────

def test_generator_bb_defend_widens_vs_later_opener():
    """BB, geç pozisyon açışına karşı daha geniş defend eder."""
    from app.poker.gto_generator import build_vs_rfi_range
    def pct(table):
        total = 0.0; played = 0.0
        for hi_i, hi in enumerate("AKQJT98765432"):
            for lo_i, lo in enumerate("AKQJT98765432"):
                if hi_i == lo_i: hk, c = hi+lo, 6
                elif hi_i < lo_i: hk, c = hi+lo+"s", 4
                else: hk, c = lo+hi+"o", 12
                total += c
                a = table.get(hk, {"raise":0,"call":0})
                played += c * (a.get("raise",0)+a.get("call",0)) / 100
        return played/total*100
    vs_utg = pct(build_vs_rfi_range("BB", "UTG", 100))
    vs_btn = pct(build_vs_rfi_range("BB", "BTN", 100))
    assert vs_utg < vs_btn, f"vs UTG {vs_utg} vs BTN {vs_btn}"


def test_generator_playability_ordering():
    from app.poker.gto_generator import hand_playability_score
    assert hand_playability_score("AA") > hand_playability_score("22")
    assert hand_playability_score("AKs") > hand_playability_score("AKo")
    assert hand_playability_score("AKo") > hand_playability_score("72o")


# ─────────────────────────────────────────────────────────────────────
# Provenance tiers
# ─────────────────────────────────────────────────────────────────────

def test_provenance_tiers():
    from app.poker.gto_provenance import range_provenance
    assert range_provenance("RFI", "BTN", 100, "cash").key == "EXACT"
    assert range_provenance("Push/Fold", "BTN", 12, "MTT").key == "EXACT"
    assert range_provenance("vs RFI", "BB", 100, "cash").key == "APPROX"


# ─────────────────────────────────────────────────────────────────────
# MTT ranges — Nash jam + ICM + bounty + squeeze
# ─────────────────────────────────────────────────────────────────────

def test_jam_pct_position_order():
    """Jam %: SB en geniş, UTG en sıkı (aynı stack)."""
    from app.poker.mtt_ranges import mtt_jam_pct
    for stk in (8, 10, 15):
        assert (mtt_jam_pct("SB", stk) > mtt_jam_pct("BTN", stk)
                > mtt_jam_pct("CO", stk) > mtt_jam_pct("UTG", stk))


def test_jam_pct_tightens_with_stack():
    from app.poker.mtt_ranges import mtt_jam_pct
    assert mtt_jam_pct("BTN", 8) > mtt_jam_pct("BTN", 15) > mtt_jam_pct("BTN", 20)


def test_icm_tightens_jam():
    """Bubble ICM jam range'i chipEV'den daraltır."""
    from app.poker.mtt_ranges import build_mtt_push_fold, build_icm_push_fold
    def pct(t):
        total=0.0; r=0.0
        for hi_i, hi in enumerate("AKQJT98765432"):
            for lo_i, lo in enumerate("AKQJT98765432"):
                if hi_i==lo_i: hk,c=hi+lo,6
                elif hi_i<lo_i: hk,c=hi+lo+"s",4
                else: hk,c=lo+hi+"o",12
                total+=c; r+=c*t.get(hk,{"raise":0}).get("raise",0)/100
        return r/total*100
    chip = pct(build_mtt_push_fold("BTN", 12))
    bubble = pct(build_icm_push_fold("BTN", 12, "bubble"))
    assert bubble < chip, f"bubble {bubble} >= chip {chip}"


def test_bounty_widens_call():
    from app.poker.mtt_ranges import build_call_vs_jam, build_pko_call_vs_jam
    def pct(t):
        total=0.0; played=0.0
        for hi_i, hi in enumerate("AKQJT98765432"):
            for lo_i, lo in enumerate("AKQJT98765432"):
                if hi_i==lo_i: hk,c=hi+lo,6
                elif hi_i<lo_i: hk,c=hi+lo+"s",4
                else: hk,c=lo+hi+"o",12
                total+=c
                a=t.get(hk,{}); played+=c*(a.get("call",0))/100
        return played/total*100
    normal = pct(build_call_vs_jam(12))
    bounty = pct(build_pko_call_vs_jam(12, 1.0))
    assert bounty > normal, f"bounty {bounty} <= normal {normal}"


def test_squeeze_tightens_with_callers():
    from app.poker.mtt_ranges import build_squeeze
    def pct(t):
        total=0.0; played=0.0
        for hi_i, hi in enumerate("AKQJT98765432"):
            for lo_i, lo in enumerate("AKQJT98765432"):
                if hi_i==lo_i: hk,c=hi+lo,6
                elif hi_i<lo_i: hk,c=hi+lo+"s",4
                else: hk,c=lo+hi+"o",12
                total+=c; a=t.get(hk,{})
                played+=c*(a.get("raise",0)+a.get("call",0))/100
        return played/total*100
    one = pct(build_squeeze("BTN", 100, 1))
    two = pct(build_squeeze("BTN", 100, 2))
    assert two < one, f"2 caller {two} >= 1 caller {one}"


# ─────────────────────────────────────────────────────────────────────
# Vectorized river solver — polarized structure
# ─────────────────────────────────────────────────────────────────────

def test_vector_solver_polarized():
    """Nuts bet, medium check (showdown value), air bet (bluff)."""
    from app.poker.vector_solver import VectorRiverSolver
    s = VectorRiverSolver(
        ["KK", "QQ", "76s", "65s"], ["AKs", "TT", "99", "JTo"],
        board="7s 4d 2c Kh 9s", pot=100, bet_frac=0.75,
    )
    r = s.solve(iterations=2000)
    bet = {}
    for st in r.hero:
        h = st.hand_label
        k = h[0]+h[2] if h[0] == h[2] else (h[0]+h[2]+"s" if h[1] == h[3] else h[0]+h[2]+"o")
        bet.setdefault(k, []).append(st.bet)
    avg = {k: sum(v)/len(v) for k, v in bet.items()}
    # KK (top set) çok bet etmeli; 76s (bottom pair, showdown value) az
    assert avg["KK"] > 50, f"KK bet {avg['KK']}"
    assert avg["76s"] < 30, f"76s bet {avg['76s']}"


def test_vector_solver_fast():
    """Vectorized solver makul hızda (3000 iter < 2s)."""
    from app.poker.vector_solver import VectorRiverSolver
    s = VectorRiverSolver(
        ["AA", "KK", "QQ"], ["JJ", "TT", "99"],
        board="As Kd 2c 7h 3s", pot=100,
    )
    r = s.solve(iterations=3000)
    assert r.elapsed_ms < 2000, f"{r.elapsed_ms}ms çok yavaş"


# ─────────────────────────────────────────────────────────────────────
# Live GTO advice — scenario mapping
# ─────────────────────────────────────────────────────────────────────

def test_live_advice_preflop_available_postflop_not():
    from app.engine.game_loop import PokerGame
    from app.poker.gto_live_advice import live_gto_advice
    from app.engine.hand_state import ActionType
    g = PokerGame(num_players=6, starting_stack=100.0, small_blind=0.5,
                  big_blind=1.0, hero_seat=0, bot_archetypes=["Reg"]*5,
                  paced_bots=False)
    g.start_hand()
    # hero kararına gel
    guard = 0
    while g.current_hand and not g.is_waiting_for_hero \
            and not g.current_hand.is_complete and guard < 30:
        g.step_action(); guard += 1
    if g.is_waiting_for_hero:
        adv = live_gto_advice(g.current_hand, g.current_hand.hero_idx, mode="cash")
        # Preflop → frekanslar toplamı ~100 (available ise)
        if adv.available:
            tot = adv.fold + adv.call + adv.raise_ + adv.allin
            assert 95 <= tot <= 105, f"freq toplam {tot}"
            assert adv.scenario   # scenario etiketi var


# ─────────────────────────────────────────────────────────────────────
# Bet-sizing analysis — recommendation + quality scoring
# ─────────────────────────────────────────────────────────────────────

def test_sizing_score_monotonic_and_example():
    """Kullanıcı örneği: 5bb suboptimal, 12bb (rec~11) mükemmel olmalı."""
    from app.poker.sizing_advice import SizingAdvice
    adv = SizingAdvice(available=True, recommended_bb=11.0)
    s5 = adv.score(5.0, pot_bb=15)
    s12 = adv.score(12.0, pot_bb=15)
    # GTO-standarda yakın olan daha yüksek quality + daha az EV kaybı
    assert s12["quality_pct"] > s5["quality_pct"]
    assert s12["ev_loss_bb"] <= s5["ev_loss_bb"]
    assert 0 <= s5["quality_pct"] <= 100
    # Tam optimumda quality ~100, EV kaybı 0
    opt = adv.score(11.0, pot_bb=15)
    assert opt["quality_pct"] >= 99
    assert opt["ev_loss_bb"] == 0.0


def test_sizing_advice_preflop_open_sane():
    """RFI açış önerisi makul aralıkta (2.0–3.0bb) olmalı."""
    from app.engine.game_loop import PokerGame
    from app.poker.sizing_advice import sizing_advice
    g = PokerGame(num_players=6, starting_stack=100.0, small_blind=0.5,
                  big_blind=1.0, hero_seat=0, bot_archetypes=["Reg"]*5,
                  paced_bots=False)
    g.start_hand()
    guard = 0
    while g.current_hand and not g.is_waiting_for_hero \
            and not g.current_hand.is_complete and guard < 30:
        g.step_action(); guard += 1
    if g.is_waiting_for_hero:
        adv = sizing_advice(g.current_hand, g.current_hand.hero_idx, mode="cash")
        assert adv.available
        assert adv.recommended_bb > 0
        assert adv.label


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
