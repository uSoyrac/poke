"""Oyuncu koltuğu hover HUD'u — profil adı + istatistik + exploit ipucu."""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _seat_with_hud(qapp):
    from PySide6.QtWidgets import QWidget
    from app.ui.components.poker_table import _Seat, SeatState
    host = QWidget()
    seat = _Seat(host)
    seat._keepalive = host          # GC host'u silmesin (C++ nesne yaşasın)
    hud = {"archetype": "Shark", "vpip": 22, "pfr": 19, "three_bet": 11,
           "aggression": 3.2, "af": 3.2, "fold_to_cbet": 56, "river_bluff": 0.36,
           "call_down": 0.30, "overbet_freq": 0.07,
           "notes": "Strong reg — exploits leaks."}
    st = SeatState(pos="BTN", name="villain_3", stack=100, bet=0,
                   is_hero=False, hud_stats=hud, animal="🦁 Lion")
    seat.apply(st, show_name=True)
    return seat


def test_hover_shows_profile_and_stats(qapp):
    seat = _seat_with_hud(qapp)
    tip = seat.card.toolTip()
    assert "Shark" in tip            # profil adı
    assert "Lion" in tip             # Hellmuth hayvan-tipi
    assert "VPIP" in tip and "PFR" in tip and "3bet" in tip
    assert "AF" in tip and "F-cbet" in tip
    assert "exploits leaks" in tip   # exploit ipucu (notes)


def test_hover_plain_values_present(qapp):
    seat = _seat_with_hud(qapp)
    plain = re.sub("<[^>]+>", " ", seat.card.toolTip())
    assert "22%" in plain and "19%" in plain      # VPIP/PFR
    assert "3.2" in plain                          # AF


def test_hero_seat_has_no_hud(qapp):
    from PySide6.QtWidgets import QWidget
    from app.ui.components.poker_table import _Seat, SeatState
    host = QWidget()
    seat = _Seat(host)
    seat._keepalive = host
    st = SeatState(pos="BTN", name="", stack=100, bet=0, is_hero=True)
    seat.apply(st, show_name=True)
    assert seat.card.toolTip() == ""   # hero kendi profilini görmez
