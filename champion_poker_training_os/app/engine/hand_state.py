from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple


# ─── Card Representation ────────────────────────────────────────────

RANKS = "23456789TJQKA"
SUITS = "cdhs"
SUIT_SYMBOLS = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def value(self) -> int:
        return RANK_VALUES.get(self.rank, 0)

    @property
    def display(self) -> str:
        return f"{self.rank}{SUIT_SYMBOLS.get(self.suit, self.suit)}"

    @property
    def code(self) -> str:
        return f"{self.rank}{self.suit}"

    def __str__(self) -> str:
        return self.display

    def __repr__(self) -> str:
        return self.display


def card_from_str(s: str) -> Card:
    return Card(rank=s[0].upper(), suit=s[1].lower())


def cards_from_str(s: str) -> List[Card]:
    s = s.replace(" ", "")
    return [card_from_str(s[i:i + 2]) for i in range(0, len(s), 2)]


# ─── Deck ────────────────────────────────────────────────────────────

class Deck:
    def __init__(self):
        self.cards: List[Card] = [Card(r, s) for r in RANKS for s in SUITS]
        self.dealt: List[Card] = []

    def shuffle(self) -> None:
        self.cards = [Card(r, s) for r in RANKS for s in SUITS]
        self.dealt = []
        random.shuffle(self.cards)

    def deal(self, n: int = 1) -> List[Card]:
        result = self.cards[:n]
        self.cards = self.cards[n:]
        self.dealt.extend(result)
        return result

    def deal_one(self) -> Card:
        return self.deal(1)[0]

    def remove(self, cards: List[Card]) -> None:
        for c in cards:
            self.cards = [x for x in self.cards if not (x.rank == c.rank and x.suit == c.suit)]


# ─── Street Enum ─────────────────────────────────────────────────────

class Street(Enum):
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()

    @property
    def next_street(self) -> Optional["Street"]:
        order = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER, Street.SHOWDOWN]
        idx = order.index(self)
        return order[idx + 1] if idx < len(order) - 1 else None


# ─── Action ──────────────────────────────────────────────────────────

class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all-in"


@dataclass
class Action:
    player_idx: int
    action_type: ActionType
    amount: float = 0.0
    street: Street = Street.PREFLOP
    total_bet: float = 0.0  # Total commitment after this action on this street
    pot_after: float = 0.0

    def __str__(self) -> str:
        if self.action_type in (ActionType.FOLD, ActionType.CHECK):
            return self.action_type.value
        return f"{self.action_type.value} {self.amount:.1f}"


# ─── Player Seat ─────────────────────────────────────────────────────

POSITIONS_HU = ["SB/BTN", "BB"]
POSITIONS_3MAX = ["SB", "BB", "BTN"]
POSITIONS_4MAX = ["SB", "BB", "CO", "BTN"]
POSITIONS_5MAX = ["SB", "BB", "UTG", "CO", "BTN"]
POSITIONS_6MAX = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
POSITIONS_7MAX = ["SB", "BB", "UTG", "LJ", "HJ", "CO", "BTN"]
POSITIONS_8MAX = ["SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO", "BTN"]
POSITIONS_9MAX = ["SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN"]

POSITIONS_BY_SIZE = {
    2: POSITIONS_HU,
    3: POSITIONS_3MAX,
    4: POSITIONS_4MAX,
    5: POSITIONS_5MAX,
    6: POSITIONS_6MAX,
    7: POSITIONS_7MAX,
    8: POSITIONS_8MAX,
    9: POSITIONS_9MAX,
}


