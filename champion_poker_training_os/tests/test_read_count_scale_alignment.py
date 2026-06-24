"""D-A0 (SAYIM-MVP HİZALAMA — denetim ön-şartı): masa cheatsheet'i + insanın kafadan tuttuğu
ölçek, range_narrowing motorunun GERÇEK sdelta'sıyla BİREBİR olmalı. Motor TEK-KAYNAK; bu test
motor değişirse KIRILIR → panel/insan asla farklı sayı bulamaz.

ÖNEMLİ: int(round(sdelta)) Python round-half-to-even kullanır → flop-cbet 0.5→0, turn-barrel 0.8→1.
Cheatsheet bu GERÇEK değerlere uydurulur (motor kaynak, cheatsheet türev)."""
from app.poker.range_narrowing import _apply, narrow, starting_range

_B = starting_range("BTN", "open")

# (street, role, action) → masada kullanılan tamsayı = int(round(sdelta))
_EXPECTED = {
    ("preflop", "facing_raise", "call"): -2,   # flat = capped (QQ+/AK 3bet'lerdi)
    ("flop", "aggressor", "check"): -1,        # cbet YAPMADI (give-up)   round(-1.2)
    ("turn", "aggressor", "check"): -1,        # barrel YAPMADI           round(-1.0)
    ("flop", "aggressor", "cbet"): 0,          # flop cbet round(0.5)=0 (banker rounding!)
    ("turn", "aggressor", "barrel"): 1,        # turn barrel round(0.8)=1
    ("river", "aggressor", "bet"): 1,          # river polar round(1.2)=1
    ("flop", "caller", "check_raise"): 2,      # POLARİZE güçlü (dizi-kilit)
    ("flop", "caller", "check_call"): -1,      # round(-0.8)
    ("flop", "caller", "donk"): 0,             # round(-0.3)=0 (ihmal)
    ("flop", "caller", "check"): -1,           # round(-0.8)
}


def test_apply_sdelta_matches_cheatsheet():
    """Her _apply branch'inin int(round(sdelta))'sı cheatsheet tamsayısına eşit."""
    for (street, role, action), expected in _EXPECTED.items():
        _, _, sdelta, _ = _apply(_B, street, role, action)
        got = int(round(sdelta))
        assert got == expected, (
            f"{street}/{role}/{action}: motor {sdelta}→{got} ≠ cheatsheet {expected}")


def test_narrow_running_count_cumulative():
    """Dizi flat(−2) + flop check-raise(+2) → kümülatif rc = 0 (motor)."""
    nr = narrow("BB", [("preflop", "facing_raise", "call"),
                       ("flop", "caller", "check_raise")], first_action="flat")
    assert nr.running_count == 0, f"flat(−2)+XR(+2)=0 olmalı: {nr.running_count}"


def test_checkraise_alone_is_value_lock():
    """Dizi-kilit: tek check-raise = +2 (örneklemsiz, en yüksek-sinyal)."""
    nr = narrow("BB", [("flop", "caller", "check_raise")], first_action="open")
    assert nr.running_count == 2
