"""soyrac_explain öğretici motoru — preflop dalı + fidelity (soyrac_advice değişmedi)."""
from app.poker.soyrac_advisor import soyrac_explain, soyrac_advice, shcp_breakdown, _tone_for_action


def test_breakdown():
    assert "= 27" in shcp_breakdown("AKs") or "27" in shcp_breakdown("AKs")
    assert "çifti" in shcp_breakdown("AA") and "40" in shcp_breakdown("AA")
    assert "suited+4" in shcp_breakdown("98s")


def test_tone():
    assert _tone_for_action("RAISE (AÇ)") == "go"
    assert _tone_for_action("CALL") == "caution"
    assert _tone_for_action("FOLD") == "stop"


def test_rfi():
    e = soyrac_explain("AKs", "UTG", "RFI")
    assert e["phase"] == "preflop" and e["action"] == soyrac_advice("AKs", "UTG", "RFI")["action"]
    assert e["score"] == 27 or e["score"] >= 25
    assert len(e["chain_steps"]) >= 3
    assert all(len(s) <= 70 for s in e["chain_steps"])   # ~60 hedef, tolerans
    assert e["why"] and e["tone"] in ("go", "caution", "stop")


def test_vs3bet():
    e = soyrac_explain("A5s", "CO", "vs 3-bet", vs_position="BB")
    assert e["b4"] is not None
    assert "KATLA" in e["why"] or "4-BET" in e["why"] or "çağır" in e["why"]
    assert e["action"] == soyrac_advice("A5s", "CO", "vs 3-bet", vs_position="BB")["action"]


def test_vsrfi():
    e = soyrac_explain("AJs", "BTN", "vs RFI", vs_position="CO")
    assert e["call_t"] is not None and e["raise_t"] is not None
    assert len(e["chain_steps"]) >= 3


def test_quiz_fields():
    e = soyrac_explain("KK", "MP", "RFI")
    assert e["quiz_correct"] == e["action"]
    assert e["quiz_prompt"] and e["quiz_options"]


def test_fidelity_unchanged():
    # explain çağrısı soyrac_advice çıktısını ETKİLEMEZ
    a1 = soyrac_advice("98s", "BTN", "RFI")
    soyrac_explain("98s", "BTN", "RFI")
    a2 = soyrac_advice("98s", "BTN", "RFI")
    assert a1 == a2


# ── POSTFLOP motoru ──
from app.engine.hand_state import Card, Street
from app.poker.soyrac_advisor import soyrac_postflop_advice, soyrac_explain as _se


class _PP:
    def __init__(self, hole, stack=100):
        self.hole_cards = [Card(c[0], c[1].lower()) for c in hole]; self.stack = stack


class _HH:
    def __init__(self, hole, board, pot=10, to_call=0, street=Street.FLOP):
        self.players = [_PP(hole)]
        self.community = [Card(c[0], c[1].lower()) for c in board]
        self.pot = pot; self.street = street; self._tc = to_call
    def to_call(self, idx): return self._tc


def test_postflop_nut_set():
    pf = soyrac_postflop_advice(_HH(['7h', '7c'], ['7s', '2d', '9h']), 0)
    assert pf and pf["tier"] == "NUT"
    assert "BET" in pf["action"]


def test_postflop_overpair_strong():
    pf = soyrac_postflop_advice(_HH(['Ah', 'Ac'], ['Ks', '7d', '2h']), 0)
    assert pf and pf["tier"] in ("GÜÇLÜ", "NUT")


def test_postflop_commit_gate():
    # zayıf el + büyük bahis → commit-gate uyarısı
    pf = soyrac_postflop_advice(_HH(['3h', '3c'], ['Ks', '9d', '2h'], pot=10, to_call=90), 0)
    assert pf and ("Commit-gate" in (pf["golden_rule"] or "") or pf["action"] == "FOLD")


def test_postflop_board_label():
    pf = soyrac_postflop_advice(_HH(['Ah', 'Kh'], ['7s', '2d', '9h']), 0)
    assert pf["board_label"] in ("KURU", "SEMİ-ISLAK", "ISLAK", "EŞLİ", "TEK-RENK")


