from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from app.engine.bot_brain import BotBrain, BotProfile, BOT_ARCHETYPES
from app.engine.evaluator import determine_winners
from app.engine.hand_state import (
    Action, ActionType, Card, Deck, HandState, PlayerSeat,
    Street, POSITIONS_6MAX, POSITIONS_HU, positions_for,
)


@dataclass
class HandResult:
    """Summary of a completed hand."""
    hand_id: int
    hero_cards: str
    community: str
    pot: float
    winners: List[int]
    winner_hand_name: str
    hero_won: bool
    hero_profit: float
    actions: List[Action] = field(default_factory=list)
    hero_invested: float = 0.0
    streets_seen: int = 0


class PokerGame:
    """Manages a full poker game session with multiple hands."""

    def __init__(
        self,
        num_players: int = 6,
        starting_stack: float = 100.0,
        small_blind: float = 0.5,
        big_blind: float = 1.0,
        hero_seat: int = 0,
        bot_archetype: str = "Balanced Reg",
        bot_archetypes: Optional[Dict[int, str]] = None,
    ):
        self.num_players = min(max(num_players, 2), 11)
        self.starting_stack = starting_stack
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.hero_seat = hero_seat
        self.hand_count = 0
        self.dealer_idx = 0
        self.deck = Deck()

        # Create players
        positions = positions_for(num_players)
        bot_profiles = list(BOT_ARCHETYPES.values())
        # Resolve the default archetype profile if it exists, otherwise use index 0
        default_profile = BOT_ARCHETYPES.get(bot_archetype) or bot_profiles[0]

        # bot_archetypes maps seat_idx → archetype name; falls back to bot_archetype
        # for any unspecified seat. None means "use the default for every bot".
        per_seat_archetypes = bot_archetypes or {}

        self.players: List[PlayerSeat] = []
        self.bots: Dict[int, BotBrain] = {}

        for i in range(self.num_players):
            pos = positions[i % len(positions)]
            if i == hero_seat:
                self.players.append(PlayerSeat(
                    name="Hero", stack=starting_stack,
                    position=pos, is_hero=True,
                ))
            else:
                arch_name = per_seat_archetypes.get(i, bot_archetype)
                profile = BOT_ARCHETYPES.get(arch_name) or default_profile
                self.players.append(PlayerSeat(
                    name=profile.name, stack=starting_stack,
                    position=pos, is_hero=False,
                ))
                self.bots[i] = BotBrain(profile)

        self.current_hand: Optional[HandState] = None
        self.hand_history: List[HandResult] = []
        self._waiting_for_hero = False
        self._hero_action_callback: Optional[Callable] = None

    @property
    def is_waiting_for_hero(self) -> bool:
        return self._waiting_for_hero

    def start_hand(self) -> HandState:
        """Deal a new hand and run until hero needs to act or hand completes."""
        self.hand_count += 1
        self.deck.shuffle()

        # Reset players
        for p in self.players:
            p.reset_for_hand()

        # Assign positions. dealer_idx is the BTN seat (player with the
        # dealer button). Heads-up is special — in HU the dealer is the SB,
        # so seat at dealer_idx posts SB and seat at dealer_idx+1 posts BB.
        positions = positions_for(self.num_players)
        n = self.num_players
        if n == 2:
            # HU: positions_for() returns ["SB","BB"]; dealer = SB = positions[0]
            self.players[self.dealer_idx].position           = positions[0]  # SB (dealer)
            self.players[(self.dealer_idx + 1) % n].position = positions[1]  # BB
        else:
            # Non-HU: positions[0]="SB" goes to dealer_idx+1, BTN wraps back to dealer_idx
            for i in range(n):
                idx = (self.dealer_idx + i + 1) % n
                self.players[idx].position = positions[i]

        # Create hand state
        self.current_hand = HandState(
            hand_id=self.hand_count,
            players=self.players,
            dealer_idx=self.dealer_idx,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
        )

        # Post blinds
        self._post_blinds()

        # Deal hole cards
        for p in self.players:
            p.hole_cards = self.deck.deal(2)

        # Start preflop action
        self._run_until_hero_or_complete()
        return self.current_hand

    def hero_act(self, action_type: ActionType, amount: float = 0.0) -> HandState:
        """Process hero's action and continue the hand."""
        if not self._waiting_for_hero or not self.current_hand:
            return self.current_hand

        hero_idx = self.current_hand.hero_idx
        self._apply_action(hero_idx, action_type, amount)
        self._waiting_for_hero = False

        # Continue running
        self._run_until_hero_or_complete()
        return self.current_hand

    def _post_blinds(self) -> None:
        hand = self.current_hand
        n = self.num_players

        if n == 2:
            sb_idx = self.dealer_idx
            bb_idx = (self.dealer_idx + 1) % n
        else:
            sb_idx = (self.dealer_idx + 1) % n
            bb_idx = (self.dealer_idx + 2) % n

        # Post small blind
        sb = min(hand.small_blind, self.players[sb_idx].stack)
        self.players[sb_idx].stack -= sb
        self.players[sb_idx].current_bet = sb
        self.players[sb_idx].invested_this_hand = sb
        hand.pot += sb

        # Post big blind
        bb = min(hand.big_blind, self.players[bb_idx].stack)
        self.players[bb_idx].stack -= bb
        self.players[bb_idx].current_bet = bb
        self.players[bb_idx].invested_this_hand = bb
        hand.pot += bb

        hand.current_bet = hand.big_blind
        hand.min_raise = hand.big_blind

    def _get_action_order(self) -> List[int]:
        """Get player indices in action order for current street."""
        hand = self.current_hand
        n = self.num_players

        if hand.street == Street.PREFLOP:
            if n == 2:
                start = self.dealer_idx  # SB acts first preflop in HU
            else:
                start = (self.dealer_idx + 3) % n  # UTG
        else:
            if n == 2:
                start = (self.dealer_idx + 1) % n
            else:
                start = (self.dealer_idx + 1) % n  # SB

        order = []
        for i in range(n):
            idx = (start + i) % n
            if self.players[idx].is_active:
                order.append(idx)
        return order

    def _run_until_hero_or_complete(self) -> None:
        """Run the hand forward until hero needs to act or hand is done."""
        hand = self.current_hand
        if not hand or hand.is_complete:
            return

        while True:
            # Check if hand is over
            if hand.active_count <= 1:
                self._finish_hand()
                return

            if hand.street == Street.SHOWDOWN:
                self._finish_hand()
                return

            # Run betting round
            if self._run_betting_round_step():
                return  # Waiting for hero

            # Betting round complete — advance street
            if hand.active_count <= 1:
                self._finish_hand()
                return

            self._advance_street()

    def _run_betting_round_step(self) -> bool:
        """Run one step of betting. Returns True if waiting for hero."""
        hand = self.current_hand
        order = self._get_action_order()

        # Find the next player who hasn't acted or needs to respond to a raise
        for idx in order:
            player = self.players[idx]
            if not player.is_active:
                continue

            needs_to_act = (
                not player.has_acted or
                player.current_bet < hand.current_bet
            )

            if not needs_to_act:
                continue

            if player.is_hero:
                self._waiting_for_hero = True
                return True  # Pause for hero input
            else:
                # Bot decides
                bot = self.bots.get(idx)
                if bot:
                    action_type, amount = bot.decide(hand, idx)
                    self._apply_action(idx, action_type, amount)

                    # After a raise, other players may need to act again
                    if action_type in (ActionType.RAISE, ActionType.BET):
                        return self._run_betting_round_step()

        # All players have acted
        return False

    def _apply_action(self, player_idx: int, action_type: ActionType, amount: float) -> None:
        """Apply an action to the hand state."""
        hand = self.current_hand
        player = self.players[player_idx]

        if action_type == ActionType.FOLD:
            player.is_folded = True
            player.has_acted = True

        elif action_type == ActionType.CHECK:
            player.has_acted = True

        elif action_type == ActionType.CALL:
            to_call = min(hand.current_bet - player.current_bet, player.stack)
            player.stack -= to_call
            player.current_bet += to_call
            player.invested_this_hand += to_call
            hand.pot += to_call
            if player.stack <= 0:
                player.is_all_in = True
            player.has_acted = True

        elif action_type in (ActionType.BET, ActionType.RAISE):
            amount = min(amount, player.stack)
            old_bet = player.current_bet
            player.stack -= amount
            player.current_bet += amount
            player.invested_this_hand += amount
            hand.pot += amount

            raise_size = player.current_bet - hand.current_bet
            if raise_size > 0:
                hand.min_raise = raise_size
            hand.current_bet = player.current_bet

            if player.stack <= 0:
                player.is_all_in = True

            # Reset other players' has_acted
            for i, p in enumerate(self.players):
                if i != player_idx and p.is_active:
                    p.has_acted = False
            player.has_acted = True

        elif action_type == ActionType.ALL_IN:
            all_in_amount = player.stack
            player.current_bet += all_in_amount
            player.invested_this_hand += all_in_amount
            hand.pot += all_in_amount
            player.stack = 0
            player.is_all_in = True

            if player.current_bet > hand.current_bet:
                raise_size = player.current_bet - hand.current_bet
                hand.min_raise = max(hand.min_raise, raise_size)
                hand.current_bet = player.current_bet
                for i, p in enumerate(self.players):
                    if i != player_idx and p.is_active:
                        p.has_acted = False
            player.has_acted = True

        # Record action
        hand.actions.append(Action(
            player_idx=player_idx,
            action_type=action_type,
            amount=amount,
            street=hand.street,
        ))

    def _advance_street(self) -> None:
        """Deal community cards and advance to next street."""
        hand = self.current_hand

        # Reset for new street
        for p in self.players:
            p.reset_for_street()
        hand.current_bet = 0
        hand.min_raise = hand.big_blind

        next_street = hand.street.next_street
        if not next_street or next_street == Street.SHOWDOWN:
            hand.street = Street.SHOWDOWN
            return

        hand.street = next_street

        if next_street == Street.FLOP:
            self.deck.deal(1)  # Burn
            hand.community.extend(self.deck.deal(3))
        elif next_street == Street.TURN:
            self.deck.deal(1)  # Burn
            hand.community.extend(self.deck.deal(1))
        elif next_street == Street.RIVER:
            self.deck.deal(1)  # Burn
            hand.community.extend(self.deck.deal(1))

    def _finish_hand(self) -> None:
        """Resolve the hand: showdown or last player standing."""
        hand = self.current_hand
        hand.is_complete = True

        active_players = [(i, p) for i, p in enumerate(self.players) if not p.is_folded]

        if len(active_players) == 1:
            # Last player standing
            winner_idx = active_players[0][0]
            hand.winners = [winner_idx]
            hand.winner_hand_name = "Last player standing"
            self.players[winner_idx].stack += hand.pot
        else:
            # Showdown — deal remaining community cards if needed
            while len(hand.community) < 5:
                self.deck.deal(1)  # Burn
                hand.community.extend(self.deck.deal(1))

            # Evaluate hands
            players_hands = [(i, p.hole_cards) for i, p in active_players]
            winners, hand_name = determine_winners(players_hands, hand.community)
            hand.winners = winners
            hand.winner_hand_name = hand_name

            # Distribute pot
            share = hand.pot / len(winners)
            for w in winners:
                self.players[w].stack += share

        # Record result
        hero_idx = hand.hero_idx
        hero = self.players[hero_idx]
        hero_profit = hero.stack - self.starting_stack - sum(
            r.hero_profit for r in self.hand_history
        )
        # More precise: profit = current stack - (start of hand stack)
        pre_hand_stack = hero.invested_this_hand + hero.stack
        if hero_idx in hand.winners:
            share = hand.pot / len(hand.winners)
            hero_profit = share - hero.invested_this_hand
        else:
            hero_profit = -hero.invested_this_hand

        result = HandResult(
            hand_id=hand.hand_id,
            hero_cards=hero.cards_display,
            community=hand.community_display,
            pot=hand.pot,
            winners=hand.winners,
            winner_hand_name=hand.winner_hand_name,
            hero_won=hero_idx in hand.winners,
            hero_profit=round(hero_profit, 2),
            actions=list(hand.actions),
            hero_invested=hero.invested_this_hand,
            streets_seen=_count_streets(hand),
        )
        self.hand_history.append(result)

        # Advance dealer
        self.dealer_idx = (self.dealer_idx + 1) % self.num_players

    def get_session_stats(self) -> dict:
        """Calculate running session statistics."""
        if not self.hand_history:
            return {
                "hands": 0, "profit": 0, "vpip": 0, "pfr": 0,
                "wtsd": 0, "win_rate": 0, "biggest_pot": 0,
            }

        total = len(self.hand_history)
        wins = sum(1 for h in self.hand_history if h.hero_won)
        profit = sum(h.hero_profit for h in self.hand_history)
        vpip_count = sum(1 for h in self.hand_history if h.hero_invested > self.big_blind)
        pfr_count = sum(
            1 for h in self.hand_history
            if any(
                a.action_type in (ActionType.BET, ActionType.RAISE)
                and a.player_idx == self.hero_seat
                and a.street == Street.PREFLOP
                for a in h.actions
            )
        )
        showdown = sum(1 for h in self.hand_history if h.streets_seen >= 4)
        biggest = max(h.pot for h in self.hand_history)

        return {
            "hands": total,
            "profit": round(profit, 2),
            "profit_bb": round(profit / self.big_blind, 1),
            "vpip": round(100 * vpip_count / total, 1) if total else 0,
            "pfr": round(100 * pfr_count / total, 1) if total else 0,
            "wtsd": round(100 * showdown / total, 1) if total else 0,
            "win_rate": round(100 * wins / total, 1) if total else 0,
            "biggest_pot": round(biggest, 2),
            "bb_per_100": round(100 * profit / (total * self.big_blind), 1) if total else 0,
        }


def _count_streets(hand: HandState) -> int:
    streets_with_actions = set()
    for a in hand.actions:
        streets_with_actions.add(a.street)
    return len(streets_with_actions)
