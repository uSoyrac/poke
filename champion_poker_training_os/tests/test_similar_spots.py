"""Tests for similar-spot finder (replay → drill set)."""
from __future__ import annotations

from app.training.similar_spots import (
    POT_TYPE_MAP,
    _score_match,
    _street_from_actions,
    find_similar_spots,
)


def _drill(id_: str, **kwargs) -> dict:
    base = {
        "id": id_,
        "position": "BTN",
        "street": "flop",
        "pot_type": "single raised pot",
        "stack_bb": 100,
        "format": "MTT",
        "base_ev": 1.0,
    }
    base.update(kwargs)
    return base


# --- street inference -------------------------------------------------------

def test_street_from_actions_returns_river_when_river_actions():
    assert _street_from_actions({"river_actions": "BC"}) == "river"


def test_street_from_actions_returns_turn_when_only_turn_actions():
    assert _street_from_actions({
        "turn_actions": "BC", "river_actions": "",
    }) == "turn"


def test_street_from_actions_returns_flop_when_only_flop_actions():
    assert _street_from_actions({
        "flop_actions": "BC", "turn_actions": "", "river_actions": "",
    }) == "flop"


def test_street_from_actions_defaults_to_preflop():
    assert _street_from_actions({}) == "preflop"


# --- pot type map -----------------------------------------------------------

def test_pot_type_map_covers_common_codes():
    for code in ("Limp", "SRP", "3BP", "4BP", "Squeeze"):
        assert code in POT_TYPE_MAP


# --- _score_match -----------------------------------------------------------

def test_score_match_full_house_of_matches():
    spot = _drill("S1")
    score = _score_match(spot, {
        "position": "BTN", "street": "flop",
        "pot_type": "single raised pot", "stack_bb": 100, "format": "MTT",
    })
    assert score >= 4 + 3 + 3 + 2 + 1  # all weights summed


def test_score_match_partial():
    spot = _drill("S1", position="CO", pot_type="3bet pot")
    # Only street and stack match
    score = _score_match(spot, {
        "position": "BTN", "street": "flop",
        "pot_type": "single raised pot", "stack_bb": 102,
    })
    assert score == 3 + 2  # street + close stack


def test_score_match_zero_when_nothing_matches():
    spot = _drill("S1", position="UTG", street="river", pot_type="3bet pot",
                   stack_bb=20, format="Cash")
    assert _score_match(spot, {
        "position": "BTN", "street": "preflop",
        "pot_type": "single raised pot", "stack_bb": 100, "format": "MTT",
    }) == 0


# --- find_similar_spots end-to-end ------------------------------------------

def test_find_similar_returns_top_n():
    hand = {
        "hero_position": "BTN", "pot_type": "SRP",
        "river_actions": "BC", "turn_actions": "BC", "flop_actions": "BC",
        "stack_bb": 100, "format": "MTT",
    }
    drills = [
        _drill("PERFECT", position="BTN", street="river",
               pot_type="single raised pot", stack_bb=100, format="MTT"),
        _drill("CLOSE-1", position="BTN", street="flop",
               pot_type="single raised pot", stack_bb=100, format="MTT"),
        _drill("CLOSE-2", position="CO", street="river",
               pot_type="single raised pot", stack_bb=100),
        _drill("OFF-TOPIC", position="UTG", street="preflop",
               pot_type="3bet pot", stack_bb=20),
    ]
    out = find_similar_spots(hand, drills, n=3)
    assert len(out) == 3
    assert out[0]["id"] == "PERFECT"
    # OFF-TOPIC scored 0, must not appear
    assert all(s["id"] != "OFF-TOPIC" for s in out)


def test_find_similar_respects_n():
    hand = {"hero_position": "BTN", "pot_type": "SRP", "stack_bb": 100}
    drills = [_drill(f"S{i}", position="BTN") for i in range(20)]
    out = find_similar_spots(hand, drills, n=5)
    assert len(out) == 5


def test_find_similar_with_zero_matches_returns_empty():
    hand = {"hero_position": "BTN", "pot_type": "SRP"}
    drills = [_drill("X", position="UTG", street="river", pot_type="3bet pot",
                      stack_bb=20, format="Cash")]
    # No criteria match → score 0 → excluded
    out = find_similar_spots(hand, drills, n=5)
    assert out == []


def test_find_similar_handles_imported_hand_shape():
    """The function should work on imported_hands rows with hero_position +
    *_actions fields without explicit street."""
    hand = {
        "hero_position": "SB",
        "pot_type": "3BP",
        "preflop_actions": "RC",
        "flop_actions": "BC",
        "turn_actions": "",
        "river_actions": "",
        "format": "Cash",
    }
    drills = [
        _drill("MATCH", position="SB", street="flop", pot_type="3bet pot"),
        _drill("OTHER", position="BTN", street="preflop", pot_type="single raised pot"),
    ]
    out = find_similar_spots(hand, drills, n=2)
    assert out and out[0]["id"] == "MATCH"
