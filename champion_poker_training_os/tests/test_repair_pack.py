"""Hatalardan otomatik drill — ağırlıklı tamir paketi (Phase D4)."""
from __future__ import annotations

import pytest


@pytest.fixture()
def lib():
    from app.training.drill_library import DrillLibrary
    return DrillLibrary()        # izole örnek (singleton değil); QApplication yok


def test_generate_from_leak_count(lib):
    leak = {"name": "Over-folding (vs 3-bet)", "category": "Preflop",
            "severity": "High", "fix": "Defend wider"}
    drills = lib.generate_from_leak(leak, count=3)
    assert len(drills) == 3
    assert all(d["leak_name"] == leak["name"] for d in drills)


def test_repair_pack_weights_by_severity(lib):
    leaks = [
        {"name": "A", "category": "Preflop", "severity": "Critical", "ev_lost": 20, "fix": "x"},
        {"name": "B", "category": "Flop", "severity": "Medium", "ev_lost": 3, "fix": "y"},
    ]
    pack = lib.generate_repair_pack(leaks, max_total=50)
    by = {}
    for d in pack:
        by[d["leak_name"]] = by.get(d["leak_name"], 0) + 1
    # Critical 6 vs Medium 2 → daha ağıra daha çok tekrar
    assert by["A"] == 6 and by["B"] == 2
    assert by["A"] > by["B"]


def test_repair_pack_skips_info_and_low(lib):
    leaks = [
        {"name": "Info one", "severity": "Info", "fix": ""},
        {"name": "Real", "category": "Preflop", "severity": "High", "ev_lost": 5, "fix": "z"},
    ]
    pack = lib.generate_repair_pack(leaks)
    assert all(d["leak_name"] == "Real" for d in pack)
    assert len(pack) == 4   # High → 4


def test_repair_pack_respects_max_total(lib):
    leaks = [
        {"name": f"L{i}", "category": "Preflop", "severity": "Critical",
         "ev_lost": 10, "fix": "f"} for i in range(10)
    ]
    pack = lib.generate_repair_pack(leaks, max_total=10)
    assert len(pack) == 10


def test_repair_pack_unique_ids(lib):
    leaks = [
        {"name": "A", "category": "Preflop", "severity": "High", "ev_lost": 5, "fix": "x"},
        {"name": "B", "category": "Flop", "severity": "High", "ev_lost": 5, "fix": "y"},
    ]
    pack = lib.generate_repair_pack(leaks)
    ids = [d["id"] for d in pack]
    assert len(ids) == len(set(ids))    # çakışma yok


def test_repair_pack_empty(lib):
    assert lib.generate_repair_pack([]) == []
