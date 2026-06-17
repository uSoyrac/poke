"""D252 (+EV-max audit): vs-3bet'te EARLY-OOP defender (UTG/MP) dominated broadway'i
çok genişti. Soft pop 3-bet value-locked → dominated continue −EV. flat_t +2 (UTG/MP).
ADVICE-only (bot/CO/BTN dokunulmaz)."""
from app.poker.soyrac_advisor import soyrac_advice


def _a(hk, pos, vs="BTN", bot=False):
    return soyrac_advice(hk, pos, scenario="vs 3-bet", vs_position=vs,
                         stack_bb=100, bot_mode=bot)["action"]


def test_early_oop_folds_dominated_broadway():
    """UTG vs 3-bet: QJs/KJs/AQo dominated → FOLD (eski CALL)."""
    for hk in ("QJs", "KJs", "AQo"):
        assert _a(hk, "UTG") == "FOLD", f"{hk}: {_a(hk,'UTG')}"


def test_premiums_still_4bet():
    """Premium (AKs/QQ+) DOKUNULMAZ → 4-BET."""
    assert _a("AKs", "UTG") == "4-BET"
    assert _a("QQ", "UTG") == "4-BET"


def test_late_position_untouched():
    """CO (IP/late) → continue korunur (fix yalnız UTG/MP)."""
    for hk in ("QJs", "KJs", "AQo"):
        assert _a(hk, "CO") in ("CALL", "4-BET")


def test_bot_mode_unchanged_fidelity():
    """BOT (bot_mode) → eski davranış (advice-only → fidelity 0-sapma)."""
    assert _a("QJs", "UTG", bot=True) == "CALL"
