"""D263 (+EV-max audit #7): SHCP nut-flush/Kx blocker primi weak-suited'i şişiriyordu.
Erken (sıkı) açışa karşı vs-RFI flat'te ÖLÜ Kx-low (K2s-K4s: redraw yok, dominated)
sıkılaştırılır → FOLD. Redraw-zengin A-x (nut-flush+wheel) ve geç-opener KORUNUR."""
from app.poker.soyrac_advisor import soyrac_advice


def _a(hk, vs, pos="BTN"):
    return soyrac_advice(hk, pos, scenario="vs RFI", vs_position=vs, stack_bb=100)["action"]


def test_dead_kx_low_folds_vs_early():
    """K2s/K3s vs UTG (erken): ölü dominated → FOLD."""
    assert _a("K2s", "UTG") == "FOLD"
    assert _a("K3s", "UTG") == "FOLD"


def test_redraw_ax_preserved():
    """A5s (wheel) ve A-x redraw'lı → vs erken bile devam (FOLD değil)."""
    assert _a("A5s", "UTG") != "FOLD"
    assert _a("A2s", "UTG") != "FOLD"


def test_late_opener_untouched():
    """Geç açana (BTN) karşı K2s/K3s dokunulmaz (sıkılaştırma yalnız erken-opener)."""
    assert _a("K2s", "BTN") != "FOLD"


def test_premium_suited_untouched():
    """KQs vs erken → güçlü, devam (3-BET/CALL)."""
    assert _a("KQs", "UTG") in ("3-BET", "CALL")
