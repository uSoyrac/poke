from __future__ import annotations


def test_played_decision_review_returns_verdict() -> None:
    from app.engine.game_loop import PokerGame
    from app.engine.hand_state import ActionType
    from app.training.decision_review import analyze_hero_decision

    game = PokerGame(num_players=6, starting_stack=100.0, hero_seat=0)
    hand = game.start_hand()
    assert game.is_waiting_for_hero

    action_type = hand.get_valid_actions(hand.hero_idx)[0][0]
    review = analyze_hero_decision(hand, action_type, 0.0)

    assert review["hand_id"] == hand.hand_id
    assert review["hero_action"]
    assert review["solver_action"]
    assert review["verdict"] in {"Correct", "Close", "Mistake"}
    assert review["source_confidence"] == "Rule-based heuristic"
    assert review["ev_loss"] >= 0


def test_decision_review_persistence_round_trip(monkeypatch, tmp_path) -> None:
    from app.core import config as cfg
    from app.db import repository

    db_path = tmp_path / "decision_review.db"
    monkeypatch.setattr(cfg, "DB_PATH", db_path)
    monkeypatch.setattr(repository, "DB_PATH", db_path)
    repository.initialize_database()

    review = {
        "hand_id": 77,
        "spot_id": "PLAY-0077-PREFLOP",
        "street": "preflop",
        "position": "BTN",
        "hero_cards": "AsKh",
        "board": "",
        "pot_bb": 2.5,
        "hero_action": "fold",
        "solver_action": "raise",
        "hero_ev": 0.3,
        "best_ev": 1.1,
        "ev_loss": 0.8,
        "solver_frequency": 0.05,
        "best_frequency": 0.62,
        "is_correct": False,
        "verdict": "Mistake",
        "severity": "High",
        "sizing_feedback": "Action class error.",
        "exploit_note": "Steal wider vs overfolders.",
        "drill_target": "Repair drill: Preflop BTN SRP",
        "source_confidence": "Rule-based heuristic",
    }

    row_id = repository.save_decision_review(review)
    assert row_id > 0

    rows = repository.get_decision_reviews(hand_id=77)
    assert len(rows) == 1
    assert rows[0]["is_correct"] is False
    assert rows[0]["ev_loss"] == 0.8

    summary = repository.get_decision_review_summary()
    assert summary["count"] == 1
    assert summary["mistakes"] == 1
    assert summary["ev_loss"] == 0.8
    assert summary["worst"][0]["drill_target"].startswith("Repair drill")

