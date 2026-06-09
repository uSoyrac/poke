"""D140: Soyrac HCP danışmanı — KULLANICI için masada-yapılabilir el değerlendirme.
SHCP skoru + pozisyon eşiği + senaryo (RFI/vs-RFI/vs-3bet/push) → aksiyon satırı."""
from __future__ import annotations
from app.poker.soyrac_advisor import shcp_score, soyrac_advice, _b4_blocker


def test_shcp_score_anchors():
    assert shcp_score("AA") == 40
    assert shcp_score("72o") == -1
    assert shcp_score("AKs") == 27
    assert shcp_score("A5s") == 15
    assert shcp_score("98s") == 12      # suited connector


def test_rfi_speculative_late_position():
    # 98s: UTG fold, CO/BTN aç (implied-odds late position mantığı)
    assert soyrac_advice("98s", "UTG", "RFI")["action"] == "FOLD"
    assert soyrac_advice("98s", "CO", "RFI")["action"] == "RAISE (AÇ)"
    assert soyrac_advice("AA", "UTG", "RFI")["action"] == "RAISE (AÇ)"
    assert soyrac_advice("72o", "BTN", "RFI")["action"] == "FOLD"


def test_vs3bet_blocker_axis_a5s_beats_ajs():
    # Equity sıralaması çöker: A5s 4-bet (blocker), AJs call (dominated)
    a5 = soyrac_advice("A5s", "BTN", "vs 3-bet")
    aj = soyrac_advice("AJs", "BTN", "vs 3-bet")
    assert a5["action"] == "4-BET" and a5["b4"] >= 2
    assert aj["action"] != "4-BET"


def test_vs_rfi_dual_threshold():
    assert soyrac_advice("KQs", "BB", "vs RFI", "CO")["action"] == "3-BET"
    assert soyrac_advice("72o", "BB", "vs RFI", "BTN")["action"] == "FOLD"


def test_push_fold_short_stack():
    assert soyrac_advice("AA", "UTG", "RFI", stack_bb=10)["action"] == "JAM"
    assert soyrac_advice("72o", "UTG", "RFI", stack_bb=10)["action"] == "FOLD"
