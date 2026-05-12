"""Test RangeMatrix mode switching + EV/Equity derivation.

Doesn't require PySide6 rendering — just exercises the public API.
"""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def matrix(qapp):
    from app.ui.components.range_matrix import RangeMatrix
    from app.solver.preflop_charts import CHARTS
    m = RangeMatrix()
    m.set_strategy(CHARTS["BTN-RFI-40"])
    yield m
    m.close()


def test_default_mode_is_strategy(matrix):
    assert matrix.mode == "strategy"


def test_set_mode_changes_internal_state(matrix):
    matrix.set_mode("ev")
    assert matrix.mode == "ev"
    matrix.set_mode("equity")
    assert matrix.mode == "equity"
    matrix.set_mode("strategy_ev")
    assert matrix.mode == "strategy_ev"


def test_invalid_mode_falls_back_to_strategy(matrix):
    matrix.set_mode("bogus")
    assert matrix.mode == "strategy"


def test_set_strategy_derives_ev_map_for_each_hand(matrix):
    # BTN-RFI-40 has 169 hands defined
    assert len(matrix._ev_map) == 169
    # AA should have positive EV (raise 100%)
    assert matrix._ev_map.get("AA", 0) > 0.5
    # 72o should have negative EV (fold 100%)
    assert matrix._ev_map.get("72o", 0) < 0


def test_set_strategy_derives_equity_map(matrix):
    assert len(matrix._equity_map) == 169
    # AA equity proxy → high (aggression)
    assert matrix._equity_map.get("AA", 0) > 0.8
    # 72o equity proxy → low (fold)
    assert matrix._equity_map.get("72o", 0) < 0.2


def test_clear_wipes_all_maps(matrix):
    matrix.clear()
    assert matrix._freq_map == {}
    assert matrix._ev_map == {}
    assert matrix._equity_map == {}


def test_hand_clicked_signal_emits(matrix, qapp):
    # Need a real click event — skip if we can't synthesise one
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QMouseEvent
    received = []
    matrix.hand_clicked.connect(lambda h: received.append(h))
    matrix.resize(520, 520)
    # Click the centre (TT cell at row 4, col 4 of 13)
    cx = matrix.width() / 2
    cy = matrix.height() / 2
    ev = QMouseEvent(
        QMouseEvent.MouseButtonPress,
        QPoint(int(cx), int(cy)),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    matrix.mousePressEvent(ev)
    assert len(received) >= 1
