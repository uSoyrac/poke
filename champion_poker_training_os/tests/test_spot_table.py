"""spot_table.parse_cards — bitişik + boşluklu kart formatları (ICM/Math masası)."""
from __future__ import annotations

from app.ui.components.spot_table import parse_cards


def test_concatenated_two_cards():
    assert parse_cards("AsKh") == ["As", "Kh"]


def test_concatenated_board_three():
    assert parse_cards("7c2d9s") == ["7c", "2d", "9s"]


def test_space_separated():
    assert parse_cards("As Kh") == ["As", "Kh"]


def test_symbol_suits_spaced():
    assert parse_cards("A♦ K♥") == ["A♦", "K♥"]


def test_empty_and_preflop():
    assert parse_cards("") == []
    assert parse_cards("preflop") == []
    assert parse_cards(None) == []
    assert parse_cards("—") == []


def test_table_size_parsing():
    from app.ui.components.spot_table import _table_size
    assert _table_size("9-max") == 9
    assert _table_size("4-max") == 4
    assert _table_size("HU") == 2
    assert _table_size("2-max") == 2
    assert _table_size("6-max") == 6
    assert _table_size("") == 6           # varsayılan


def test_icm_drill_builds_full_table():
    from app.ui.screens.icm_trainer import _generate_icm_drills
    from app.ui.components.spot_table import _seats_from_spot
    for d in _generate_icm_drills(8):
        seats, _, _ = _seats_from_spot(d)
        # Koltuk sayısı pot/oyuncu sayısıyla tutarlı, asla 9'u aşmaz
        assert 2 <= len(seats) <= 9
