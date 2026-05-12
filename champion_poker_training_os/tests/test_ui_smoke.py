"""UI smoke tests — instantiate every screen headlessly and verify no crash.

Skips automatically if PySide6 is not installed (CI / sandbox environments).
Runs with QT_QPA_PLATFORM=offscreen so no display server is required.
"""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")

# Force offscreen rendering BEFORE QApplication imports
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def state():
    from app.core.app_state import AppState
    return AppState()


# ── individual screens ───────────────────────────────────────────────────

def test_welcome_screen(qapp, state):
    from app.ui.screens.welcome import WelcomeScreen
    w = WelcomeScreen(state)
    assert w is not None
    w.close()


def test_dashboard_screen(qapp, state):
    from app.ui.screens.dashboard import DashboardScreen
    w = DashboardScreen(state)
    assert w is not None
    w.close()


def test_play_session_screen(qapp, state):
    from app.ui.screens.play_session import PlaySessionScreen
    w = PlaySessionScreen(state)
    assert w is not None
    w.close()


def test_hands_list_screen(qapp, state):
    from app.ui.screens.hands_list import HandsListScreen
    w = HandsListScreen(state)
    assert w is not None
    w.close()


def test_drill_builder_screen(qapp, state):
    from app.ui.screens.drill_builder import DrillBuilderScreen
    w = DrillBuilderScreen(state)
    assert w is not None
    w.close()


def test_gto_trainer_screen(qapp, state):
    from app.ui.screens.gto_trainer import GTOTrainerScreen
    w = GTOTrainerScreen(state)
    assert w is not None
    w.close()


def test_study_library_screen(qapp, state):
    from app.ui.screens.study_library import StudyLibraryScreen
    w = StudyLibraryScreen(state)
    assert w is not None
    w.close()


def test_spot_trainer_screen(qapp, state):
    from app.ui.screens.spot_trainer import SpotTrainerScreen
    w = SpotTrainerScreen(state)
    assert w is not None
    w.close()


def test_hand_analyzer_screen(qapp, state):
    from app.ui.screens.hand_analyzer import HandAnalyzerScreen
    w = HandAnalyzerScreen(state)
    assert w is not None
    w.close()


def test_fast_play_simulator_screen(qapp, state):
    from app.ui.screens.fast_play_simulator import FastPlaySimulatorScreen
    w = FastPlaySimulatorScreen(state)
    assert w is not None
    w.close()


def test_tournament_simulator_screen(qapp, state):
    from app.ui.screens.tournament_simulator import TournamentSimulatorScreen
    w = TournamentSimulatorScreen(state)
    assert w is not None
    w.close()


def test_tournament_play_screen(qapp, state):
    from app.ui.screens.tournament_play import TournamentPlayScreen
    w = TournamentPlayScreen(state)
    assert w is not None
    w.close()


def test_heads_up_trainer_screen(qapp, state):
    from app.ui.screens.heads_up_trainer import HeadsUpTrainerScreen
    w = HeadsUpTrainerScreen(state)
    assert w is not None
    w.close()


def test_icm_trainer_screen(qapp, state):
    from app.ui.screens.icm_trainer import IcmTrainerScreen
    w = IcmTrainerScreen(state)
    assert w is not None
    w.close()


def test_preflop_range_trainer_screen(qapp, state):
    from app.ui.screens.range_trainer import RangeTrainerScreen
    w = RangeTrainerScreen(state)
    assert w is not None
    w.close()


def test_postflop_trainer_screen(qapp, state):
    from app.ui.screens.postflop_trainer import PostflopTrainerScreen
    w = PostflopTrainerScreen(state)
    assert w is not None
    w.close()


def test_river_trainer_screen(qapp, state):
    from app.ui.screens.river_trainer import RiverTrainerScreen
    w = RiverTrainerScreen(state)
    assert w is not None
    w.close()


def test_math_lab_screen(qapp, state):
    from app.ui.screens.math_lab import MathLabScreen
    w = MathLabScreen(state)
    assert w is not None
    w.close()


def test_combat_trainer_screen(qapp, state):
    from app.ui.screens.combat_trainer import CombatTrainerScreen
    w = CombatTrainerScreen(state)
    assert w is not None
    w.close()


def test_leak_finder_screen(qapp, state):
    from app.ui.screens.leak_finder import LeakFinderScreen
    w = LeakFinderScreen(state)
    assert w is not None
    w.close()


def test_ai_coach_screen(qapp, state):
    from app.ui.screens.ai_coach import AiCoachScreen
    w = AiCoachScreen(state)
    assert w is not None
    w.close()


def test_knowledge_base_screen(qapp, state):
    from app.ui.screens.knowledge_base import KnowledgeBaseScreen
    w = KnowledgeBaseScreen(state)
    assert w is not None
    w.close()


def test_study_planner_screen(qapp, state):
    from app.ui.screens.study_planner import StudyPlannerScreen
    w = StudyPlannerScreen(state)
    assert w is not None
    w.close()


def test_reports_screen(qapp, state):
    from app.ui.screens.reports import ReportsScreen
    w = ReportsScreen(state)
    assert w is not None
    w.close()


def test_aggregated_reports_screen(qapp, state):
    from app.ui.screens.aggregated_reports import AggregatedReportsScreen
    w = AggregatedReportsScreen(state)
    assert w is not None
    w.close()


def test_range_viewer_screen(qapp, state):
    from app.ui.screens.range_viewer import RangeViewerScreen
    w = RangeViewerScreen(state)
    assert w is not None
    w.close()


def test_table_settings_screen(qapp, state):
    from app.ui.screens.table_settings import TableSettingsScreen
    w = TableSettingsScreen(state)
    assert w is not None
    w.close()


def test_settings_screen(qapp, state):
    from app.ui.screens.settings import SettingsScreen
    w = SettingsScreen(state)
    assert w is not None
    w.close()


# ── components ──────────────────────────────────────────────────────────

def test_range_matrix_widget(qapp):
    from app.ui.components.range_matrix import RangeMatrix
    from app.solver.preflop_charts import CHARTS
    m = RangeMatrix()
    m.set_strategy(CHARTS["BTN-RFI-40"])
    m.highlight_hand("AKs")
    m.close()


def test_live_poker_table_widget(qapp):
    from app.ui.components.live_poker_table import LivePokerTable
    t = LivePokerTable()
    t.update_state(None)  # tolerate None
    t.close()


def test_card_view_widget(qapp):
    from app.ui.components.card_view import CardView
    c = CardView("Ah")
    assert c is not None
    c.close()
