"""Çok-sokaklı plan — el sınıfı → kaç sokak value/barrel, scare kartları."""
from __future__ import annotations

from app.poker.street_plan import coach_plan_line, street_plan


def test_set_gets_value_plan():
    # 99 board 9-5-2 → set → güçlü value, çok sokak
    p = street_plan("9h 9d", "9s 5c 2d")
    assert p["kind"] == "güçlü value"
    assert "VALUE" in p["plan"] and p["streets"] == 2


def test_top_pair_thin_value():
    # AK board A-7-2 → top pair → ince value (pot kontrol river)
    p = street_plan("Ah Kd", "As 7c 2d")
    assert "top pair" in p["kind"]
    assert "İNCE value" in p["plan"]


def test_flush_draw_semibluff():
    # iki kupa + board iki kupa → flush draw → semi-bluff
    p = street_plan("Ah 5h", "Kh 8h 2c")
    assert "semi-bluff" in p["kind"]
    assert "SEMI-BLUFF" in p["plan"]
    assert p["draw_eq"] >= 0.3


def test_middle_pair_pot_control():
    # board K-8-3, hero 8x → orta pair → pot kontrol
    p = street_plan("8d 7d", "Ks 8c 3h")
    assert p["kind"] == "orta pair (showdown)"
    assert "POT KONTROL" in p["plan"]


def test_air_polarized_or_giveup():
    # board K-Q-5, hero 7-2 air, no draw
    p = street_plan("7c 2d", "Ks Qh 5d")
    assert p["kind"] == "hava (air)"
    assert "POLARİZE" in p["plan"] or "give-up" in p["plan"]


def test_turn_has_one_street_left():
    p = street_plan("9h 9d", "9s 5c 2d 3h")   # turn (4 kart)
    assert p["streets"] == 1


def test_coach_line_and_invalid():
    p = street_plan("9h 9d", "9s 5c 2d")
    assert "El:" in coach_plan_line(p)
    # geçersiz board
    assert street_plan("Ah Kd", "Ah")["plan"] == ""
