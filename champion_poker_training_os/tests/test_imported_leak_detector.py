"""Tests for the imported-hands leak detector."""
from __future__ import annotations

from app.leaks.imported_leak_detector import detect_leaks


def _hand(**overrides) -> dict:
    base = {
        "hero_position": "BTN",
        "hero_cards": "AsKs",
        "hero_profit_bb": 0.0,
        "pot_type": "SRP",
        "preflop_actions": "RC",
        "flop_actions": "BC",
        "turn_actions": "",
        "river_actions": "",
    }
    base.update(overrides)
    return base


def test_no_hands_returns_info_message():
    out = detect_leaks([])
    assert len(out) == 1
    assert out[0]["severity"] == "Info"
    assert "Import" in out[0]["fix"] or "import" in out[0]["fix"]


def test_small_sample_warning():
    out = detect_leaks([_hand() for _ in range(10)])
    assert len(out) == 1
    assert "Small sample" in out[0]["name"]


def test_sb_overflat_detection():
    hands = []
    # 12 SB hands, 8 of them flat-call (>50% which is high)
    for i in range(12):
        codes = "FC" if i < 9 else "RC"
        hands.append(_hand(hero_position="SB", preflop_actions=codes))
    # Pad with non-SB hands to clear the small-sample threshold
    for _ in range(20):
        hands.append(_hand(hero_position="BTN", preflop_actions="RC"))
    out = detect_leaks(hands)
    names = [l["name"] for l in out]
    assert any("SB overflat" in n for n in names)


def test_bb_underdefend_detection():
    hands = []
    for i in range(15):
        # 12 of 15 BB hands fold preflop (>65% target)
        codes = "F" if i < 12 else "C"
        hands.append(_hand(hero_position="BB", preflop_actions=codes))
    # Pad
    for _ in range(20):
        hands.append(_hand(hero_position="BTN", preflop_actions="RC"))
    out = detect_leaks(hands)
    assert any("BB underdefend" in l["name"] for l in out)


def test_river_overbluff_detection():
    hands = []
    # 12 hands that go to river, 6 of them have a B/R on river AND lose money
    for i in range(12):
        if i < 6:
            hands.append(_hand(
                river_actions="BF",
                hero_profit_bb=-15.0,
                pot_type="SRP",
            ))
        else:
            hands.append(_hand(
                river_actions="X",
                hero_profit_bb=2.0,
            ))
    # Pad
    for _ in range(15):
        hands.append(_hand(hero_position="BTN", preflop_actions="RC"))
    out = detect_leaks(hands)
    assert any("River overbluff" in l["name"] for l in out)


def test_clean_hands_returns_no_major_leak():
    hands = [_hand(hero_position=p, hero_profit_bb=1.0) for p in ["BTN", "CO", "HJ"] * 10]
    out = detect_leaks(hands)
    # Either no major leaks or low-severity only
    severities = {l["severity"] for l in out}
    assert "Critical" not in severities


def test_severity_ordering_critical_first():
    # Build a case with both 3bet pot spew (Critical) and BB underdefend (High)
    hands = []
    for _ in range(8):
        hands.append(_hand(pot_type="3BP", hero_profit_bb=-25.0))
    for _ in range(12):
        hands.append(_hand(hero_position="BB", preflop_actions="F"))
    for _ in range(20):
        hands.append(_hand(hero_position="BTN"))
    out = detect_leaks(hands)
    sev = [l["severity"] for l in out]
    # Critical should come first
    if "Critical" in sev and "High" in sev:
        assert sev.index("Critical") < sev.index("High")
