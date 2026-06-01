"""Oyun deneyimi — bot hız kontrolü + bahis-boyutu klavye kısayolları."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _cash(qapp):
    from app.core.app_state import AppState
    from app.ui.screens.play_session import PlaySessionScreen
    w = PlaySessionScreen(AppState())
    w._start()                      # cash sayfasını kur
    qapp.processEvents()
    return w


def test_cash_speed_control(qapp):
    w = _cash(qapp)
    assert w._bot_timer.interval() == 450          # Normal varsayılan
    w.speed_combo.setCurrentIndex(3)               # Turbo
    assert w._bot_timer.interval() == 90
    w.speed_combo.setCurrentIndex(0)               # Yavaş
    assert w._bot_timer.interval() == 750


def test_cash_bet_size_keys(qapp):
    w = _cash(qapp)
    v = w.size_slider.value()
    w._key_action("+")
    assert w.size_slider.value() == v + 5
    w._key_action("-")
    assert w.size_slider.value() == v


def test_cash_size_key_clamped(qapp):
    w = _cash(qapp)
    w.size_slider.setValue(w.size_slider.maximum())
    w._key_action("+")                              # taşmamalı
    assert w.size_slider.value() == w.size_slider.maximum()


def test_mtt_speed_and_size(qapp):
    from app.core.app_state import AppState
    from app.ui.screens.play_session import PlaySessionScreen
    w = PlaySessionScreen(AppState())
    w._format = "mtt"
    w._start_mtt()
    qapp.processEvents()
    w.mtt_speed_combo.setCurrentIndex(3)
    assert w._mtt_bot_timer.interval() == 90
    v = w.mtt_size_slider.value()
    w._key_action_mtt("+")
    assert w.mtt_size_slider.value() == v + 5
