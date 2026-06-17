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


def test_d235_board_two_pair_play_not_value():
    """D235: NON-pocket hero çift-eşli board'da board'un iki çiftini oynuyor (6,2 / A-A-4-4)
    → kicker-only, value-bet ETMEMELİ (eski: GÜÇLÜ→BET spew, gerçek eq ~%12)."""
    out = _spot(["6d", "2h"], ["As", "Ad", "4c", "4h"], 0.0)
    assert out["tier"] != "GÜÇLÜ", f"board-oynama GÜÇLÜ olmamalı: {out['tier']}"
    assert "BET (value)" not in out["action"], f"board-oynama value-bet etmemeli: {out['action']}"


def test_d235_real_two_pair_preserved():
    """KORUMA: gerçek top-two (K9 / K-9-7) → BET(value) KALMALI (regresyon yok)."""
    out = _spot(["Kh", "9d"], ["Ks", "9c", "7h", "2s"], 0.0)
    assert "BET" in out["action"], f"gerçek two-pair value kalmalı: {out['action']}"


def test_d239_board_trips_play_not_value():
    """D239: board'da trips (7-7-7) + hero o ranke sahip değil → kicker-only, value DEĞİL."""
    out = _spot(["Kh", "Jd"], ["7h", "5d", "2c", "7s", "7d"], 0.0)
    assert out["tier"] != "GÜÇLÜ", f"board-trips oynama GÜÇLÜ olmamalı: {out['tier']}"
    assert "BET (value)" not in out["action"]


def test_d239_board_quads_play_not_nut():
    """D239: board'da quads (3-3-3-3) + hero kicker → NUT DEĞİL (raise spew kapandı)."""
    out = _spot(["6h", "Tc"], ["3c", "3s", "3h", "3d", "5s"], 0.0)
    assert out["tier"] != "NUT", f"board-quads oynama NUT olmamalı: {out['tier']}"
    assert "RAISE" not in out["action"] and "BET (value)" not in out["action"]


def test_d239_real_trips_preserved():
    """KORUMA: hero gerçekten trips yapıyor (K7 / 7-7-2, hero'nun 7'si var) → BET value."""
    out = _spot(["Kh", "7d"], ["7h", "7s", "2c"], 0.0)
    assert "BET" in out["action"], f"gerçek trips value kalmalı: {out['action']}"


# ── D249: TEK-eşli board'da alt iki-çift (board çifti + hero düşük çift) over-value ──

def test_d249_low_two_pair_single_paired_board_not_value():
    """D249 (value-audit): non-pocket hero TEK-eşli board'da board-çifti + DÜŞÜK kendi
    çifti yapıyor (5s8s / K-J-J-Q-8: 88+JJ, hp=8<bp=J, gerçek eq ~%29) → GÜÇLÜ DEĞİL,
    value-bet ETMEMELİ (board-çift rank'ine sahip herkes trips yapar)."""
    out = _spot(["5s", "8s"], ["Kc", "Jc", "Jd", "Qd", "8h"], 4.0)
    assert out["tier"] != "GÜÇLÜ", f"alt iki-çift GÜÇLÜ olmamalı: {out['tier']}"
    assert "BET (value)" not in out["action"]


def test_d249_kings_up_preserved():
    """KORUMA: hero çifti board-çiftinin ÜSTÜNDE (K8 / J-J-K-3, hp=K>bp=J) → KK+JJ
    gerçek üst iki-çift → GÜÇLÜ kalmalı (regresyon yok)."""
    out = _spot(["Kh", "8d"], ["Jc", "Js", "Kd", "3h"], 0.0)
    assert out["tier"] in ("GÜÇLÜ", "NUT", "ORTA"), out["tier"]


def test_d249_real_top_two_on_paired_board_preserved():
    """KORUMA: iki board-TEKİLİNİ eşleyen gerçek top-two (K9 / K-9-7-7) → GÜÇLÜ kalmalı."""
    out = _spot(["Kh", "9d"], ["Kc", "9s", "7h", "7d"], 0.0)
    assert out["tier"] in ("GÜÇLÜ", "NUT"), out["tier"]
    assert "BET" in out["action"]


# ── D268: DÜZ ama board EŞLİ/TRIPS → DOLU geçer → NUT değil (value-audit residual) ──

def test_d268_straight_on_trips_board_not_nut():
    """Js9s / 8-Q-Q-T-Q: düz (8-9-T-J-Q) ama QQQ board → dolu/quads geçer (eq~%44).
    NUT/RAISE DEĞİL (eski: NUT 0.85 spew)."""
    out = _spot(["Js", "9s"], ["8d", "Qd", "Qh", "Th", "Qs"], 0.0)
    assert out["tier"] not in ("NUT", "GÜÇLÜ"), out["tier"]
    assert "RAISE" not in out["action"] and "BET (value)" not in out["action"]


def test_d268_straight_unpaired_board_preserved():
    """KORUMA: eşsiz board'da gerçek düz → NUT/GÜÇLÜ kalmalı (regresyon yok)."""
    out = _spot(["Th", "9d"], ["Jc", "8s", "7h", "2d", "Kc"], 0.0)
    assert out["tier"] in ("NUT", "GÜÇLÜ"), out["tier"]


def test_d268_straight_paired_board_capped():
    """Eşli board'da düz → dolu mümkün → NUT değil (cap ORTA/GÜÇLÜ)."""
    out = _spot(["Th", "9d"], ["Jc", "8s", "7h", "7d"], 0.0)
    assert out["tier"] != "NUT", out["tier"]


def test_d268_flush_untouched():
    """KORUMA: nut floş eşli board'da bile dokunulmaz (düz fix floş'u etkilemez)."""
    out = _spot(["Ah", "Kh"], ["Qh", "7h", "2h", "2c"], 0.0)
    assert out["tier"] in ("NUT", "GÜÇLÜ"), out["tier"]
