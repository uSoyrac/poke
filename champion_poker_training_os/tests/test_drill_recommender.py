"""Drill recommendation engine — regression tests."""
from __future__ import annotations


def _make_mistake(sig_pos, sig_pt, sig_action, ev=2.0, stack=40.0):
    from app.db.mistakes_queue import MistakeEntry
    return MistakeEntry(
        id="m-" + sig_pos + sig_pt + sig_action,
        logged_at="2026-01-01",
        context="spot_trainer",
        spot_id="",
        position=sig_pos,
        stack_bb=stack,
        pot_type=sig_pt,
        hero_action=sig_action,
        gto_action="raise",
        ev_loss=ev,
    )


def test_empty_mistakes_returns_noop_pack():
    from app.training.drill_recommender import pack_from_leaks
    pack = pack_from_leaks([], [])
    assert pack["positions"] == []
    assert "No open mistakes" in pack["notes"]


def test_pack_picks_spots_matching_top_leak_signature():
    from app.db.drill_catalog import build_full_catalog
    from app.training.drill_recommender import pack_from_leaks

    catalog = build_full_catalog()
    # User leaked BTN SRP fold 3 times, lost 2bb each
    mistakes = [
        _make_mistake("BTN", "SRP", "fold", ev=2.0, stack=40),
        _make_mistake("BTN", "SRP", "fold", ev=2.5, stack=40),
        _make_mistake("BTN", "SRP", "fold", ev=1.8, stack=40),
    ]
    # Add one weaker BB leak
    mistakes.append(_make_mistake("BB", "3BP", "call", ev=0.5, stack=40))

    pack = pack_from_leaks(mistakes, catalog, max_size=10)
    assert len(pack["positions"]) > 0
    # The pack's notes should mention the dominant signature
    assert "BTN" in pack["notes"]


def test_already_drilled_mistakes_are_skipped():
    from app.db.drill_catalog import build_full_catalog
    from app.training.drill_recommender import pack_from_leaks
    catalog = build_full_catalog()
    open_m = _make_mistake("BTN", "SRP", "fold")
    drilled_m = _make_mistake("CO", "SRP", "fold")
    drilled_m.drilled = True
    pack = pack_from_leaks([open_m, drilled_m], catalog)
    assert "BTN" in pack["notes"]
    # The drilled-CO leak should NOT be in the notes' "Targeted leaks" list
    assert "CO" not in pack["notes"]


def test_queue_pack_in_state_writes_pending_queue():
    from dataclasses import dataclass
    from app.training.drill_recommender import queue_pack_in_state

    @dataclass
    class _FakeState:
        pending_spot_queue: list = None
        pending_spot_id: str = ""

    s = _FakeState()
    pack = {"positions": ["spot-1", "spot-2", "spot-3"]}
    n = queue_pack_in_state(pack, s)
    assert n == 3
    assert s.pending_spot_queue == ["spot-1", "spot-2", "spot-3"]
    assert s.pending_spot_id == "spot-1"
