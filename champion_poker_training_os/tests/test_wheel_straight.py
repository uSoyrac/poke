"""LEAK-FIX (D219): TEKERLEK (wheel A-2-3-4-5) düz tespit edilmiyordu.

BUG (kullanıcı canlı yakaladı): A♥4♥ / 5♥-T♣-2♣-Q♣-3♣ → A-2-3-4-5 düz var ama motor
'high card → HAVA' dedi. Kök sebep: _hand_strength düz-tespiti A'yı sadece YÜKSEK (12)
sayıyor, A-DÜŞÜK tekerleği (-1) hiç denemiyordu → made wheel görünmez.

NÜANS: bu spotta board 4-sinek → düz NUTS DEĞİL (floş onu geçer). Doğru sonuç: made
straight AMA flush-board'da bluff-catch → CHECK. Eski 'HAVA' iki kat yanlıştı (düzü hiç
görmedi). Fix bot_brain'de (kök) — fidelity 0-sapma korundu (wheel bot kararını bantta
değiştirmedi).
"""
import types
from app.engine.hand_state import Street, card_from_str
from app.poker.soyrac_advisor import _explain_bb, _tier_from, soyrac_postflop_advice


def _hs(h, b):
    return _explain_bb()._hand_strength([card_from_str(x) for x in h.split()],
                                        [card_from_str(x) for x in b.split()])


def test_made_wheel_detected_as_straight():
    """A4 / 5-T-2-Q-3 → 'straight' (HAVA DEĞİL)."""
    s, d, lab = _hs("Ah 4h", "5h Tc 2c Qc 3c")
    assert lab == "straight", f"tekerlek düz görülmeli, {lab!r} çıktı"
    assert s >= 0.80, f"straight gücü ~0.85 olmalı, {s}"


def test_wheel_variants():
    """Tekerlek farklı board sıralarında da tespit edilmeli."""
    assert _hs("Ah 5d", "2c 3s 4d Kh 9c")[2] == "straight"   # A-2-3-4-5
    assert _hs("Ad 2h", "3c 4s 5d 9h Kc")[2] == "straight"   # A-2 + 3-4-5


def test_broadway_straight_regression():
    """Üst-uç düz (A-yüksek) bozulmadı: AK / Q-J-T → straight."""
    assert _hs("Ah Kd", "Qc Js Td 4h 2c")[2] == "straight"


def test_normal_straight_regression():
    """Orta düz regresyonsuz: 67 / 5-8-9 → straight."""
    assert _hs("6h 7d", "5c 8s 9d")[2] == "straight"


def test_no_false_wheel():
    """A var ama tekerlek YOK → düz uydurma. A-K-7-4-2 → düz değil."""
    lab = _hs("Ah Kd", "7c 4s 2d 9h Qc")[2]
    assert lab != "straight", f"sahte tekerlek: {lab!r}"


def _spot(h, b, to_call):
    hole = [card_from_str(x) for x in h.split()]
    board = [card_from_str(x) for x in b.split()]
    hero = types.SimpleNamespace(hole_cards=hole, stack=31.0, is_folded=False, is_eliminated=False)
    vill = types.SimpleNamespace(hole_cards=[], stack=20.0, is_folded=False, is_eliminated=False)
    hand = types.SimpleNamespace(players=[hero, vill], community=board, street=Street.RIVER,
                                 pot=9.4, active_count=2, to_call=lambda i: to_call)
    return soyrac_postflop_advice(hand, 0)


def test_wheel_on_flush_board_is_bluffcatch_not_air():
    """KULLANICI SPOTU: A4 wheel / 4-sinek board, checked-to → CHECK + 'made ama NUTS DEĞİL'
    (HAVA DEĞİL, ama floş-board'da değer de değil → bluff-catch)."""
    out = _spot("Ah 4h", "5h Tc 2c Qc 3c", 0.0)
    assert out["tier"] != "HAVA", f"made düz HAVA olmamalı: {out['tier']}"
    assert "BET (value)" not in out["action"], f"floş board'da düz value-bet etmemeli: {out['action']}"
    assert out["action"].startswith("CHECK"), f"checked-to → CHECK beklenir: {out['action']}"


def test_wheel_on_flush_board_facing_bet_bluffcatch():
    """A4 wheel / floş board, bet'e karşı → bluff-catch (eq floş-haircut'lı), GÜÇLÜ-value değil."""
    out = _spot("Ah 4h", "5h Tc 2c Qc 3c", 3.0)
    assert out["tier"] in ("BLUFF-CATCH", "ZAYIF", "HAVA") or "bluff" in out["action"].lower(), \
        f"floş board'da düz bluff-catch olmalı: tier={out['tier']} action={out['action']}"
