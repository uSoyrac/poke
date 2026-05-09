from __future__ import annotations

from app.engine.hand_state import ActionType, HandState, Street
from app.poker.cards import normalize_hand
from app.solver.mock_solver import compare_action


ACTION_ORDER = ("fold", "check", "call", "bet small", "bet medium", "bet large", "raise", "jam")


def analyze_hero_decision(hand: HandState, hero_action: ActionType, amount: float = 0.0) -> dict:
    """Score one offline hero decision against a transparent training baseline.

    This is deliberately not real-time solver advice. It evaluates decisions
    only inside Champion OS simulations/training hands and labels the source as
    rule-based/mock unless imported solver data is later attached.
    """
    spot = build_decision_spot(hand, hero_action, amount)
    hero_action_name = normalize_action(hero_action, amount, max(hand.pot, 1.0))
    comparison = compare_action(spot, hero_action_name)
    ev_loss = float(comparison["ev_loss"])
    severity = severity_from_ev_loss(ev_loss)
    verdict = "Correct" if comparison["is_correct"] else ("Close" if ev_loss <= 0.18 else "Mistake")
    return {
        "hand_id": hand.hand_id,
        "spot_id": spot["id"],
        "street": spot["street"],
        "position": spot["position"],
        "hero_cards": spot["hero_cards"],
        "board": spot["board"],
        "pot_bb": spot["pot_bb"],
        "hero_action": hero_action_name,
        "solver_action": comparison["best_action"],
        "hero_ev": comparison["hero_ev"],
        "best_ev": comparison["best_ev"],
        "ev_loss": ev_loss,
        "solver_frequency": comparison["solver_frequency"],
        "best_frequency": comparison["best_frequency"],
        "is_correct": comparison["is_correct"],
        "verdict": verdict,
        "severity": severity,
        "sizing_feedback": comparison["sizing_feedback"],
        "exploit_note": exploit_note_for_spot(spot, hero_action_name),
        "drill_target": drill_target_for_spot(spot, severity),
        "source_confidence": spot["source_confidence"],
    }


def build_decision_spot(hand: HandState, hero_action: ActionType, amount: float = 0.0) -> dict:
    hero = hand.hero
    hero_cards = "".join(card.code for card in (hero.hole_cards if hero else []))
    options = tuple(_legal_action_names(hand))
    best_action = _baseline_action(hand, options)
    return {
        "id": f"PLAY-{hand.hand_id:04d}-{hand.street.name}",
        "title": f"Played hand {hand.hand_id} {hand.street.name.title()} decision",
        "format": "simulation",
        "table": f"{len(hand.players)}-max",
        "street": hand.street.name.lower(),
        "position": hero.position if hero else "Hero",
        "stack_bb": int(round(hero.stack if hero else 0)),
        "pot_bb": round(hand.pot, 2),
        "hero_cards": hero_cards,
        "board": hand.board_str,
        "board_texture": _board_texture(hand.board_str),
        "pot_type": _pot_type(hand),
        "action_history": _action_history(hand),
        "options": options,
        "best_action": best_action,
        "base_ev": _base_ev_for_hand(hero_cards, hand.street),
        "range_advantage": _range_advantage(hand),
        "nut_advantage": _nut_advantage(hand),
        "icm": "off",
        "source_confidence": "Rule-based heuristic",
    }


def normalize_action(action_type: ActionType, amount: float = 0.0, pot: float = 1.0) -> str:
    if action_type == ActionType.FOLD:
        return "fold"
    if action_type == ActionType.CHECK:
        return "check"
    if action_type == ActionType.CALL:
        return "call"
    if action_type == ActionType.RAISE:
        return "raise"
    if action_type == ActionType.ALL_IN:
        return "jam"
    if action_type == ActionType.BET:
        ratio = amount / max(pot, 1.0)
        if ratio <= 0.45:
            return "bet small"
        if ratio <= 0.85:
            return "bet medium"
        return "bet large"
    return action_type.value


