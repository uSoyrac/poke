"""Verify GTOTrainerScreen's interactive elements actually wire up.

Tests that:
  • _PositionChip emits clicked(position) on mouse press
  • Tab buttons exist and switching mode changes the matrix
  • _HandComboCard emits clicked(combo) on mouse press
  • _on_position_clicked() rewires self.index to a matching drill
"""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def state():
    from app.core.app_state import AppState
    return AppState()


@pytest.fixture
def trainer(qapp, state):
    from app.ui.screens.gto_trainer import GTOTrainerScreen
    s = GTOTrainerScreen(state)
    yield s
    s.close()


# ── _PositionChip click ──────────────────────────────────────────────────

def test_position_chip_emits_on_click(qapp):
    from app.ui.screens.gto_trainer import _PositionChip
    chip = _PositionChip("BTN", 40, [("Fold", "fold"), ("Raise 2.3", "raise")], is_hero=False)
    received = []
    chip.clicked.connect(lambda p: received.append(p))
    ev = QMouseEvent(
        QMouseEvent.MouseButtonPress, QPoint(10, 10),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    chip.mousePressEvent(ev)
    assert received == ["BTN"]


# ── _HandComboCard click ─────────────────────────────────────────────────

def test_hand_combo_card_emits_on_click(qapp):
    from app.ui.screens.gto_trainer import _HandComboCard
    card = _HandComboCard("A♠K♥", {"raise": 1.0})
    received = []
    card.clicked.connect(lambda c: received.append(c))
    ev = QMouseEvent(
        QMouseEvent.MouseButtonPress, QPoint(5, 5),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    card.mousePressEvent(ev)
    assert received == ["A♠K♥"]


# ── Tab switching ────────────────────────────────────────────────────────

def test_tab_switching_changes_matrix_mode(trainer):
    trainer._switch_tab("EV")
    assert trainer._matrix.mode == "ev"
    trainer._switch_tab("Equity")
    assert trainer._matrix.mode == "equity"
    trainer._switch_tab("Strategy + EV")
    assert trainer._matrix.mode == "strategy_ev"
    trainer._switch_tab("Strategy")
    assert trainer._matrix.mode == "strategy"


def test_tab_buttons_constructed(trainer):
    expected_tabs = {"Strategy", "Strategy + EV", "EV", "Equity",
                     "Solver Tree", "Runout Comparison", "Aggregate Reports"}
    assert set(trainer._tab_buttons.keys()) == expected_tabs


# ── Position click switches the active spot ──────────────────────────────

def test_position_click_switches_active_spot(trainer):
    # Drill catalog has multiple positions — verify clicking a different
    # position lands self.index on a drill with that position.
    initial_index = trainer.index
    initial_pos = trainer.drills[initial_index].get("position")
    # Pick a different position present in the catalog
    other = next(d.get("position") for d in trainer.drills if d.get("position") != initial_pos)
    trainer._on_position_clicked(other)
    new_pos = trainer.drills[trainer.index].get("position")
    assert new_pos == other


def test_next_spot_button_advances_index(trainer):
    initial = trainer.index
    trainer._next_spot()
    # Should change (modulo catalog wrap)
    assert trainer.index != initial or len(trainer.drills) == 1