@dataclass
class PlayerSeat:
    name: str
    stack: float
    position: str = ""
    is_hero: bool = False
    hole_cards: List[Card] = field(default_factory=list)
    is_folded: bool = False
    is_all_in: bool = False
    current_bet: float = 0.0
    invested_this_hand: float = 0.0
    has_acted: bool = False
    is_eliminated: bool = False  # Out of tournament

    def reset_for_hand(self, new_stack: Optional[float] = None) -> None:
        if new_stack is not None:
            self.stack = new_stack
        self.hole_cards = []
        self.is_folded = False
        self.is_all_in = self.stack <= 0
        self.current_bet = 0.0
        self.invested_this_hand = 0.0
        self.has_acted = False

    def reset_for_street(self) -> None:
        self.current_bet = 0.0
        self.has_acted = False

    @property
    def is_active(self) -> bool:
        return not self.is_folded and not self.is_all_in and not self.is_eliminated

    @property
    def is_in_hand(self) -> bool:
        return not self.is_folded and not self.is_eliminated

    @property
    def cards_display(self) -> str:
        return " ".join(c.display for c in self.hole_cards) if self.hole_cards else "?? ??"


# ─── Hand State ──────────────────────────────────────────────────────

@dataclass
class HandState:
    hand_id: int = 0
    players: List[PlayerSeat] = field(default_factory=list)
    community: List[Card] = field(default_factory=list)
    pot: float = 0.0
    street: Street = Street.PREFLOP
    current_bet: float = 0.0
    min_raise: float = 0.0  # Size of last legal raise (added on top of previous bet)
    last_full_raise_size: float = 0.0
    actions: List[Action] = field(default_factory=list)
    dealer_idx: int = 0
    small_blind: float = 0.5
    big_blind: float = 1.0
    ante: float = 0.0
    is_complete: bool = False
    winners: List[int] = field(default_factory=list)
    winner_hand_name: str = ""
    pots: List[dict] = field(default_factory=list)  # Side pots after resolution

    @property
    def hero(self) -> Optional[PlayerSeat]:
        for p in self.players:
            if p.is_hero:
                return p
        return None

    @property
    def hero_idx(self) -> int:
        for i, p in enumerate(self.players):
            if p.is_hero:
                return i
        return 0

    @property
    def active_count(self) -> int:
        """Count of players still in the hand (not folded)."""
        return sum(1 for p in self.players if p.is_in_hand)

    @property
    def can_act_count(self) -> int:
        """Count of players who can still act (in hand AND not all-in)."""
        return sum(1 for p in self.players if p.is_active)

    @property
    def community_display(self) -> str:
        return " ".join(c.display for c in self.community) if self.community else "—"

    @property
    def board_str(self) -> str:
        return "".join(c.code for c in self.community)

    @property
    def street_name(self) -> str:
        return self.street.name.capitalize()

    def to_call(self, player_idx: int) -> float:
        return max(0.0, self.current_bet - self.players[player_idx].current_bet)

    def get_valid_actions(self, player_idx: int) -> List[Tuple[ActionType, float, float]]:
        player = self.players[player_idx]
        if player.is_folded or player.is_all_in or player.is_eliminated:
            return []

        valid: List[Tuple[ActionType, float, float]] = []
        to_call = self.to_call(player_idx)
        stack = player.stack

        if to_call > 0:
            valid.append((ActionType.FOLD, 0.0, 0.0))
            if to_call >= stack:
                valid.append((ActionType.ALL_IN, stack, stack))
            else:
                valid.append((ActionType.CALL, to_call, to_call))
                # Raise: must raise by at least last_full_raise_size on top of current bet
                min_raise_to = self.current_bet + max(self.last_full_raise_size, self.big_blind)
                raise_amount = min_raise_to - player.current_bet
                if raise_amount < stack:
                    valid.append((ActionType.RAISE, raise_amount, stack))
                else:
                    valid.append((ActionType.ALL_IN, stack, stack))
        else:
            valid.append((ActionType.CHECK, 0.0, 0.0))
            min_bet = self.big_blind
            if stack > min_bet:
                valid.append((ActionType.BET, min_bet, stack))
            elif stack > 0:
                valid.append((ActionType.ALL_IN, stack, stack))

        return valid
