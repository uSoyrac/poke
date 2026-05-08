"""Tests for session-feature additions: pending_spot_id, weekly progress, hero seat."""
from __future__ import annotations

import datetime as dt

import pytest


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """Run each test against a fresh SQLite file."""
    from app.core import config as cfg
    from app.db import repository
    db_path = tmp_path / "champion_test.db"
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    repository.initialize_database()
    yield db_path


# --- pending_spot_id state ---------------------------------------------------

def test_app_state_pending_spot_id_initially_none():
    from app.core.app_state import AppState
    s = AppState()
    assert s.pending_spot_id is None


def test_app_state_pending_spot_id_assignable():
    from app.core.app_state import AppState
    s = AppState()
    s.pending_spot_id = "REPLAY-DEMO-0001"
    assert s.pending_spot_id == "REPLAY-DEMO-0001"


# --- Weekly progress chart data --------------------------------------------

def test_weekly_progress_returns_seven_days_default(isolated_db):
    from app.training.weekly_stats import collect_weekly_stats
    days = collect_weekly_stats()
    assert len(days) == 7
    today = dt.date.today()
    assert days[-1]["date"] == today
    # All zero on a fresh DB
    assert all(d["drills"] == 0 and d["hands"] == 0 for d in days)


def test_weekly_progress_picks_up_played_hands(isolated_db):
    from app.db.repository import save_played_hand
    from app.training.weekly_stats import collect_weekly_stats

    save_played_hand({
        "hand_id": 1,
        "hero_cards": "AsKh",
        "community": "Ah7c2d",
        "pot": 12.5,
        "hero_invested": 5.0,
        "hero_profit": 7.5,
        "hero_won": 1,
        "winner_hand_name": "Top pair",
        "streets_seen": 2,
    })
    days = collect_weekly_stats()
    today_row = days[-1]
    assert today_row["hands"] >= 1
    assert today_row["profit_bb"] >= 7.0


# --- Hero-seat clamp logic --------------------------------------------------

@pytest.mark.parametrize("n,seat_input,expected", [
    (6, 1, 0),
    (6, 6, 5),
    (2, 2, 1),
    (11, 11, 10),
    (4, 99, 3),     # clamped
    (4, 0, 0),      # already 0
])
def test_hero_seat_clamping(n: int, seat_input: int, expected: int):
    """Mirrors the formula used in PlaySessionScreen._start_session."""
    hero_seat = max(0, min(n - 1, seat_input - 1))
    assert hero_seat == expected


# --- Leak detector: combined source -----------------------------------------

def test_leak_detector_handles_played_hands_shape():
    """Played-hands rows mapped to imported_hands shape should be detector-safe."""
    from app.leaks.imported_leak_detector import detect_leaks

    # Simulate the normaliser output from leak_finder._played_hands_normalised
    rows = []
    for i in range(25):
        rows.append({
            "external_id": str(i),
            "site": "Champion OS",
            "format": "Cash",
            "date": "",
            "hero_position": "BTN",
            "hero_cards": "AhKh",
            "board": "",
            "pot_bb": 5.0,
            "hero_profit_bb": -1.0,
            "ev_loss": 0.0,
            "pot_type": "SRP",
            "preflop_actions": "F" if i % 2 == 0 else "RC",
            "flop_actions": "",
            "turn_actions": "",
            "river_actions": "",
        })
    leaks = detect_leaks(rows)
    # Should at least produce some output and not crash
    assert isinstance(leaks, list)
    assert all("name" in l and "severity" in l for l in leaks)


# --- SolverFrequencyBar imported flag ---------------------------------------

def test_solver_frequency_bar_accepts_imported_kwarg():
    """Smoke test that the imported flag is wired up (no crash)."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app.ui.components.solver_bar import SolverFrequencyBar
    bar = SolverFrequencyBar("call", 0.45, 1.20, "33% pot", imported=True)
    bar2 = SolverFrequencyBar("fold", 0.55, 0.0, "", imported=False)
    assert bar is not None
    assert bar2 is not None
