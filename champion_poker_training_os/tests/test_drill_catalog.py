"""Drill catalog smoke tests."""
from __future__ import annotations

import pytest

from app.db.drill_catalog import build_full_catalog, catalog_size
from app.db.seed_data import generate_spot_drills


def test_catalog_has_300_plus_drills():
    assert catalog_size() >= 300


def test_every_drill_has_required_fields():
    required = {"id", "name", "category", "format", "format_tag", "table",
                "stack_bb", "position", "street", "pot_type", "hero_cards",
                "pot_bb", "options", "best_action", "base_ev"}
    for d in build_full_catalog():
        missing = required - set(d.keys())
        assert not missing, f"drill {d.get('id')} missing fields: {missing}"


def test_every_drill_has_unique_id():
    ids = [d["id"] for d in build_full_catalog()]
    assert len(ids) == len(set(ids)), "duplicate drill ids detected"


def test_generate_spot_drills_uses_full_catalog():
    drills = generate_spot_drills(50)
    # Even when count=50, we should get the full catalog (300+) because it's all real
    assert len(drills) >= 300


def test_drill_options_are_tuples():
    for d in build_full_catalog()[:50]:
        assert isinstance(d["options"], tuple)
        assert len(d["options"]) >= 2


def test_drill_categories_cover_main_areas():
    cats = {d["category"] for d in build_full_catalog()}
    # Must cover all main training categories
    assert any("Open-Raising" in c for c in cats)
    assert any("BB Defense"   in c for c in cats)
    assert any("3-Bet Defense" in c for c in cats)
    assert any("Strategy"     in c for c in cats)
    assert any("ICM"          in c or "Final Table" in c for c in cats)
    assert any("Cash"         in c for c in cats)


def test_format_tags_match_known_set():
    valid = {"Tournaments 8-Max", "Tournaments ICM", "Tournaments Explo",
             "Cash Games 8-Max", "Cash Games 6-Max", "Cash Games Explo"}
    tags = {d["format_tag"] for d in build_full_catalog()}
    assert tags.issubset(valid), f"Unknown format_tag(s): {tags - valid}"
