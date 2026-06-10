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
