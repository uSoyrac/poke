"""S1 guard: ESC canlı turnuvayı ONAYSIZ silmemeli (D123).

Bug (canlı test): ESC doğrudan _end_and_restart / _end_mtt'ye bağlıydı →
kazara basılan ESC çalışan turnuvayı (sıralama/stack/field) anında siliyordu.
Fix: canlı (is_complete=False) turnuva varken _confirm_abort() onayı; reddedilirse
teardown ÇALIŞMAZ. Tamamlanmış/yok ise onaysız geçer.
"""
from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass

import pytest
from PySide6.QtWidgets import QApplication
from app.core.app_state import AppState

_app = QApplication.instance() or QApplication([])


class _FakeTournament:
    def __init__(self, complete=False):
        self.is_complete = complete


def _screen_classes():
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    from app.ui.screens.play_session import PlaySessionScreen
    return [
        (TournamentSimulatorScreen, "_end_and_restart"),
        (PlaySessionScreen, "_end_mtt"),
    ]


@pytest.mark.parametrize("cls,method", _screen_classes())
def test_esc_declined_keeps_live_tournament(cls, method):
    scr = cls(AppState())
    scr.tournament = _FakeTournament(complete=False)
    scr._confirm_abort = lambda: False           # kullanıcı 'Hayır'
    getattr(scr, method)()
    assert scr.tournament is not None, "Onay reddedilince canlı turnuva SİLİNMEMELİ"


@pytest.mark.parametrize("cls,method", _screen_classes())
def test_esc_confirmed_tears_down(cls, method):
    scr = cls(AppState())
    scr.tournament = _FakeTournament(complete=False)
    scr._confirm_abort = lambda: True            # kullanıcı 'Evet'
    getattr(scr, method)()
    assert scr.tournament is None, "Onaylanınca turnuva sonlanmalı"


@pytest.mark.parametrize("cls,method", _screen_classes())
def test_completed_tournament_no_confirm(cls, method):
    """Tamamlanmış turnuvada onay sorulmamalı (frictionless setup'a dön)."""
    scr = cls(AppState())
    scr.tournament = _FakeTournament(complete=True)
    asked = {"v": False}
    def _spy():
        asked["v"] = True
        return True
    scr._confirm_abort = _spy
    getattr(scr, method)()
    assert asked["v"] is False, "Tamamlanmış turnuvada onay sorulmamalı"
    assert scr.tournament is None
