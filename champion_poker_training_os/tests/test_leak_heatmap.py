"""LeakHeatmap component tests."""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_leak_cell_severity_bands():
    from app.ui.components.leak_heatmap import LeakCell
    assert LeakCell(sample=10, correct=9).severity == "bright_green"  # 90%
    assert LeakCell(sample=10, correct=7).severity == "green"          # 70%
    assert LeakCell(sample=10, correct=5).severity == "amber"          # 50%
    assert LeakCell(sample=10, correct=2).severity == "red"            # 20%
    assert LeakCell(sample=0).severity == "unknown"


def test_leak_cell_accuracy_calculation():
    from app.ui.components.leak_heatmap import LeakCell
    assert LeakCell(sample=8, correct=6).accuracy == 0.75
    assert LeakCell(sample=0).accuracy == 0.0


def test_heatmap_set_data(qapp):
    from app.ui.components.leak_heatmap import LeakHeatmap, LeakCell
    h = LeakHeatmap()
    cells = {
        ("BB", "SRP"): LeakCell(sample=10, correct=4, ev_loss=8.0),
        ("BTN", "3BP"): LeakCell(sample=5, correct=4, ev_loss=2.0),
    }
    h.set_data(cells)
    assert h._cells[("BB", "SRP")].severity == "red"
    assert h._cells[("BTN", "3BP")].severity == "green"


def test_heatmap_set_data_from_leaks(qapp):
    from app.ui.components.leak_heatmap import LeakHeatmap
    h = LeakHeatmap()
    h.set_data_from_leaks([
        {"position": "BB", "pot_type": "SRP", "sample": 12,
         "total_ev_loss": 9.6, "avg_ev_loss": 0.8},
    ])
    cell = h._cells.get(("BB", "SRP"))
    assert cell is not None and cell.sample == 12


def test_heatmap_ignores_unknown_positions(qapp):
    from app.ui.components.leak_heatmap import LeakHeatmap
    h = LeakHeatmap()
    h.set_data_from_leaks([
        {"position": "NOT_A_POS", "pot_type": "SRP", "sample": 5,
         "total_ev_loss": 1.0, "avg_ev_loss": 0.2},
    ])
    assert h._cells == {}


def test_heatmap_grid_dimensions():
    from app.ui.components.leak_heatmap import POSITIONS, POT_TYPES
    assert len(POSITIONS) == 8
    assert len(POT_TYPES) == 5
    assert "BTN" in POSITIONS
    assert "SRP" in POT_TYPES
