"""D276 (kullanıcı 88'i 39bb'de canlı yakaladı: 'emin değilim 4-bet doğru mu'):
vs-3bet ekseni EQ DEĞİL, BLOKER+DOMİNASYON (verify_blocker_vs3bet). Sığ dal (≤45bb)
pair-ladder (16+2×rank) orta çiftleri (66-TT skor 24-32) + AQs'i şişirip GATE'siz
4bet-JAM ettiriyordu = DOMINATED spew. GTO-teyit (gto_ranges.get_action IP tabloları):
88/99/AQs raise%0-call%50-85, TT/JJ call-lean; QQ+/AK/A5s = 4bet.

FIX: ADVICE'ta orta-derin (>25bb, jam-or-fold DEĞİL) → polarize, GATE b4≥2
(=QQ+/AK + wheel-ace blöf). Orta çift/AQs/TT/JJ → CALL. ≤25bb (jam-or-fold) merged
geniş jam KORUNUR. BOT (bot_mode) DOKUNULMAZ (fidelity 0)."""
from app.poker.soyrac_advisor import soyrac_advice


def _a(hk, st, bot=False):
    return soyrac_advice(hk, "SB", "vs 3-bet", "BTN", stack_bb=st,
                         tourney=True, bot_mode=bot)["action"]


def test_user_hand_88_39bb_calls_not_4bet():
    """Kullanıcının eli: 88, 39bb, vs 3-bet → CALL (set-mine), 4-BET DEĞİL (dominated spew)."""
    assert _a("88", 39) == "CALL"


def test_midpairs_and_aqs_call_at_mid_deep():
    """26-45bb orta-derin: orta çift (77-TT) + AQs DOMINATED → CALL (4-BET değil)."""
    for st in (30, 39, 45):
        for hk in ("77", "88", "99", "TT", "AQs"):
            assert _a(hk, st) == "CALL", f"{hk}@{st}bb: {_a(hk, st)}"


def test_premiums_and_wheel_still_4bet():
    """QQ+/AK value + A5s wheel-blöf → 4-BET korunur (her stack)."""
    for st in (30, 39, 100):
        for hk in ("QQ", "AKo", "A5s"):
            assert _a(hk, st) == "4-BET", f"{hk}@{st}bb: {_a(hk, st)}"


def test_very_short_merged_jam():
    """≤25bb jam-or-fold: 88+ merged geniş value-jam (4-BET) KORUNUR."""
    for hk in ("88", "99", "TT"):
        assert _a(hk, 20) == "4-BET", f"{hk}@20bb: {_a(hk, 20)}"


def test_bot_mode_unchanged_fidelity():
    """BOT (bot_mode) → eski geniş value-4bet (advice-only fix → fidelity 0-sapma)."""
    for hk in ("88", "TT", "AQs"):
        assert _a(hk, 39, bot=True) == "4-BET", f"{hk} bot: {_a(hk, 39, bot=True)}"
