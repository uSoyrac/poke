"""Tests for AdaptiveEngine SQLite persistence + spot snapshot helpers."""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    """Run each test against a fresh SQLite file in a temp directory."""
    from app.core import config as cfg
    from app.db import repository
    db_path = tmp_path / "champion_test.db"
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    repository.initialize_database()
    yield db_path


def test_adaptive_save_and_load_round_trip(isolated_db):
    from app.training.adaptive_engine import AdaptiveEngine
    e1 = AdaptiveEngine()
    e1._now = 1000.0
    e1.record_attempt("S1", correct=True, ev_loss=0.0, tags=("preflop", "BTN"))
    e1.record_attempt("S2", correct=False, ev_loss=0.6)
    e1.record_attempt("S3", correct=False, ev_loss=0.9)

    written = e1.save_to_db()
    assert written == 3

    # Fresh engine — load from DB
    e2 = AdaptiveEngine()
    loaded = e2.load_from_db()
    assert loaded == 3
    assert "S1" in e2.spots
    assert "S2" in e2.spots
    assert "S3" in e2.spots
    # Mistake queue persisted (S3 was recorded last so it should be at the front)
    assert e2.mistake_queue[0] == "S3"
    assert "S2" in e2.mistake_queue


def test_adaptive_state_survives_clear_and_re_save(isolated_db):
    from app.db.repository import clear_adaptive_state
    from app.training.adaptive_engine import AdaptiveEngine
    e1 = AdaptiveEngine()
    e1._now = 1000.0
    e1.record_attempt("X1", correct=True)
    e1.save_to_db()

    clear_adaptive_state()

    e2 = AdaptiveEngine()
    loaded = e2.load_from_db()
    assert loaded == 0
    assert "X1" not in e2.spots


def test_adaptive_tags_round_trip(isolated_db):
    from app.training.adaptive_engine import AdaptiveEngine
    e1 = AdaptiveEngine()
    e1._now = 2000.0
    e1.record_attempt("Y1", correct=True, ev_loss=0.0, tags=("river", "BB", "3BP"))
    e1.save_to_db()

    e2 = AdaptiveEngine()
    e2.load_from_db()
    assert tuple(e2.spots["Y1"].tags) == ("river", "BB", "3BP")


# --- Spot snapshot helpers ---------------------------------------------------

def test_build_spot_snapshot_creates_n_seats():
    from app.ui.components.spot_snapshot import build_spot_snapshot
    spot = {"position": "BTN", "hero_cards": "AsKh", "stack_bb": 100, "pot_bb": 5,
            "board": "", "street": "preflop"}
    for n in (2, 6, 9, 11):
        snap = build_spot_snapshot(spot, num_players=n)
        assert len(snap.players) == n
        assert any(p.is_hero for p in snap.players)


def test_spot_snapshot_hero_position_matched():
    from app.ui.components.spot_snapshot import build_spot_snapshot
    spot = {"position": "CO", "hero_cards": "QdQs", "stack_bb": 100, "pot_bb": 8,
            "board": "", "street": "preflop"}
    snap = build_spot_snapshot(spot, num_players=6)
    hero = next(p for p in snap.players if p.is_hero)
    assert hero.position == "CO"


def test_spot_snapshot_flop_has_three_community_cards():
    from app.ui.components.spot_snapshot import build_spot_snapshot
    spot = {"position": "BTN", "hero_cards": "AsKh", "stack_bb": 100, "pot_bb": 5,
            "board": "Ah7c2d", "street": "flop"}
    snap = build_spot_snapshot(spot, num_players=6)
    assert len(snap.community) == 3
    assert snap.street_name == "Flop"


def test_spot_snapshot_river_has_five_community_cards():
    from app.ui.components.spot_snapshot import build_spot_snapshot
    spot = {"position": "BB", "hero_cards": "9s9c", "stack_bb": 100, "pot_bb": 18,
            "board": "Ah7c2d9s4c", "street": "river"}
    snap = build_spot_snapshot(spot, num_players=6)
    assert len(snap.community) == 5
    assert snap.street_name == "River"


def test_spot_snapshot_btn_is_dealer():
    from app.ui.components.spot_snapshot import build_spot_snapshot
    spot = {"position": "SB", "hero_cards": "QcKc", "stack_bb": 100, "pot_bb": 4,
            "board": "", "street": "preflop"}
    snap = build_spot_snapshot(spot, num_players=6)
    btn_seat = snap.players[snap.dealer_idx]
    assert btn_seat.position == "BTN"
