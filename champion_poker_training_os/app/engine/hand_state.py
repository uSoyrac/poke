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
    rank: str  # '2'..'A'
    suit: str  # 'c','d','h','s'

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
    """Parse 'Ah', 'Td', '2c' etc."""
    return Card(rank=s[0].upper(), suit=s[1].lower())


def cards_from_str(s: str) -> List[Card]:
    """Parse 'AhKs' or 'Ah Ks' into list of Cards."""
    s = s.replace(" ", "")
    return [card_from_str(s[i:i+2]) for i in range(0, len(s), 2)]


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
        """Remove specific cards (for testing/setup)."""
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
    amount: float = 0.0  # Bet/raise/call amount
    street: Street = Street.PREFLOP

    def __str__(self) -> str:
        if self.action_type in (ActionType.FOLD, ActionType.CHECK):
            return self.action_type.value
        return f"{self.action_type.value} {self.amount:.0f}"


# ─── Player Seat ─────────────────────────────────────────────────────

POSITIONS_6MAX = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
POSITIONS_HU = ["SB", "BB"]
POSITIONS_9MAX = ["SB", "BB", "UTG", "UTG+1", "MP", "MP+1", "HJ", "CO", "BTN"]


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

    def reset_for_hand(self, new_stack: Optional[float] = None) -> None:
        if new_stack is not None:
            self.stack = new_stack
        self.hole_cards = []
        self.is_folded = False
        self.is_all_in = False
        self.current_bet = 0.0
        self.invested_this_hand = 0.0
        self.has_acted = False

    def reset_for_street(self) -> None:
        self.current_bet = 0.0
        self.has_acted = False

    @property
    def is_active(self) -> bool:
        return not self.is_folded and not self.is_all_in

    @property
    def cards_display(self) -> str:
        return " ".join(c.display for c in self.hole_cards) if self.hole_cards else "?? ??"


# ─── Hand State ──────────────────────────────────────────────────────

@dataclass
class HandState:
    """Complete state of a single hand."""
    hand_id: int = 0
    players: List[PlayerSeat] = field(default_factory=list)
    community: List[Card] = field(default_factory=list)
    pot: float = 0.0
    street: Street = Street.PREFLOP
    current_bet: float = 0.0  # Largest bet on current street
    min_raise: float = 0.0
    actions: List[Action] = field(default_factory=list)
    dealer_idx: int = 0  # BTN position
    small_blind: float = 0.5
    big_blind: float = 1.0
    ante: float = 0.0
    is_complete: bool = False
    winners: List[int] = field(default_factory=list)
    winner_hand_name: str = ""

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
        return sum(1 for p in self.players if not p.is_folded)

    @property
    def players_to_act(self) -> int:
        return sum(1 for p in self.players if p.is_active and not p.has_acted)

    @property
    def community_display(self) -> str:
        return " ".join(c.display for c in self.community) if self.community else "—"

    @property
    def board_str(self) -> str:
        return "".join(c.code for c in self.community)

    @property
    def street_name(self) -> str:
        return self.street.name.capitalize()

    def get_valid_actions(self, player_idx: int) -> List[Tuple[ActionType, float, float]]:
        """Return list of (action_type, min_amount, max_amount) for a player."""
        player = self.players[player_idx]
        if player.is_folded or player.is_all_in:
            return []

        valid = []
        to_call = self.current_bet - player.current_bet
        stack = player.stack

        # Always can fold (unless nothing to call)
        if to_call > 0:
            valid.append((ActionType.FOLD, 0, 0))

        # Check if no bet to call
        if to_call <= 0:
            valid.append((ActionType.CHECK, 0, 0))

        # Call
        if to_call > 0:
            call_amount = min(to_call, stack)
            valid.append((ActionType.CALL, call_amount, call_amount))

        # Bet (only if no current bet on this street)
        if self.current_bet == 0 or (self.street == Street.PREFLOP and self.current_bet == self.big_blind and to_call == 0):
            min_bet = self.big_blind
            if stack > min_bet:
                valid.append((ActionType.BET, min_bet, stack))
            elif stack > 0:
                valid.append((ActionType.ALL_IN, stack, stack))

        # Raise (if there's a bet to raise)
        if to_call > 0 and stack > to_call:
            min_raise_to = self.current_bet + max(self.min_raise, self.big_blind)
            raise_amount = min_raise_to - player.current_bet
            if raise_amount < stack:
                valid.append((ActionType.RAISE, raise_amount, stack))
            else:
                valid.append((ActionType.ALL_IN, stack, stack))

        return valid
