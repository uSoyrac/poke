"""Build a renderable HandState-like snapshot from a spot dict.

Used by tournament_simulator and combat_trainer to feed LivePokerTable when no
real PokerGame is running — we fake a HandState from the spot metadata.
"""
from __future__ import annotations

from app.engine.hand_state import positions_for


class SpotCard:
    """Lightweight stand-in for engine.Card — only needs .display."""
    __slots__ = ("display",)
    def __init__(self, display: str):
        self.display = display


class SpotSeat:
    """Lightweight stand-in for engine.PlayerSeat for LivePokerTable rendering."""
    def __init__(self, name: str, position: str, stack: float, current_bet: float = 0,
                 is_hero: bool = False, is_folded: bool = False, is_all_in: bool = False,
                 hole_cards: list | None = None):
        self.name = name
        self.position = position
        self.stack = stack
        self.current_bet = current_bet
        self.is_hero = is_hero
        self.is_folded = is_folded
        self.is_all_in = is_all_in
        self.hole_cards = hole_cards or []


class SpotSnapshot:
    """Lightweight HandState replacement for static-spot rendering."""
    def __init__(self, players: list, dealer_idx: int, hero_idx: int,
                 community: list, pot: float, big_blind: float, street_name: str,
                 active_player_idx: int | None = None):
        self.players = players
        self.dealer_idx = dealer_idx
        self.hero_idx = hero_idx
        self.active_player_idx = active_player_idx
        self.community = community
        self.pot = pot
        self.big_blind = big_blind
        self.street_name = street_name
        self.actions: list = []


def board_to_cards(board: str) -> list[SpotCard]:
    if not board:
        return []
    chunks = [board[i:i + 2] for i in range(0, len(board) - len(board) % 2, 2)]
    return [SpotCard(c) for c in chunks]


def hero_cards(hero: str) -> list[SpotCard]:
    if not hero:
        return []
    if len(hero) >= 4:
        return [SpotCard(hero[:2]), SpotCard(hero[2:4])]
    if len(hero) == 3:
        suited = hero.endswith("s")
        return [SpotCard(hero[0] + "h"), SpotCard(hero[1] + ("h" if suited else "d"))]
    if len(hero) == 2:
        return [SpotCard(hero[0] + "h"), SpotCard(hero[1] + "d")]
    return []


def build_spot_snapshot(spot: dict, num_players: int = 6, hero_chip_stack: int = 100,
                        avg_stack: int = 100, blind_size_chips: int = 1) -> SpotSnapshot:
    """Synthesise a renderable HandState from a spot dict (for static spots without a live game)."""
    n = max(2, min(num_players, 11))
    positions = positions_for(n)
    hero_pos = (spot.get("position") or "BTN").upper()
    hero_seat_idx = positions.index(hero_pos) if hero_pos in positions else 0

    bb = max(1, blind_size_chips)
    seats: list[SpotSeat] = []
    for i, pos in enumerate(positions):
        is_hero = (i == hero_seat_idx)
        # Mark roughly half the table as folded preflop for visual realism
        is_folded = (not is_hero) and (i not in {(hero_seat_idx + 1) % n, (hero_seat_idx - 1) % n})
        stack = hero_chip_stack if is_hero else max(1, int(avg_stack * (0.7 + 0.06 * i)))
        current_bet = bb if pos == "SB" else (bb * 2 if pos == "BB" else 0)
        hole = hero_cards(spot.get("hero_cards", "")) if is_hero else []
        seats.append(SpotSeat(
            name="Hero" if is_hero else f"Bot{i}",
            position=pos,
            stack=stack,
            current_bet=current_bet,
            is_hero=is_hero,
            is_folded=is_folded,
            hole_cards=hole,
        ))

    board = spot.get("board") or ""
    street = (spot.get("street") or "preflop").lower()
    street_name = {"preflop": "Preflop", "flop": "Flop", "turn": "Turn", "river": "River"}.get(street, "Preflop")

    if street in ("flop", "turn", "river"):
        community = board_to_cards(board)
        if street == "flop":
            community = community[:3] or [SpotCard("?h"), SpotCard("?d"), SpotCard("?s")]
        elif street == "turn":
            community = community[:4]
        elif street == "river":
            community = community[:5]
    else:
        community = []

    btn_idx = positions.index("BTN") if "BTN" in positions else (n - 1)
    pot_chips = float(spot.get("pot_bb", 0)) * bb

    return SpotSnapshot(
        players=seats,
        dealer_idx=btn_idx,
        hero_idx=hero_seat_idx,
        active_player_idx=hero_seat_idx,
        community=community,
        pot=pot_chips,
        big_blind=float(bb),
        street_name=street_name,
    )
