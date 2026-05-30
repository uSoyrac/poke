"""MTT/Quiz/Study Library UI düzeltmeleri — sayaç görünürlüğü, kart
render güvenilirliği, Study Library filtre→matris dinamizmi."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── KART EŞLEMESİ (saf, Qt'siz) ──────────────────────────────────────
def test_hand_key_to_cards():
    from app.ui.components.card_view import hand_key_to_cards
    assert hand_key_to_cards("AKs") == ("As", "Ks")      # suited → aynı suit
    assert hand_key_to_cards("AKo") == ("As", "Kh")      # offsuit → ayrı suit
    assert hand_key_to_cards("77") == ("7s", "7h")       # pair
    assert hand_key_to_cards("") == ("", "")             # geçersiz


def test_two_card_hand_updates(qapp):
    from app.ui.components.card_view import TwoCardHand
    w = TwoCardHand(size="xl")
    w.set_hand("QQ")
    assert w._c1.rank == "Q" and w._c2.rank == "Q"
    w.set_hand("T9s")
    assert w._c1.rank == "T" and w._c2.rank == "9"


# ── SAYAÇ GÖRÜNÜRLÜĞÜ ─────────────────────────────────────────────────
def test_mtt_timer_idle_until_shown(qapp):
    from app.ui.screens.mtt_trainer import MTTTrainerScreen
    s = MTTTrainerScreen(None)
    # init'te sayaç ÇALIŞMAMALI (arka planda akıp SÜRE DOLDU'ya düşmemeli)
    assert not s._timer.isActive()
    assert s._spot is not None          # ama spot hazır (ekran boş değil)
    s.show()
    qapp.processEvents()
    assert s._timer.isActive()          # görününce başlar
    s.hide()
    qapp.processEvents()
    assert not s._timer.isActive()      # gizlenince durur


def test_quiz_timer_idle_until_shown(qapp):
    from app.ui.screens.quiz_trainer import QuizTrainerScreen
    s = QuizTrainerScreen(None)
    assert not s._timer.isActive()
    assert s._current_spot is not None
    s.show()
    qapp.processEvents()
    assert s._timer.isActive()
    s.hide()
    qapp.processEvents()
    assert not s._timer.isActive()


# ── STUDY LIBRARY FİLTRE → MATRİS ────────────────────────────────────
def test_study_filters_drive_matrix(qapp):
    from app.core.app_state import AppState
    from app.ui.screens.study_library import StudyLibraryScreen
    s = StudyLibraryScreen(AppState())
    # default: BTN RFI 100bb cash
    assert s.range_grid.position == "BTN"
    assert s.range_grid.mode == "cash"
    assert s.range_grid.stack_depth == 100

    s.filter_boxes["Format"].setCurrentText("MTT")
    s.filter_boxes["Position"].setCurrentText("LJ")
    s.filter_boxes["Stack"].setCurrentText("40bb")
    # LJ → MP alias, MTT mode, 40bb stack matrise yansımalı
    assert s.range_grid.position == "MP"
    assert s.range_grid.mode == "MTT"
    assert s.range_grid.stack_depth == 40
    # node başlığı ve özet de güncel
    assert "MP" in s.node_title.text() and "MTT" in s.node_title.text()


def test_study_short_stack_mtt_is_pushfold(qapp):
    from app.core.app_state import AppState
    from app.ui.screens.study_library import StudyLibraryScreen
    s = StudyLibraryScreen(AppState())
    s.filter_boxes["Format"].setCurrentText("MTT")
    s.filter_boxes["Stack"].setCurrentText("15bb")
    assert s.range_grid.scenario == "Push/Fold"


def test_study_vs_3bet_scenario(qapp):
    from app.core.app_state import AppState
    from app.ui.screens.study_library import StudyLibraryScreen
    s = StudyLibraryScreen(AppState())
    s.filter_boxes["Scenario"].setCurrentText("3BP")
    assert s.range_grid.scenario == "vs 3-bet"


def test_node_summary_sums_to_100(qapp):
    from app.ui.screens.study_library import _node_summary
    summ = _node_summary("BTN", "RFI", 100, "cash")
    total = summ["raise"] + summ["call"] + summ["fold"]
    assert abs(total - 100.0) < 0.5
    # BTN RFI 100bb geniş bir açış range'i (~%40-55)
    assert 35 <= summ["raise"] + summ["call"] <= 60


def test_node_summary_tighter_when_shorter(qapp):
    """40bb MTT açış range'i 100bb cash'ten dar olmalı."""
    from app.ui.screens.study_library import _node_summary
    deep = _node_summary("MP", "RFI", 100, "cash")
    short = _node_summary("MP", "RFI", 40, "MTT")
    assert short["raise"] + short["call"] <= deep["raise"] + deep["call"] + 1
