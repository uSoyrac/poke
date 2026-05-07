"""Tests for the poker game engine."""
from __future__ import annotations

from app.engine.hand_state import Card, Deck, ActionType, card_from_str
from app.engine.evaluator import evaluate_best_hand, evaluate_5cards, determine_winners
from app.engine.game_loop import PokerGame


def test_deck_has_52_cards() -> None:
    d = Deck()
    assert len(d.cards) == 52
    d.shuffle()
    assert len(d.cards) == 52


def test_deck_deal_removes_cards() -> None:
    d = Deck()
    d.shuffle()
    dealt = d.deal(5)
    assert len(dealt) == 5
    assert len(d.cards) == 47


def test_evaluate_royal_flush() -> None:
    hero = [card_from_str("Ah"), card_from_str("Kh")]
    board = [card_from_str("Qh"), card_from_str("Jh"), card_from_str("Th"),
             card_from_str("2c"), card_from_str("3d")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Royal Flush"


def test_evaluate_full_house() -> None:
    hero = [card_from_str("Ks"), card_from_str("Kd")]
    board = [card_from_str("Kc"), card_from_str("7h"), card_from_str("7d"),
             card_from_str("2c"), card_from_str("3d")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Full House"


def test_evaluate_flush() -> None:
    hero = [card_from_str("Ah"), card_from_str("9h")]
    board = [card_from_str("Kh"), card_from_str("7h"), card_from_str("3h"),
             card_from_str("2c"), card_from_str("Td")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Flush"


def test_evaluate_straight() -> None:
    hero = [card_from_str("9c"), card_from_str("8d")]
    board = [card_from_str("7h"), card_from_str("6s"), card_from_str("5c"),
             card_from_str("2d"), card_from_str("Kh")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Straight"


def test_determine_winners_split_pot() -> None:
    c1 = [card_from_str("Ah"), card_from_str("Kh")]
    c2 = [card_from_str("As"), card_from_str("Ks")]
    board = [card_from_str("2c"), card_from_str("3d"), card_from_str("7h"),
             card_from_str("Td"), card_from_str("Jc")]
    winners, _ = determine_winners([(0, c1), (1, c2)], board)
    assert len(winners) == 2  # Split pot


def test_game_loop_completes_hand() -> None:
    game = PokerGame(num_players=2, starting_stack=100.0)
    hand = game.start_hand()
    while game.is_waiting_for_hero:
        valid = hand.get_valid_actions(hand.hero_idx)
        if valid:
            game.hero_act(valid[0][0], valid[0][1])
    assert hand.is_complete


def test_game_loop_session_stats() -> None:
    game = PokerGame(num_players=6, starting_stack=100.0)
    for _ in range(5):
        hand = game.start_hand()
        while game.is_waiting_for_hero:
            valid = hand.get_valid_actions(hand.hero_idx)
            if valid:
                game.hero_act(valid[0][0], valid[0][1])
    stats = game.get_session_stats()
    assert stats["hands"] == 5
    assert "vpip" in stats
    assert "win_rate" in stats


def test_ai_coach_hand_review() -> None:
    from app.ai.coach_engine import analyze_played_hand
    review = analyze_played_hand({
        "hero_cards": "A♥ K♠",
        "community": "Q♦ J♣ T♠ 2♥ 5♣",
        "hero_profit": 25.0,
        "hero_won": True,
        "hero_invested": 15.0,
        "pot": 40.0,
        "winner_hand_name": "Straight",
    })
    assert "El Analizi" in review
    assert "Kazandın" in review


def test_ai_coach_session_summary() -> None:
    from app.ai.coach_engine import session_summary
    s = session_summary({"hands": 10, "profit_bb": 12.5, "vpip": 24, "win_rate": 40}, [])
    assert "Session Özeti" in s
    assert "10" in s


def test_ai_coach_pattern_detection() -> None:
    from app.ai.coach_engine import identify_patterns
    hands = [{"hero_won": False, "streets_seen": 1}] * 5
    result = identify_patterns(hands)
    assert "Pattern" in result or "fold" in result.lower()


def test_player_profile_strength_weakness() -> None:
    from app.core.player_profile import PlayerProfile
    p = PlayerProfile()
    p.update_from_stats({
        "total_hands": 100, "vpip": 45.0, "pfr": 10.0,
        "wtsd": 40.0, "wsd": 35.0, "af": 0.8,
        "profit_bb": -50.0, "bb_per_100": -50.0,
    })
    assert len(p.weaknesses) > 0
    assert any("loose" in w.lower() or "vpip" in w.lower() for w in p.weaknesses)


def test_bot_archetypes_coverage() -> None:
    from app.engine.bot_brain import BOT_ARCHETYPES
    assert len(BOT_ARCHETYPES) >= 10
    for name, profile in BOT_ARCHETYPES.items():
        assert 0 < profile.vpip < 60
        assert profile.aggression >= 0


def test_evaluate_four_of_a_kind() -> None:
    hero = [card_from_str("As"), card_from_str("Ah")]
    board = [card_from_str("Ac"), card_from_str("Ad"), card_from_str("5h"),
             card_from_str("7c"), card_from_str("9d")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Four of a Kind"


def test_evaluate_two_pair() -> None:
    hero = [card_from_str("Kh"), card_from_str("Qd")]
    board = [card_from_str("Ks"), card_from_str("Qc"), card_from_str("2h"),
             card_from_str("7d"), card_from_str("5s")]
    _, _, name = evaluate_best_hand(hero, board)
    assert name == "Two Pair"
