"""AI Coach chat-history persistence regression tests.

User flow guarded:
  1. Open AI Coach → ask a question → answer appears in transcript.
  2. Navigate away (hideEvent fires) → transcript snapshot saved to AppState.
  3. Navigate back (showEvent fires) → transcript restored.
  4. Press 'Temizle' → both view and stored snapshot cleared.
"""
from __future__ import annotations

import os
import pytest


def _ensure_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _make_screen():
    _ensure_qt()
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app.core.app_state import AppState
    from app.ui.screens.ai_coach import AiCoachScreen
    state = AppState()
    w = AiCoachScreen(state)
    w.show()
    app.processEvents()
    return w, state, app


def test_app_state_has_coach_chat_history_field():
    """The persistence-anchor field must exist on AppState."""
    from app.core.app_state import AppState
    s = AppState()
    assert hasattr(s, "coach_chat_history")
    assert s.coach_chat_history == ""


def test_chat_is_saved_on_hide_and_restored_on_show():
    w, state, app = _make_screen()
    # Simulate user typing into the transcript
    w.history.setPlainText("User: Bir spot anlat.\n\nCoach: ...")
    # Trigger hide → save
    w.hide()
    app.processEvents()
    assert "Bir spot anlat" in state.coach_chat_history

    # Build a fresh screen with the SAME state, show it, expect restore
    from app.ui.screens.ai_coach import AiCoachScreen
    w2 = AiCoachScreen(state)
    w2.show()
    app.processEvents()
    assert "Bir spot anlat" in w2.history.toPlainText()


def test_clear_history_wipes_persisted_snapshot():
    w, state, app = _make_screen()
    w.history.setPlainText("Persist me.")
    w.hide()
    app.processEvents()
    assert "Persist me." in state.coach_chat_history

    w.show()
    app.processEvents()
    w._clear_history()
    assert state.coach_chat_history == ""
    # And a fresh screen built after clear should NOT restore the old text
    from app.ui.screens.ai_coach import AiCoachScreen
    w3 = AiCoachScreen(state)
    w3.show()
    app.processEvents()
    assert "Persist me." not in w3.history.toPlainText()
