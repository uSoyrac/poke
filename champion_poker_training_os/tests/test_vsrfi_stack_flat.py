"""D259 (+EV-max audit #13): vs-RFI IP flat bandı stack-kördü → sığlaştıkça speculative
suited-connector/offsuit-broadway implied-odds'u çöker. IP defender (CO/BTN/HJ/LJ) flat
sığ'da daralır (3bet-jam-or-fold); BB/SB closing (D257) + raise_t + bot DOKUNULMAZ."""
from app.poker.soyrac_advisor import soyrac_advice


def _a(hk, pos, vs, stack, bot=False):
    return soyrac_advice(hk, pos, scenario="vs RFI", vs_position=vs,
                         stack_bb=stack, bot_mode=bot)["action"]


def test_speculative_ip_flat_narrows_when_shallow():
    """97s BTN vs CO: 100bb CALL → 22bb FOLD (SPR çöktü, implied-odds yok)."""
    assert _a("97s", "BTN", "CO", 100) == "CALL"
    assert _a("97s", "BTN", "CO", 22) == "FOLD"


def test_strong_flats_survive_shallow():
    """Showdown-değerli flat (KJo) sığ'da da CALL (implied-odds'a bağlı değil)."""
    assert _a("KJo", "BTN", "CO", 22) == "CALL"


def test_blind_closing_untouched():
    """BB (closing, D257) → stack'ten bağımsız (flat-narrowing yalnız IP)."""
    assert _a("T9s", "BB", "CO", 100) == _a("T9s", "BB", "CO", 22)


def test_bot_unchanged():
    """BOT → eski IP flat (advice-only → fidelity 0)."""
    assert _a("97s", "BTN", "CO", 22, bot=True) == _a("97s", "BTN", "CO", 100, bot=True)