def test_explain_postflop_branch():
    e = _se("77", "BTN", "RFI", hand=_HH(['7h', '7c'], ['7s', '2d', '9h']), hero_idx=0)
    assert e["phase"] == "postflop" and e["tier"] == "NUT"
    assert e["flow_nodes"] and len(e["chain_steps"]) >= 3


# ── LEAK kategorisi ──
from app.poker.soyrac_advisor import soyrac_leak_category


def test_leak_categories():
    # uyuşma → None
    assert soyrac_leak_category({"phase": "preflop", "scenario": "RFI", "action": "FOLD"}, "FOLD") is None
    # RFI eşik-altı raise
    assert "geniş açış" in soyrac_leak_category({"phase": "preflop", "scenario": "RFI", "action": "FOLD"}, "RAISE")
    # vs-3bet over-call
    assert "over-call" in soyrac_leak_category({"phase": "preflop", "scenario": "vs 3-bet", "action": "FOLD"}, "CALL")
    # commit-gate ihlali
    e = {"phase": "postflop", "scenario": "Postflop", "action": "CHECK", "golden_rule": "⛔ Commit-gate: ..."}
    assert "Commit-gate" in soyrac_leak_category(e, "RAISE")


# ── TRUE-COUNT eşik kırılımı (D194) ──
def test_explain_carries_threshold_breakdown():
    # Düzeltmeli senaryo → count_line + breakdown dolu
    e = soyrac_explain("AJo", "UTG", "RFI", stack_bb=30, icm=True, tourney=True)
    bd = e.get("threshold_breakdown")
    assert bd and bd["base"] == 15 and bd["effective"] == bd["base"] + bd["icm_adj"] \
        + bd["deep_adj"] + bd["tourney_adj"] + bd["table_adj"]
    assert "baz 15" in e["count_line"] and "efektif" in e["count_line"]


def test_explain_count_line_base_only_when_no_adjust():
    # Düz cash 100bb UTG → sadece baz (düzeltme yok)
    e = soyrac_explain("AJo", "UTG", "RFI", stack_bb=100, icm=False, tourney=False)
    bd = e["threshold_breakdown"]
    assert bd["icm_adj"] == 0 and bd["deep_adj"] == 0 and bd["tourney_adj"] == 0
    assert e["count_line"].startswith("baz")


# ── BOARD-TEHDİT haircut (D198) — flush board'da top-pair bluff-catcher ──
from app.engine.hand_state import Card as _C, Street as _St


def _PFH(hole, board, pot, tc, street=_St.RIVER):
    class _P:
        def __init__(s): s.hole_cards=[_C(c[0],c[1]) for c in hole]; s.stack=75.0
    class _H:
        def __init__(s): s.players=[_P()]; s.community=[_C(c[0],c[1]) for c in board]; s.pot=pot; s.street=street
        def to_call(s,i): return tc
    return _H()


def test_monotone_board_top_pair_is_bluffcatch():
    # Q9 (çubuksuz) monotone 3-çubuk board, bahse karşı → bluff-catcher, kör CALL DEĞİL
    pf = soyrac_postflop_advice(_PFH(["Qh","9d"], ["Ts","5c","Qc","2h","3c"], 83.8, 33.3), 0)
    assert pf["tier"] == "BLUFF-CATCH"
    assert "marjinal" in pf["action"] or pf["action"] == "FOLD"
    assert pf["eq"] >= 0.5                    # ham eq hâlâ yüksek (görünür)
    assert "Board-tehdit" in (pf["golden_rule"] or "")


def test_flush_hand_unaffected_by_threat():
    # Hero FLUSH (çubuklu) aynı board → güçlü kalır (haircut muaf)
    pf = soyrac_postflop_advice(_PFH(["Ac","9c"], ["Ts","5c","Qc","2h","3c"], 83.8, 33.3), 0)
    assert pf["tier"] == "NUT" and "RAISE" in pf["action"]


def test_dry_board_top_pair_still_calls():
    # Kuru K72 board top-pair (AK) bahse karşı → CALL (tehdit yok, over-fix yok)
    pf = soyrac_postflop_advice(_PFH(["Ah","Kd"], ["Ks","7d","2h"], 10, 3, _St.FLOP), 0)
    assert pf["action"] == "CALL" and pf["tier"] == "GÜÇLÜ"


