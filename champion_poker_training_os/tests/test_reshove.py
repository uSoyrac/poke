"""D243: Re-shove (re-jam) — sığ stack AÇIŞA karşı JAM/FOLD (call-vs-jam değil).

Eski D185 tüm <15bb facing'i call-vs-jam'e atıyordu → açışa karşı re-shove edge'ini
(fold-equity'li 3bet-jam) kaçırıyordu. Açış JAM DEĞİL → re-jam mümkün+kârlı.
ADVICE-only (not bot_mode) → fidelity korunur."""
from app.poker.soyrac_advisor import soyrac_advice


def _adv(hk, scenario, stack, bot=False, pos="BB", vs="BTN"):
    return soyrac_advice(hk, pos, scenario=scenario, vs_position=vs,
                         stack_bb=stack, tourney=True, bot_mode=bot)


def test_reshove_vs_open_jams_not_calls():
    """13bb açışa karşı orta-güç el → JAM (re-shove), CALL değil."""
    r = _adv("A9s", "vs RFI", 13)
    assert r["action"] == "JAM", r
    assert "Re-Jam" in r["scenario"]


def test_reshove_range_wider_than_callfold_junk_folds():
    """Re-shove geniş ama sınırsız değil — gerçek çöp (72o) FOLD."""
    assert _adv("72o", "vs RFI", 13)["action"] == "FOLD"
    assert _adv("J8o", "vs RFI", 13)["action"] == "FOLD"


def test_reshove_premiums_jam():
    """Premium (AA/TT/AK) açışa karşı sığ → JAM (flat değil, commit)."""
    for hk in ("AA", "TT", "AKo", "KQs"):
        assert _adv(hk, "vs RFI", 12)["action"] == "JAM", hk


def test_vs_3bet_stays_call_vs_jam():
    """3-BET'e karşı re-jam YOK → Call-vs-Jam (CALL/FOLD) korunur."""
    r = _adv("99", "vs 3-bet", 13, pos="CO", vs="BTN")
    assert r["scenario"] == "Call vs Jam"
    assert r["action"] in ("CALL", "FOLD")


def test_bot_mode_unchanged_for_fidelity():
    """BOT açışa karşı sığ → eski Call-vs-Jam (re-shove advice-only → fidelity 0-sapma)."""
    r = _adv("A9s", "vs RFI", 13, bot=True)
    assert r["scenario"] == "Call vs Jam"
    assert r["action"] in ("CALL", "FOLD")


def test_reshove_size_is_allin():
    """Re-shove aksiyonu all-in sizing taşır (jam)."""
    r = _adv("A9s", "vs RFI", 13)
    assert r.get("size") and "all-in" in r["size"]["text"]


def test_deep_stack_not_reshove():
    """Derin (40bb) açışa karşı → normal vs-RFI (3-BET/CALL/FOLD), re-jam dalına girmez."""
    r = _adv("A9s", "vs RFI", 40, pos="BTN", vs="CO")
    assert r["scenario"] == "vs RFI"
