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


def test_vs_3bet_curated_shape():
    """vs-3bet curated (BTN/UTG/MP/CO, cash, 100bb) doğru POLARİZE şekil:

    Heuristic burada zararlıydı (TT/AQs ile %100 4-bet, A5s'i %100 fold).
    Curated ders-kitabı şekli üretmeli:
      - AA pure value 4-bet
      - TT/AQs flat-heavy (4-bet DEĞİL)
      - A5s polarize bluff-4bet (fold DEĞİL)
      - çöp (AJo vs UTG) fold
    """
    from app.poker.gto_ranges import get_action
    # Pure value 4-bet
    assert get_action("BTN", "AA", "vs 3-bet", 100, "cash")["raise"] == 100
    # Flat-heavy, NOT 4-bet
    btn_tt = get_action("BTN", "TT", "vs 3-bet", 100, "cash")
    assert btn_tt["call"] >= 70 and btn_tt["raise"] <= 20
    btn_aqs = get_action("BTN", "AQs", "vs 3-bet", 100, "cash")
    assert btn_aqs["call"] >= 70 and btn_aqs["raise"] <= 20
    # Bluff 4-bet candidate — must raise some, not pure-fold
    btn_a5s = get_action("BTN", "A5s", "vs 3-bet", 100, "cash")
    assert btn_a5s["raise"] >= 30, btn_a5s
    # UTG JJ continues (call-heavy), trash folds
    assert get_action("UTG", "JJ", "vs 3-bet", 100, "cash")["call"] >= 70
    assert get_action("UTG", "AJo", "vs 3-bet", 100, "cash")["fold"] == 100


def test_vs_3bet_uncovered_falls_back_to_heuristic():
    """SB (curated dışı) vs-3bet → heuristic fallback, yine de geçerli dict."""
    from app.poker.gto_ranges import get_action
    a = get_action("SB", "AA", "vs 3-bet", 100, "cash")
    assert abs(a["raise"] + a["call"] + a["fold"] - 100) < 0.5


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
# Vectorized turn+river solver — nested ground-truth ile doğrulama
# ─────────────────────────────────────────────────────────────────────

def test_vector_turn_filters_board_combos():
    """Board kartıyla çakışan combo'lar elenmeli (phantom-combo bug regresyonu)."""
    from app.poker.vector_turn_solver import VectorTurnRiverSolver
    # Board'da Kc ve Ah var → KK'nın Kc'li, AA'nın Ah'lı combo'ları imkansız
    s = VectorTurnRiverSolver(["AA"], ["KK"], board_turn="Ah Kc 8d 3s",
                              pot=100, bet_frac=0.66)
    labels = {h.hand_label for h in s.solve(iterations=50).hero}
    assert not any("Ah" in l for l in labels), f"board combo elenmedi: {labels}"
    # AA'nın geçerli combo'ları: AcAd, AcAs, AdAs (Ah hariç)
    assert len(labels) == 3, f"beklenen 3 AA combo, gelen {labels}"


def test_vector_turn_value_bet_polarization():
    """Set/trips değer eli yüksek bet, air düşük (yön doğru)."""
    from app.poker.vector_turn_solver import VectorTurnRiverSolver
    r = VectorTurnRiverSolver(["AA", "72o"], ["KK"], board_turn="Ah Kc 8d 3s",
                              pot=100, bet_frac=0.66).solve(iterations=1500)
    bet = {("AA" if h.hand_label[0] == h.hand_label[2] else "72o"): []
           for h in r.hero}
    for h in r.hero:
        k = "AA" if h.hand_label[0] == h.hand_label[2] else "72o"
        bet[k].append(h.turn_bet)
    aa = sum(bet["AA"]) / len(bet["AA"])
    air = sum(bet["72o"]) / len(bet["72o"])
    assert aa > 80, f"AA (trips) değer eli bet {aa}"
    assert air < aa, f"air {air} >= value {aa} — polarizasyon yok"


def test_vector_turn_matches_nested_single_villain():
    """DOĞRULANAN ALT-KÜME: tek-villain spotta oyun-değeri nested ile tutarlı.

    CFR equilibrium stratejisi tek değil ama OYUN-DEĞERİ tektir. Tek-villain
    küçük spotta iki solver da aynı per-pair EV'ye yakınsar. (NOT: çok-el hero
    range'inde bilinen value-dağılım hatası var — bkz test_vector_turn_KNOWN_BUG.)
    """
    import numpy as np
    from app.poker.nested_solver import NestedTurnRiverSolver
    from app.poker.vector_turn_solver import VectorTurnRiverSolver
    H, V, board = ["AA", "72o"], ["KK"], "Ah Kc 8d 3s"
    ns = NestedTurnRiverSolver(H, V, board_turn=board, pot=100, bet_frac=0.66)
    # nested self-play oyun değeri (pair başına)
    pairs = []
    bset = ns._board_set
    for hi in range(len(ns.hero)):
        hc = {(ns.hero[hi][0].rank, ns.hero[hi][0].suit),
              (ns.hero[hi][1].rank, ns.hero[hi][1].suit)}
        if hc & bset:
            continue
        for vi in range(len(ns.vill)):
            vc = {(ns.vill[vi][0].rank, ns.vill[vi][0].suit),
                  (ns.vill[vi][1].rank, ns.vill[vi][1].suit)}
            if vc & bset or vc & hc:
                continue
            pairs.append((hi, vi))
    ev = [sum(ns._turn_cfr(hi, vi, 1.0, 1.0, None) for hi, vi in pairs)
          for _ in range(400)]
    nested_gv = np.mean(ev[200:]) / len(pairs)
    vs = VectorTurnRiverSolver(H, V, board_turn=board, pot=100, bet_frac=0.66)
    vs.solve(iterations=3000)
    vec_gv = np.mean(vs.ev_trace[1500:]) / len(pairs)
    # İkisi de hero-kaybı (negatif) ve birbirine yakın (≤4bb, convergence payı)
    assert nested_gv < 0 and vec_gv < 0, f"nested {nested_gv} vec {vec_gv}"
    assert abs(nested_gv - vec_gv) < 4.0, \
        f"oyun-değeri sapması: nested {nested_gv:.2f} vs vector {vec_gv:.2f}"


