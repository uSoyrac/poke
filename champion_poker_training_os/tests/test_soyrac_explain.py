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
