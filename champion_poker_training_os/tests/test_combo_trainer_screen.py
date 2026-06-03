"""Combo Trainer ekranı — kurulum + cevap akışı + nav kaydı smoke."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
except Exception:
    pass


def test_screen_builds_and_deals_spot():
    from PySide6.QtWidgets import QApplication
    from app.ui.screens.combo_trainer import ComboTrainerScreen
    app = QApplication.instance() or QApplication([])
    scr = ComboTrainerScreen()
    assert scr._spot is not None
    assert scr._spot["street"] == "river"
    assert len(scr._spot["board"].split()) == 5


def test_answer_grades_and_reveals():
    from PySide6.QtWidgets import QApplication
    from app.ui.screens.combo_trainer import ComboTrainerScreen
    app = QApplication.instance() or QApplication([])
    scr = ComboTrainerScreen()
    scr._answer("CALL")
    assert scr._answered
    assert scr._n == 1
    assert scr._reveal.isVisible() or scr._reveal.text()  # reveal dolu
    # ikinci cevap aynı spotta sayılmaz
    scr._answer("FOLD")
    assert scr._n == 1


def test_next_spot_resets():
    from PySide6.QtWidgets import QApplication
    from app.ui.screens.combo_trainer import ComboTrainerScreen
    app = QApplication.instance() or QApplication([])
    scr = ComboTrainerScreen()
    scr._answer("CALL")
    scr._new_spot()
    assert not scr._answered
    assert scr._call_btn.isEnabled()


def test_registered_in_nav():
    from app.main import NAV_ITEMS
    assert "Combo Trainer" in NAV_ITEMS
