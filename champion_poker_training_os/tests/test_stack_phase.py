"""Canlı stack-derinliği faz koçu — Playbook MTT Stack Fazları ile bağlı.

stack_phase(bb) → deep/mid/short/pushfold. Hero'nun fazı değişince koç BİR KEZ
o faza özel stratejiyi hatırlatır (spam yok).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass

from app.simulator.mtt_field import stack_phase


def test_phase_boundaries():
    assert stack_phase(60)[0] == "deep"
    assert stack_phase(40)[0] == "deep"
    assert stack_phase(39)[0] == "mid"
    assert stack_phase(20)[0] == "mid"
    assert stack_phase(19)[0] == "short"
    assert stack_phase(10)[0] == "short"
    assert stack_phase(9)[0] == "pushfold"
    assert stack_phase(3)[0] == "pushfold"


def test_phase_has_tag_and_coach_text():
    for bb in (60, 30, 15, 6):
        key, tag, txt = stack_phase(bb)
        assert tag and len(txt) > 30
        assert "Playbook" in stack_phase(60)[2]   # deep faz Playbook'a atıf


def test_stack_coach_fires_once_per_phase():
    from PySide6.QtWidgets import QApplication
    from app.core.app_state import AppState
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    app = QApplication.instance() or QApplication([])
    scr = TournamentSimulatorScreen(AppState())
    msgs = []
    scr.coach_message.connect(msgs.append)
    scr._maybe_stack_coach(50)   # deep
    scr._maybe_stack_coach(45)   # hâlâ deep → tekrar YOK
    assert sum("Stack fazı" in m for m in msgs) == 1
    scr._maybe_stack_coach(15)   # short → yeni uyarı
    assert sum("Stack fazı" in m for m in msgs) == 2
    scr._maybe_stack_coach(8)    # push/fold → yeni uyarı
    assert sum("Stack fazı" in m for m in msgs) == 3
