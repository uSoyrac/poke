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


def test_wheel_on_4flush_board_is_bluffcatch():
    """A4 wheel / 4-SİNEK board (Qc) → checked-to CHECK (tek çubuk floş yapar = gerçekten
    tehlikeli → bluff-catch, value değil). 4-floş genuinely dangerous."""
    out = _spot("Ah 4h", "5h Tc 2c Qc 3c", 0.0)
    assert out["tier"] != "HAVA", f"made düz HAVA olmamalı: {out['tier']}"
    assert "BET (value)" not in out["action"], f"4-floş'ta düz value-bet etmemeli: {out['action']}"
    assert out["action"].startswith("CHECK"), f"4-floş checked-to → CHECK: {out['action']}"


def test_wheel_on_4flush_facing_bet_bluffcatch():
    """A4 wheel / 4-floş board, bet'e karşı → bluff-catch (floş-haircut'lı)."""
    out = _spot("Ah 4h", "5h Tc 2c Qc 3c", 3.0)
    assert out["tier"] in ("BLUFF-CATCH", "ZAYIF", "HAVA") or "bluff" in out["action"].lower(), \
        f"4-floş'ta düz bluff-catch olmalı: tier={out['tier']} action={out['action']}"


def test_wheel_on_3flush_board_is_value():
    """KULLANICI GERÇEK SPOTU (D220): A4 wheel / 3-SİNEK board (Qh, sadece T-2-3 sinek) →
    floş ancak rakipte 2-çubukla (nadir) → düz hâlâ DEĞER eli (eq ~%85-93). checked-to →
    BET (value), bluff-catch DEĞİL. Eski bug: 3-floş'a 4-floş gibi 0.28 haircut → yanlış CHECK."""
    out = _spot("Ah 4h", "5h Tc 2c Qh 3c", 0.0)
    assert out["tier"] == "NUT", f"3-floş'ta wheel düz NUT kalmalı: {out['tier']}"
    assert "BET (value)" in out["action"], f"3-floş'ta düz value-bet etmeli: {out['action']}"


def test_wheel_on_3flush_facing_bet_raises():
    """A4 wheel / 3-floş board, bet'e karşı → RAISE (değer), bluff-catch-call değil."""
    out = _spot("Ah 4h", "5h Tc 2c Qh 3c", 3.0)
    assert "RAISE" in out["action"], f"3-floş'ta düz bet'e RAISE etmeli: {out['action']}"


def test_board_threat_suit_count_aware():
    """_board_threat suit-sayısına duyarlı: 4-floş ≫ 3-floş haircut (kök kural)."""
    from app.poker.soyrac_advisor import _board_threat
    b3 = [card_from_str(x) for x in "5h Tc 2c Qh 3c".split()]   # 3 sinek
    b4 = [card_from_str(x) for x in "5h Tc 2c Qc 3c".split()]   # 4 sinek
    hole = [card_from_str("Ah"), card_from_str("4h")]
    t3 = _board_threat(b3, "straight", hole)[0]
    t4 = _board_threat(b4, "straight", hole)[0]
    assert t3 < 0.15, f"3-floş küçük tehdit olmalı: {t3}"
    assert t4 >= 0.30, f"4-floş büyük tehdit olmalı: {t4}"