def summarize_decision_reviews(reviews: list[dict]) -> dict:
    if not reviews:
        return {
            "count": 0,
            "mistakes": 0,
            "ev_loss": 0.0,
            "accuracy": 0.0,
            "worst": None,
        }
    mistakes = sum(1 for review in reviews if not review.get("is_correct"))
    ev_loss = round(sum(float(review.get("ev_loss", 0.0)) for review in reviews), 2)
    accuracy = round(100 * (len(reviews) - mistakes) / len(reviews), 1)
    worst = max(reviews, key=lambda review: float(review.get("ev_loss", 0.0)))
    return {
        "count": len(reviews),
        "mistakes": mistakes,
        "ev_loss": ev_loss,
        "accuracy": accuracy,
        "worst": worst,
    }


def format_decision_review(review: dict) -> str:
    icon = "✓" if review.get("is_correct") else "!"
    return (
        f"{icon} {review['street'].title()} {review['position']} | "
        f"Hero {review['hero_action']} vs baseline {review['solver_action']} | "
        f"EV loss {review['ev_loss']:.2f}bb | {review['verdict']} | "
        f"{review['exploit_note']}"
    )


def _legal_action_names(hand: HandState) -> list[str]:
    names: list[str] = []
    for action_type, min_amount, _max_amount in hand.get_valid_actions(hand.hero_idx):
        if action_type == ActionType.BET:
            names.extend(["bet small", "bet medium", "bet large"])
        else:
            names.append(normalize_action(action_type, min_amount, max(hand.pot, 1.0)))
    if ActionType.ALL_IN in {item[0] for item in hand.get_valid_actions(hand.hero_idx)} and "jam" not in names:
        names.append("jam")
    return [name for name in ACTION_ORDER if name in set(names)] or ["check", "bet medium"]


def _baseline_action(hand: HandState, options: tuple[str, ...]) -> str:
    hero = hand.hero
    hand_class = _hand_class(hero)
    strength = _preflop_strength(hand_class)
    to_call = hand.current_bet - (hero.current_bet if hero else 0)
    has_pair_or_better = _hero_connects_board(hand)

    if hand.street == Street.PREFLOP:
        if to_call > 0:
            if strength >= 82 and "raise" in options:
                return "raise"
            if strength >= 82 and "jam" in options and (hero.stack if hero else 99) <= 20:
                return "jam"
            if strength >= 48 and "call" in options:
                return "call"
            return _first_available(options, ("fold", "call", "jam"))
        if strength >= 52:
            return _first_available(options, ("raise", "bet medium", "jam", "call"))
        return _first_available(options, ("fold", "check", "call"))

    if to_call > 0:
        if has_pair_or_better and "call" in options:
            return "call"
        if _has_nut_blocker(hero) and "raise" in options and hand.street in {Street.TURN, Street.RIVER}:
            return "raise"
        return _first_available(options, ("fold", "call", "jam"))

    if has_pair_or_better:
        return _first_available(options, ("bet medium", "bet small", "check"))
    if _has_nut_blocker(hero) and hand.street in {Street.TURN, Street.RIVER}:
        return _first_available(options, ("bet large", "bet medium", "check"))
    return _first_available(options, ("check", "bet small"))


def _first_available(options: tuple[str, ...], preferred: tuple[str, ...]) -> str:
    for action in preferred:
        if action in options:
            return action
    return options[0]


def _hand_class(hero) -> str:
    if not hero or len(hero.hole_cards) < 2:
        return "72o"
    return normalize_hand(hero.hole_cards[0].code, hero.hole_cards[1].code)


def _preflop_strength(hand_class: str) -> int:
    premiums = {"AA": 100, "KK": 96, "QQ": 92, "JJ": 86, "TT": 80, "AKs": 84, "AKo": 78, "AQs": 76}
    if hand_class in premiums:
        return premiums[hand_class]
    if hand_class.endswith("s") and hand_class[0] in "AKQJT":
        return 64
    if hand_class.endswith("o") and hand_class[0] in "AKQ":
        return 55
    if len(hand_class) >= 2 and hand_class[0] == hand_class[1]:
        return 58 if hand_class[0] in "998877" else 42
    if hand_class.endswith("s"):
        return 44
    return 32


