"""LEAK-FIX (D218): EŞLİ BOARD'da DÜŞÜK POCKET PAIR overvaluation.

BUG (kullanıcı canlı yakaladı): 22 elinde, flop tüm overcard, check-check river'a
kadar gitti, river'da koç RAISE/BET(value) öneriyor — ama "adamın low pair'i bile
beni geçiyor". Kök sebep: _hand_strength board'un kendi çiftini (örn. KK) hero'nun
'iki çift'inin yarısı sayıyor → 22 + board-KK = 'two pair' (0.66 GÜÇLÜ) → value-bet
spew. Gerçekte board'u oynuyorsun; her üst-pocket seni geçer → bluff-catch/hava.

Düzeltme COACH katmanında (soyrac_postflop_advice) — _hand_strength bot beyni,
fidelity 0-sapma korunsun diye orada DEĞİL.
"""
import types
from app.engine.hand_state import Street, card_from_str
from app.poker.soyrac_advisor import soyrac_postflop_advice


def _spot(hole_s, board_s, to_call):
    hole = [card_from_str(x) for x in hole_s]
    board = [card_from_str(x) for x in board_s]
    hero = types.SimpleNamespace(hole_cards=hole, stack=80.0, is_folded=False, is_eliminated=False)
    vill = types.SimpleNamespace(hole_cards=[], stack=80.0, is_folded=False, is_eliminated=False)
    hand = types.SimpleNamespace(players=[hero, vill], community=board, street=Street.RIVER,
                                 pot=13.0, active_count=2, to_call=lambda i: to_call)
    return soyrac_postflop_advice(hand, 0)


def test_low_pocket_paired_board_not_value_bet():
    """22 / K-K-9-7-4 checked-to → BET(value) ÖNERME (board oynuyorsun, spew)."""
    out = _spot(["2h", "2d"], ["Ks", "Kd", "9c", "7h", "4s"], 0.0)
    assert "BET (value)" not in out["action"], f"22 eşli board value-bet etmemeli: {out['action']}"
    assert out["tier"] != "GÜÇLÜ", f"22 eşli board GÜÇLÜ olmamalı: {out['tier']}"
    assert out["action"].startswith("CHECK"), f"checked-to → CHECK beklenir: {out['action']}"


def test_low_pocket_paired_board_facing_bet_not_clean_call():
    """22 / K-K-9-7-4 facing-bet → GÜÇLÜ-value CALL DEĞİL (bluff-catch/fold)."""
    out = _spot(["2h", "2d"], ["Ks", "Kd", "9c", "7h", "4s"], 4.0)
    assert out["tier"] != "GÜÇLÜ", f"facing-bet 22 GÜÇLÜ olmamalı: {out['tier']}"


def test_double_paired_board_plays_board():
    """22 / K-K-9-9-4 → tamamen board oynuyorsun → ASLA value-bet."""
    out = _spot(["2h", "2d"], ["Ks", "Kd", "9c", "9h", "4s"], 0.0)
    assert "BET (value)" not in out["action"], f"board oynarken value-bet spew: {out['action']}"


def test_overpair_on_paired_board_still_value():
    """KORUMA: AA / K-K-7-4 = aces&kings, gerçekten güçlü → BET(value) KALMALI."""
    out = _spot(["Ah", "Ad"], ["Ks", "Kd", "7c", "4h"], 0.0)
    assert out["tier"] in ("GÜÇLÜ", "NUT"), f"AA eşli board güçlü kalmalı: {out['tier']}"
    assert "BET" in out["action"], f"AA value-bet etmeli: {out['action']}"


def test_real_two_pair_unpaired_board_still_value():
    """KORUMA: K9 / K-9-7-4-2 = gerçek top-two → BET(value) KALMALI (regresyon yok)."""
    out = _spot(["Kh", "9d"], ["Ks", "9c", "7h", "4s", "2d"], 0.0)
    assert "BET" in out["action"], f"gerçek iki-çift value kalmalı: {out['action']}"
