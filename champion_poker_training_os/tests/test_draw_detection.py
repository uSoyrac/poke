"""D267 (kullanıcı yakaladı): KQ/8-9-T-7 turn "HAVA" diyordu. İki bug:
(1) _draw_equity board'un 4-sıralısını (7-8-9-T) hero'nun OESD'si sanıp 8-out veriyordu
    (gerçekte gutshot: yalnız J board-düzünü geçer). Doğru sayım: çekme ancak board-TEK-
    BAŞINA'dan İYİ düz veriyorsa out (domine/chop düzler sayılmaz).
(2) tier: gerçek çekme (gutshot dahil) varsa HAVA değil DRAW (turn'de equity yarıya iner
    → 0.30 flop-eşiğini geçemez ama 'çekmen var' bilgisi önemli)."""
import types
from app.engine.hand_state import card_from_str, Street
from app.poker.soyrac_advisor import _draw_equity, soyrac_postflop_advice


def _de(hole, board):
    return _draw_equity([card_from_str(x) for x in hole], [card_from_str(x) for x in board])


def _tier(hole, board):
    h = [card_from_str(x) for x in hole]; b = [card_from_str(x) for x in board]
    hero = types.SimpleNamespace(hole_cards=h, stack=46.0, is_folded=False, is_eliminated=False)
    v = types.SimpleNamespace(hole_cards=[], stack=46.0, is_folded=False, is_eliminated=False)
    hd = types.SimpleNamespace(players=[hero, v], community=b, street=Street.TURN,
                               pot=46.0, active_count=2, to_call=lambda i: 0.0)
    return soyrac_postflop_advice(hd, 0)["tier"]


def test_user_hand_kq_gutshot_is_draw_not_air():
    """KQ / 8-9-T-7: J ile K-yüksek düz (gutshot, board-düzünü geçer) → DRAW, HAVA değil."""
    de, notes = _de(["Kh", "Qh"], ["8d", "9d", "Tc", "7h"])
    assert any("gutshot" in n for n in notes), notes
    assert not any("açık-uçlu" in n for n in notes), "board-run OESD sayılmamalı"
    assert _tier(["Kh", "Qh"], ["8d", "9d", "Tc", "7h"]) == "DRAW"


def test_dominated_board_straight_not_counted():
    """52o / 7-8-9-T: 6 ile 5-6-7-8-9 ama board 6-7-8-9-T (T-high) daha iyi → out YOK → HAVA."""
    de, notes = _de(["5c", "2d"], ["7h", "8d", "9c", "Tc"])
    assert de == 0.0 and not notes, (de, notes)
    assert _tier(["5c", "2d"], ["7h", "8d", "9c", "Tc"]) == "HAVA"


def test_real_oesd_preserved():
    """Gerçek OESD (hero kartı kullanan, board-only değil) → açık-uçlu(8) korunur."""
    for hole, board in [(["Jh", "Th"], ["9c", "8d", "2s"]),
                        (["Kh", "Qd"], ["Jc", "Ts", "2h"]),
                        (["7h", "6d"], ["5c", "4s", "Kh"])]:
        de, notes = _de(hole, board)
        assert any("açık-uçlu" in n for n in notes), (hole, board, notes)


def test_flush_and_wheel_preserved():
    assert any("floş" in n for n in _de(["Kh", "5h"], ["Ah", "2h", "9c"])[1])
    assert any("gutshot" in n for n in _de(["Ah", "2d"], ["3c", "4s", "Kh"])[1])  # wheel


def test_pure_air_stays_air():
    assert _tier(["7c", "2d"], ["Ah", "Kd", "Qs", "3h"]) == "HAVA"
