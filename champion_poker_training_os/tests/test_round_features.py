"""Tests for the four-feature round: drill pack DB, position breakdown, per-seat bots, knowledge nav map."""
from __future__ import annotations

import pytest


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    from app.core import config as cfg
    from app.db import repository
    db_path = tmp_path / "champion_test.db"
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    repository.initialize_database()
    yield db_path


# --- Drill packs DB ---------------------------------------------------------

def test_drill_pack_save_and_list_round_trip(isolated_db):
    from app.db.repository import list_drill_packs, save_drill_pack
    pid = save_drill_pack({
        "name": "BTN steal repair",
        "positions": ["BTN", "SB"],
        "solution": "MTT • ChipEV",
        "starting_spot": "Preflop",
        "preflop_action": "SRP",
    })
    assert pid > 0
    packs = list_drill_packs()
    assert len(packs) == 1
    p = packs[0]
    assert p["name"] == "BTN steal repair"
    assert p["positions"] == ["BTN", "SB"]
    assert p["solution"] == "MTT • ChipEV"


def test_drill_pack_update_keeps_same_id(isolated_db):
    from app.db.repository import list_drill_packs, save_drill_pack
    pid = save_drill_pack({"name": "v1", "positions": ["BTN"]})
    save_drill_pack({"id": pid, "name": "v2", "positions": ["BTN", "CO"]})
    packs = list_drill_packs()
    assert len(packs) == 1
    assert packs[0]["id"] == pid
    assert packs[0]["name"] == "v2"
    assert packs[0]["positions"] == ["BTN", "CO"]


def test_drill_pack_delete(isolated_db):
    from app.db.repository import delete_drill_pack, list_drill_packs, save_drill_pack
    pid = save_drill_pack({"name": "to-delete", "positions": ["UTG"]})
    assert delete_drill_pack(pid) is True
    assert list_drill_packs() == []


def test_drill_pack_delete_missing_id_returns_false(isolated_db):
    from app.db.repository import delete_drill_pack
    assert delete_drill_pack(99999) is False


# --- Reports position breakdown ---------------------------------------------

def test_position_breakdown_aggregates_imported_hands():
    from app.training.position_breakdown import compute_position_breakdown_from_rows
    imported = [
        {"hero_position": "BTN", "hero_profit_bb": 5.0},
        {"hero_position": "BTN", "hero_profit_bb": -2.0},
        {"hero_position": "SB", "hero_profit_bb": -1.0},
        {"hero_position": "BB", "hero_profit_bb": 8.0},
    ]
    out = compute_position_breakdown_from_rows(imported, [])
    by_pos = {row["position"]: row for row in out}
    assert by_pos["BTN"]["count"] == 2
    assert by_pos["BTN"]["win_rate"] == 50.0
    assert by_pos["BTN"]["profit_bb"] == 3.0
    assert by_pos["SB"]["count"] == 1
    assert by_pos["BB"]["win_rate"] == 100.0


def test_position_breakdown_empty_rows():
    from app.training.position_breakdown import compute_position_breakdown_from_rows
    assert compute_position_breakdown_from_rows([], []) == []


def test_position_breakdown_ignores_blank_position():
    from app.training.position_breakdown import compute_position_breakdown_from_rows
    rows = [
        {"hero_position": "?", "hero_profit_bb": 5.0},
        {"hero_position": "", "hero_profit_bb": 3.0},
        {"hero_position": "BTN", "hero_profit_bb": 1.0},
    ]
    out = compute_position_breakdown_from_rows(rows, [])
    assert len(out) == 1
    assert out[0]["position"] == "BTN"


# --- Per-seat bot archetypes ------------------------------------------------

def test_per_seat_bots_assigned_correctly():
    from app.engine.bot_brain import BOT_ARCHETYPES
    from app.engine.game_loop import PokerGame
    archetype_names = list(BOT_ARCHETYPES.keys())
    if len(archetype_names) < 2:
        pytest.skip("Need at least 2 archetypes")
    a, b = archetype_names[0], archetype_names[1]
    g = PokerGame(
        num_players=4, starting_stack=100.0,
        hero_seat=0, bot_archetype=a,
        bot_archetypes={1: b, 2: a},
    )
    assert g.players[0].is_hero
    # Seat 1 should use archetype `b`
    assert g.players[1].name == BOT_ARCHETYPES[b].name
    # Seat 2 should use archetype `a`
    assert g.players[2].name == BOT_ARCHETYPES[a].name
    # Seat 3 unspecified — falls back to default `a`
    assert g.players[3].name == BOT_ARCHETYPES[a].name


def test_per_seat_bots_default_when_missing():
    from app.engine.bot_brain import BOT_ARCHETYPES
    from app.engine.game_loop import PokerGame
    arch = next(iter(BOT_ARCHETYPES.keys()))
    g = PokerGame(num_players=3, starting_stack=100.0, bot_archetype=arch)
    # All bots use the default archetype
    for i in range(3):
        if g.players[i].is_hero:
            continue
        assert g.players[i].name == BOT_ARCHETYPES[arch].name


# --- Knowledge Base concept routing ----------------------------------------

def test_knowledge_application_nav_map_covers_concepts():
    """Every concept's `application` should map to a real nav target."""
    from app.db.seed_data import knowledge_cards
    from app.training.concept_routing import APPLICATION_NAV, route_for
    apps = {c["application"] for c in knowledge_cards()}
    must_map = {"Math Lab", "ICM / PKO Trainer", "Combat Trainer"}
    for needed in must_map:
        if needed in apps:
            assert needed in APPLICATION_NAV
    # route_for() falls back to Spot Trainer for unknown
    target, filters = route_for("__nonexistent__")
    assert target == "Spot Practice Trainer"
    assert filters is None
