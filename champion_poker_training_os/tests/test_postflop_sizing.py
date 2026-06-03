"""GTO postflop advice — equity-duyarlı polarize bet sizing (ıslak board).

Modern GTO: ıslak board'da betting range POLARİZE olur → value + saf blöf
büyük basar, orta-güç eller küçük/check. Eskiden size yalnız board-texture'a
bağlıydı (equity'den bağımsız). Bu paket polarizasyonu doğrular.
"""
from __future__ import annotations

from app.poker.postflop_gto import cbet_strategy, classify_board


def _wet_board():
    # JT9 iki-renk: bağlı + ıslak (yüksek wetness)
    from app.engine.hand_state import Card
    tex = classify_board([Card("J", "h"), Card("T", "h"), Card("9", "s")])
    assert tex.wetness >= 0.5, f"board ıslak değil ({tex.wetness})"
    return tex


def _dry_board():
    from app.engine.hand_state import Card
    return classify_board([Card("A", "h"), Card("7", "d"), Card("2", "s")])


def test_value_bets_bigger_than_medium_on_wet():
    tex = _wet_board()
    _, size_value = cbet_strategy(0.78, tex, in_position=True, has_initiative=True)
    _, size_medium = cbet_strategy(0.48, tex, in_position=True, has_initiative=True)
    assert size_value > size_medium, (
        f"ıslak board value ({size_value}) orta-güçten ({size_medium}) büyük basmalı")


def test_pure_bluff_polarizes_big_on_wet():
    tex = _wet_board()
    _, size_bluff = cbet_strategy(0.22, tex, in_position=True, has_initiative=True)
    _, size_medium = cbet_strategy(0.48, tex, in_position=True, has_initiative=True)
    assert size_bluff >= 0.80, f"saf blöf ıslakta polar büyük olmalı ({size_bluff})"
    assert size_bluff > size_medium


def test_dry_board_keeps_small_range_bet():
    """Kuru board'da tek küçük range-bet (polarizasyon yok)."""
    tex = _dry_board()
    _, size_value = cbet_strategy(0.78, tex, in_position=True, has_initiative=True)
    assert size_value <= 0.5, f"kuru board range-bet küçük olmalı ({size_value})"


def test_sizes_stay_in_valid_range():
    tex = _wet_board()
    for eq in (0.10, 0.30, 0.50, 0.70, 0.95):
        freq, size = cbet_strategy(eq, tex, in_position=True, has_initiative=True)
        assert 0.0 <= freq <= 0.95
        assert 0.2 <= size <= 1.0