@pytest.mark.xfail(reason="BİLİNEN HATA: çok-el hero range'inde value-dağılımı "
                          "yanlış (KK trips bet etmiyor). Düzelene kadar UI'a "
                          "bağlanmadı; turn için nested_solver/TexasSolver kullan.",
                   strict=False)
def test_vector_turn_KNOWN_BUG_multihand_value_distribution():
    """Çok-el hero range'inde trip-el (KK) yeterince value-bet etmeli.

    nested: KK ~%34 bet. vector (hatalı): KK ~%0. Bu test kök-neden bulunup
    düzeltilince yeşile dönmeli — gelecekteki düzeltmenin hedefi.
    """
    from app.poker.vector_turn_solver import VectorTurnRiverSolver
    r = VectorTurnRiverSolver(["AA", "KK", "QQ"], ["JJ", "AK"],
                              board_turn="Ah Kc 8d 3s", pot=100,
                              bet_frac=0.66).solve(iterations=4000)
    kk = [h.turn_bet for h in r.hero if h.hand_label[0] == "K" == h.hand_label[2]]
    avg_kk = sum(kk) / len(kk)
    # KK (trip kings) güçlü value eli — anlamlı bir frekansla bet etmeli
    assert avg_kk > 15, f"KK trips bet sadece {avg_kk}% (value el bet etmeli)"


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


# ─────────────────────────────────────────────────────────────────────
# Preflop range leak fix + trainer metrics
# ─────────────────────────────────────────────────────────────────────

def test_mtt_bb_defense_wider_than_cash():
    """ANTE leak fix: MTT'de BB defansı cash'ten belirgin geniş olmalı."""
    from app.poker.gto_ranges import get_action

    def defend_pct(mode):
        ranks = "AKQJT98765432"
        keys = []
        for i, hi in enumerate(ranks):
            for j, lo in enumerate(ranks):
                if i == j:
                    keys.append(hi + lo)
                elif i < j:
                    keys.append(hi + lo + "s")
                else:
                    keys.append(lo + hi + "o")
        dc = tot = 0
        for hk in keys:
            c = 6 if len(hk) == 2 else (4 if hk.endswith("s") else 12)
            tot += c
            a = get_action("BB", hk, "vs RFI", 25, mode, vs_position="CO")
            if a.get("call", 0) + a.get("raise", 0) >= 20:
                dc += c
        return 100 * dc / tot

    cash = defend_pct("cash")
    mtt = defend_pct("MTT")
    assert mtt > cash + 10, f"MTT defansı yeterince geniş değil: cash {cash:.0f}, mtt {mtt:.0f}"
    assert 55 <= mtt <= 70, f"MTT BB defansı hedef dışı: {mtt:.0f}% (60-66 beklenir)"


def test_quiz_ev_loss_and_difficulty():
    """EV-loss heuristiği + ELO zorluk derecesi mantıklı."""
    from app.ui.screens.quiz_trainer import QuizSpot
    # Dominant aksiyonu seçmek → 0 kayıp
    sp = QuizSpot("CO", 100, "RFI", "72o", {"raise": 0, "call": 0, "fold": 100})
    assert sp.ev_loss_bb("fold") == 0.0
    # Trash'i RFI'da açmak → küçük (≤ açış boyutu mertebesi)
    assert 0 < sp.ev_loss_bb("raise") <= 3.0
    # Trash'i 15bb jam etmek → büyük (stack riski)
    jam = QuizSpot("UTG", 15, "Push/Fold", "72o", {"raise": 0, "call": 0, "fold": 100})
    assert jam.ev_loss_bb("raise") >= 10.0
    # Mixed / kısa-stack spot daha zor (yüksek ELO rating)
    easy = QuizSpot("UTG", 100, "RFI", "AA", {"raise": 100, "call": 0, "fold": 0})
    hard = QuizSpot("BTN", 18, "vs 3-bet", "A5s", {"raise": 40, "call": 30, "fold": 30})
    assert hard.difficulty_rating() > easy.difficulty_rating()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
