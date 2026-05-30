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