# ── KADEME A: board-tehdit motoru tamamlandı (D200) ──
def test_monotone_toppair_betting_checks():
    # A1: monotone board'da top-pair, to_call=0 → BET value DEĞİL, CHECK/pot-kontrol
    pf = soyrac_postflop_advice(_PFH(["Qh","9d"], ["Ts","5c","Qc","2h","3c"], 20, 0), 0)
    assert "CHECK" in pf["action"]


def test_board_straight_not_raise():
    # A2: board 5-düz (89TJQ) + 22 → RAISE DEĞİL (board oynuyor)
    pf = soyrac_postflop_advice(_PFH(["2h","2d"], ["8s","9c","Tc","Jh","Qd"], 40, 15), 0)
    assert "RAISE" not in pf["action"] and pf["tier"] == "BLUFF-CATCH"


def test_subnut_flush_not_raise():
    # A4: sub-nut floş (32c) 4-floş board → RAISE DEĞİL
    pf = soyrac_postflop_advice(_PFH(["3c","2c"], ["As","Kc","9c","4h","7c"], 40, 15), 0)
    assert "RAISE" not in pf["action"]


def test_set_on_flushboard_not_raise():
    # A5: set 4-floş board → RAISE DEĞİL (floşa karşı bluff-catch)
    pf = soyrac_postflop_advice(_PFH(["2c","2d"], ["2s","Ah","Kh","Qh","7h"], 40, 15), 0)
    assert "RAISE" not in pf["action"]


def test_bottom_boat_not_raise():
    # A8: alt-dolu (22 on AA2) → RAISE DEĞİL (her Ax üst-dolu)
    pf = soyrac_postflop_advice(_PFH(["2h","2d"], ["As","Ac","2s","7h","9d"], 40, 15), 0)
    assert "RAISE" not in pf["action"]


def test_nut_flush_still_raises():
    # OVER-FIX guard: gerçek nut floş (Ac9c) RAISE kalmalı
    pf = soyrac_postflop_advice(_PFH(["Ac","9c"], ["Ts","5c","Qc","2h","3c"], 40, 15), 0)
    assert pf["tier"] == "NUT" and "RAISE" in pf["action"]


def test_top_boat_still_raises():
    # OVER-FIX guard: üst-dolu (AA on AA2) RAISE kalmalı
    pf = soyrac_postflop_advice(_PFH(["Ah","Ad"], ["As","2c","2d","7h","9s"], 40, 15), 0)
    assert "RAISE" in pf["action"]


# ── KADEME B: çekme motoru street/combo-aware (D201) ──
def test_river_busted_draw_folds():
    # B2: river 8-high busted draw → FOLD (hayalet equity yok)
    pf = soyrac_postflop_advice(_PFH(["8h","7h"], ["Ah","Kc","Qd","2s","3c"], 40, 30), 0)
    assert pf["action"] == "FOLD" and pf["eq"] < 0.2


def test_combo_draw_flop_calls():
    # B1: FD+OESD combo flop yarım-pota → DRAW, CALL (FOLD değil)
    pf = soyrac_postflop_advice(_PFH(["9h","8h"], ["Th","7h","2c"], 20, 10, _St.FLOP), 0)
    assert pf["tier"] == "DRAW" and "CALL" in pf["action"] and pf["eq"] > 0.5


def test_turn_big_draw_reaches_draw_tier():
    # B5: turn 15-out combo → DRAW tier ulaşılabilir (HAVA değil)
    pf = soyrac_postflop_advice(_PFH(["Jh","Th"], ["9h","8h","2c","Ks"], 20, 10, _St.TURN), 0)
    assert pf["tier"] == "DRAW"


def test_made_hand_draw_zero_unchanged():
    # OVER-FIX guard: kuru board made-hand (draws=0) etkilenmez
    pf = soyrac_postflop_advice(_PFH(["7h","7c"], ["7s","2d","9h"], 10, 3, _St.FLOP), 0)
    assert pf["tier"] == "NUT" and "RAISE" in pf["action"]