def _hero_connects_board(hand: HandState) -> bool:
    hero = hand.hero
    if not hero or not hand.community:
        return False
    hero_ranks = {card.rank for card in hero.hole_cards}
    board_ranks = {card.rank for card in hand.community}
    return bool(hero_ranks & board_ranks)


def _has_nut_blocker(hero) -> bool:
    return bool(hero and any(card.rank == "A" for card in hero.hole_cards))


def _base_ev_for_hand(hero_cards: str, street: Street) -> float:
    street_bonus = {Street.PREFLOP: 0.85, Street.FLOP: 1.0, Street.TURN: 1.1, Street.RIVER: 1.2}.get(street, 0.9)
    if "A" in hero_cards:
        return street_bonus + 0.25
    return street_bonus


def _action_history(hand: HandState) -> str:
    if not hand.actions:
        return "No prior action"
    labels = []
    for action in hand.actions[-8:]:
        player = hand.players[action.player_idx]
        labels.append(f"{action.street.name.title()} {player.position} {action.action_type.value} {action.amount:.1f}".strip())
    return " / ".join(labels)


def _pot_type(hand: HandState) -> str:
    preflop_raises = sum(1 for action in hand.actions if action.street == Street.PREFLOP and action.action_type in {ActionType.BET, ActionType.RAISE, ActionType.ALL_IN})
    if preflop_raises >= 3:
        return "4BP"
    if preflop_raises == 2:
        return "3BP"
    return "SRP"


def _board_texture(board: str) -> str:
    if not board:
        return "preflop"
    ranks = board[::2]
    suits = board[1::2]
    if len(suits) >= 3 and len(set(suits[:3])) == 1:
        return "monotone"
    if len(set(ranks)) < len(ranks):
        return "paired"
    if any(rank in ranks for rank in "AK"):
        return "high-card"
    return "dynamic"


def _range_advantage(hand: HandState) -> str:
    hero = hand.hero
    if not hero:
        return "Unknown range advantage"
    if hero.position in {"BTN", "CO"} and hand.street == Street.PREFLOP:
        return "Hero has opener/position range advantage"
    if _hero_connects_board(hand):
        return "Hero has made-hand equity share"
    return "Neutral or villain-favored range interaction"


def _nut_advantage(hand: HandState) -> str:
    if _has_nut_blocker(hand.hero):
        return "Hero blocks top-of-range Ax/nut hands"
    if hand.board_str and _board_texture(hand.board_str) in {"paired", "monotone"}:
        return "Nut advantage is texture-sensitive"
    return "No clear nut advantage"


def exploit_note_for_spot(spot: dict, hero_action: str) -> str:
    texture = spot.get("board_texture", "")
    if spot.get("street") == "preflop":
        if hero_action == "fold":
            return "Exploit check: if pool overfolds blinds, steal/open ranges can widen."
        return "Exploit check: punish tight players, avoid loose calls vs aggressive 3-bettors."
    if texture in {"monotone", "paired"}:
        return "Exploit check: population under-bluffs scary textures; reduce thin bluff-catches."
    if hero_action.startswith("bet"):
        return "Exploit check: vs overfolders this pressure is valuable; vs stations shift value-heavy."
    return "Exploit check: compare villain archetype before deviating from baseline."


def drill_target_for_spot(spot: dict, severity: str) -> str:
    prefix = "Repair drill" if severity in {"High", "Critical"} else "Maintenance drill"
    return f"{prefix}: {spot.get('street', 'spot').title()} {spot.get('position', 'Hero')} {spot.get('pot_type', 'SRP')}"


def severity_from_ev_loss(ev_loss: float) -> str:
    if ev_loss >= 1.0:
        return "Critical"
    if ev_loss >= 0.45:
        return "High"
    if ev_loss >= 0.15:
        return "Medium"
    return "Low"

