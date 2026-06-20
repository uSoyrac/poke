"""Texas Hold'em game engine.

Fixes vs previous version:
- Proper action-order continuation after a raise (no recursion, no restart from UTG)
- Min-raise validation (illegal raise = bumped up to legal min, or treated as call)
- All-in for less than min-raise does NOT reopen action for already-acted players
- Side pots correctly distributed on multi-way all-in showdowns
- Busted (stack=0) players auto-skipped, dealer button advances over them
- Hero profit computed per-hand directly (not from running totals)
- Ante support
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.engine.bot_brain import BotBrain, BotProfile, BOT_ARCHETYPES, KARMA_MIX
from app.engine.evaluator import determine_winners
from app.engine.hand_state import (
    Action, ActionType, Card, Deck, HandState, PlayerSeat, SUITS,
    Street, POSITIONS_BY_SIZE,
)


@dataclass
class HandResult:
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
    hero_position: str = ""
    final_stacks: Dict[int, float] = field(default_factory=dict)
    # Gerçek poker istatistik bayrakları (preflop GÖNÜLLÜ aksiyondan türetilir,
    # kör/ante/postflop biriken çipten DEĞİL) — VPIP/PFR/3bet doğruluğu için.
    hero_vpip: bool = False
    hero_pfr: bool = False
    hero_3bet_opp: bool = False
    hero_3bet: bool = False
    hero_postflop_aggr: int = 0     # postflop bet/raise/all-in sayısı
    hero_postflop_passive: int = 0  # postflop call sayısı (AF için)


def hero_stat_fields(result) -> Dict[str, object]:
    """HandResult'tan DB'ye yazılacak gerçek istatistik bayraklarını çıkar.
    Üç kayıt yeri (play/tournament/fast) aynı doğru alanları yazsın diye ortak."""
    return {
        "hero_vpip": getattr(result, "hero_vpip", None),
        "hero_pfr": getattr(result, "hero_pfr", None),
        "hero_3bet_opp": getattr(result, "hero_3bet_opp", None),
        "hero_3bet": getattr(result, "hero_3bet", None),
        "hero_postflop_aggr": getattr(result, "hero_postflop_aggr", None),
        "hero_postflop_passive": getattr(result, "hero_postflop_passive", None),
    }


def hero_preflop_flags(hand, hero_idx: int) -> Dict[str, bool]:
    """Bir elin aksiyonlarından hero'nun PREFLOP istatistik bayraklarını türet.

    Gerçek poker tanımları (kör yatırma ve BB bedava check SAYILMAZ):
      • vpip          : preflop gönüllü CALL/RAISE/BET/ALL_IN
      • pfr           : preflop RAISE/BET/ALL_IN
      • threebet_opp  : hero aksiyonundan ÖNCE bir açılış (raise) vardı
      • threebet      : threebet_opp iken hero yeniden raise etti
    """
    from app.engine.hand_state import ActionType as _AT, Street as _St

    actions = getattr(hand, "actions", []) or []
    pf = [a for a in actions
          if a.player_idx == hero_idx and a.street == _St.PREFLOP]
    voluntary = {_AT.CALL, _AT.RAISE, _AT.BET, _AT.ALL_IN}
    raising = {_AT.RAISE, _AT.BET, _AT.ALL_IN}

    vpip = any(a.action_type in voluntary for a in pf)
    pfr = any(a.action_type in raising for a in pf)

    # Hero'nun İLK preflop aksiyonundan önce bir açılış (raise) oldu mu?
    first_hero = next((a for a in actions
                       if a.player_idx == hero_idx and a.street == _St.PREFLOP), None)
    opp = False
    if first_hero is not None:
        idx_first = actions.index(first_hero)
        opp = any(
            a.street == _St.PREFLOP and a.player_idx != hero_idx
            and a.action_type in (_AT.RAISE, _AT.BET)
            for a in actions[:idx_first]
        )
    threebet = bool(opp and pfr)

    # Postflop agresyon sayıları (AF = aggr/passive için)
    post = [a for a in actions
            if a.player_idx == hero_idx and a.street != _St.PREFLOP]
    aggr = sum(1 for a in post if a.action_type in raising)
    passive = sum(1 for a in post if a.action_type == _AT.CALL)
    return {"vpip": bool(vpip), "pfr": bool(pfr),
            "threebet_opp": bool(opp), "threebet": threebet,
            "postflop_aggr": aggr, "postflop_passive": passive}


class PokerGame:
    """Manages a full poker game session (cash or tournament hand-by-hand)."""

    # ── RANGE FILTER PRESETS ──────────────────────────────────────
    _RANGE_PRESETS: Dict[str, set] = {
        "Premium":    {"AA", "KK", "QQ", "JJ", "AKs", "AKo"},
        "TAG Range":  {"AA", "KK", "QQ", "JJ", "TT", "99", "88",
                       "AKs", "AKo", "AQs", "AQo", "AJs", "ATs",
                       "KQs", "KJs", "KTs", "QJs", "JTs", "T9s"},
        "Geniş Range":{"AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
                       "AKs", "AKo", "AQs", "AQo", "AJs", "AJo", "ATs", "ATo",
                       "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
                       "KQs", "KQo", "KJs", "KTs", "QJs", "QTs",
                       "JTs", "T9s", "98s", "87s", "76s", "65s", "54s"},
        "Speculative": {"77", "66", "55", "44", "33", "22",
                        "A5s", "A4s", "A3s", "A2s",
                        "JTs", "T9s", "98s", "87s", "76s", "65s", "54s",
                        "QTs", "KTs", "KJs"},
    }

    def __init__(
        self,
        num_players: int = 6,
        starting_stack: float = 100.0,
        small_blind: float = 0.5,
        big_blind: float = 1.0,
        ante: float = 0.0,
        hero_seat: int = 0,
        bot_archetype: str = "Balanced Reg",
        bot_archetypes: Optional[List[str]] = None,
        player_names: Optional[List[str]] = None,
        paced_bots: bool = False,
        hero_range_filter: str = "",   # "" = all hands; preset name = filter
    ):
        self.num_players = max(2, min(num_players, 9))
        self.starting_stack = starting_stack
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.ante = ante
        self.hero_seat = hero_seat
        self.hand_count = 0
        self.dealer_idx = 0
        self.deck = Deck()
        self.hero_range_filter = hero_range_filter
        # When True, start_hand() and hero_act() return after posting
        # blinds / applying the hero action without running any bot. The
        # caller (UI) drives bot decisions one at a time via step_action()
        # so the user sees the action order play out visibly.
        self.paced_bots = paced_bots

        # Bot archetypes — either single archetype repeated, or list.
        # "Karma (Mixed)" is a meta-archetype: RANDOMLY sample distinct
        # archetypes from the full pool so every game has a different
        # field composition (TAG one game, two Maniacs the next, etc.).
        import random as _random
        if bot_archetypes is None:
            num_bots = self.num_players - 1
            if bot_archetype == "Karma (Mixed)":
                # Sample WITHOUT replacement from the full KARMA_MIX pool —
                # if num_bots > pool size, fall back to with-replacement.
                pool = list(KARMA_MIX)
                if num_bots <= len(pool):
                    bot_archetypes = _random.sample(pool, num_bots)
                else:
                    bot_archetypes = _random.sample(pool, len(pool))
                    bot_archetypes += [_random.choice(pool)
                                       for _ in range(num_bots - len(pool))]
                _random.shuffle(bot_archetypes)
            else:
                bot_archetypes = [bot_archetype] * num_bots
        bot_archetypes = list(bot_archetypes)

        # Build players
        positions = POSITIONS_BY_SIZE.get(self.num_players, POSITIONS_BY_SIZE[6])
        self.players: List[PlayerSeat] = []
        self.bots: Dict[int, BotBrain] = {}

        bot_idx = 0
        default_names = ["villain_42", "BluffMaster", "icmer_X", "shovingsteve",
                         "justplaying", "deepstacked", "blockerOnly", "stationboy"]
        for i in range(self.num_players):
            pos = positions[i % len(positions)]
            if i == hero_seat:
                self.players.append(PlayerSeat(
                    name="Hero", stack=starting_stack, position=pos, is_hero=True,
                ))
            else:
                name = (player_names[bot_idx] if player_names and bot_idx < len(player_names)
                        else default_names[bot_idx % len(default_names)])
                profile_name = bot_archetypes[bot_idx % len(bot_archetypes)]
                profile = BOT_ARCHETYPES.get(profile_name, BOT_ARCHETYPES["Balanced Reg"])
                self.players.append(PlayerSeat(
                    name=name, stack=starting_stack, position=pos, is_hero=False,
                ))
                self.bots[i] = BotBrain(profile)
                bot_idx += 1

        self.current_hand: Optional[HandState] = None
        self.hand_history: List[HandResult] = []
        self._waiting_for_hero = False
        self._action_queue: List[int] = []  # FIFO of player indices yet to act this round
        self._last_aggressor: Optional[int] = None

    # ── PUBLIC API ─────────────────────────────────────────────────

    @property
    def is_waiting_for_hero(self) -> bool:
        return self._waiting_for_hero

    @property
    def active_players_count(self) -> int:
        """Players with chips remaining (in the session)."""
        return sum(1 for p in self.players if p.stack > 0 and not p.is_eliminated)

    def get_bot_profiles(self) -> Dict[int, "BotProfile"]:
        """Return {player_idx: BotProfile} — used by the UI for HUD hover tooltips."""
        return {idx: brain.profile for idx, brain in self.bots.items()}

    def _range_target(self):
        """Aktif hero range filtresinin hedef el-kümesi (set) ya da None.

        None → 'tüm eller' (filtre yok). Filtre hem PRESET adı (str) hem de
        chart picker'dan gelen ÖZEL el kümesi (set/list/frozenset) olabilir.
        Boş küme ya da 169 elin tamamı → None (filtre yok, sonsuz döngü yok).
        """
        f = self.hero_range_filter
        if not f or f in ("Tüm Eller", "Tüm Eller (GTO Default)"):
            return None
        if isinstance(f, (set, frozenset, list, tuple)):
            target = {str(h) for h in f}
            # boş ya da tam-169 → filtre yok
            if not target or len(target) >= 169:
                return None
            return target
        return self._RANGE_PRESETS.get(f)   # preset adı

    def _hand_in_range(self, cards: list) -> bool:
        """Return True if hero's hole cards match the active hero_range_filter."""
        target = self._range_target()
        if not target or len(cards) < 2:
            return True

        RANKS_ORDER = "23456789TJQKA"
        r1, r2 = cards[0].rank, cards[1].rank
        suited = cards[0].suit == cards[1].suit

        # Normalize: higher rank first
        if RANKS_ORDER.index(r1) < RANKS_ORDER.index(r2):
            r1, r2 = r2, r1

        if r1 == r2:
            hand_key = f"{r1}{r2}"
        else:
            hand_key = f"{r1}{r2}{'s' if suited else 'o'}"

        return hand_key in target

    @staticmethod
    def _cards_for_key(key: str) -> list:
        """'AA'/'AKs'/'AKo' → uygun suit'lerle 2 somut Card."""
        import random as _r
        r1, r2 = key[0], key[1]
        suits = list(SUITS)
        if len(key) == 2:                       # pair → iki farklı suit
            s1, s2 = _r.sample(suits, 2)
            return [Card(r1, s1), Card(r2, s2)]
        if key.endswith("s"):                   # suited → aynı suit
            s = _r.choice(suits)
            return [Card(r1, s), Card(r2, s)]
        s1, s2 = _r.sample(suits, 2)            # offsuit → farklı suit
        return [Card(r1, s1), Card(r2, s2)]

    def _deal_hero_from_range(self, in_game: list, target: set) -> None:
        """Hero'ya seçili kümeden rastgele bir el ver, kalanı normal dağıt."""
        import random as _r
        key = _r.choice(list(target))
        hero_cards = self._cards_for_key(key)
        self.deck = Deck()
        self.deck.shuffle()
        self.deck.remove(hero_cards)            # hero kartlarını desteden çıkar
        self.players[self.hero_seat].hole_cards = list(hero_cards)
        for i in in_game:
            if i != self.hero_seat:
                self.players[i].hole_cards = self.deck.deal(2)

    def set_blinds(self, small_blind: float, big_blind: float, ante: float = 0.0) -> None:
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.ante = ante

    def start_hand(self) -> HandState:
        """Deal a new hand. Runs until hero needs to act or hand ends."""
        self.hand_count += 1
        self.deck = Deck()
        self.deck.shuffle()

        # Eliminate busted players (no chips)
        for p in self.players:
            if p.stack <= 0 and not p.is_eliminated:
                p.is_eliminated = True

        in_game = [i for i, p in enumerate(self.players) if not p.is_eliminated]
        if len(in_game) < 2:
            # Game over — only one player remains
            self.current_hand = HandState(hand_id=self.hand_count, players=self.players)
            self.current_hand.is_complete = True
            return self.current_hand

        # Reset players for new hand
        for p in self.players:
            p.reset_for_hand()

        # Advance dealer to next non-eliminated player
        self._advance_dealer()

        # Assign positions (rotating from dealer)
        self._assign_positions()

        # Create hand state
        self.current_hand = HandState(
            hand_id=self.hand_count,
            players=self.players,
            dealer_idx=self.dealer_idx,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
            ante=self.ante,
            current_bet=0.0,
            min_raise=self.big_blind,
            last_full_raise_size=self.big_blind,
        )

        self._post_antes()
        self._post_blinds()

        # Deal hole cards — hero range filtresi aktifse hero'ya DOĞRUDAN
        # seçili kümeden bir el inşa et (eski 60-deneme re-deal yöntemi sıkı
        # filtrelerde sık başarısız oluyordu; bu O(1) ve her zaman tutar).
        target = self._range_target()
        if target and self.hero_seat in in_game:
            self._deal_hero_from_range(in_game, target)
        else:
            for i in in_game:
                self.players[i].hole_cards = self.deck.deal(2)

        # Set up action queue for preflop
        self._build_action_queue(preflop=True)
        self._waiting_for_hero = False
        # Paced mode → caller drives bots via step_action(). Synchronous
        # mode (default, for tests) → run until hero or hand complete.
        if not self.paced_bots:
            self._run_until_hero_or_complete()
        return self.current_hand

    def hero_act(self, action_type: ActionType, amount: float = 0.0) -> HandState:
        """Apply hero's chosen action."""
        if not self._waiting_for_hero or not self.current_hand:
            return self.current_hand

        hero_idx = self.current_hand.hero_idx
        # Validate / coerce amount to legal value
        action_type, amount = self._coerce_action(hero_idx, action_type, amount)
        self._apply_action(hero_idx, action_type, amount)
        self._waiting_for_hero = False
        if not self.paced_bots:
            self._run_until_hero_or_complete()
        return self.current_hand

    # ── INTERNAL: SETUP ────────────────────────────────────────────

    def _advance_dealer(self) -> None:
        n = self.num_players
        active_seats = [i for i, p in enumerate(self.players) if not p.is_eliminated]
        if not active_seats:
            return
        if self.hand_count == 1:
            self.dealer_idx = active_seats[0]
            return
        for step in range(1, n + 1):
            cand = (self.dealer_idx + step) % n
            if not self.players[cand].is_eliminated:
                self.dealer_idx = cand
                return

    def _assign_positions(self) -> None:
        in_game = [i for i, p in enumerate(self.players) if not p.is_eliminated]
        size = len(in_game)
        if size < 2:
            return
        positions = POSITIONS_BY_SIZE.get(size, POSITIONS_BY_SIZE[max(in_game and 2 or 2, 2)])
        # Sorted order starting from SB
        # In poker rotation: BTN = dealer. SB = dealer+1, BB = dealer+2.
        # Exception HU: BTN = SB (acts first preflop). We'll mark dealer as "SB/BTN".
        ordered = []
        n = self.num_players
        for step in range(n):
            seat = (self.dealer_idx + 1 + step) % n
            if not self.players[seat].is_eliminated:
                ordered.append(seat)
        # Now ordered[0] = SB-equivalent. Map to positions.
        # For HU: ordered = [SB/BTN, BB] but SB is also BTN. Use HU labels.
        if size == 2:
            # dealer = button = SB acts first preflop. ordered[0] (= dealer+1) = BB.
            # We want SB/BTN first. Re-derive: SB/BTN = dealer.
            self.players[self.dealer_idx].position = "SB/BTN"
            other = [i for i in in_game if i != self.dealer_idx][0]
            self.players[other].position = "BB"
        else:
            for i, seat in enumerate(ordered):
                self.players[seat].position = positions[i] if i < len(positions) else f"S{i}"

    def _post_antes(self) -> None:
        if self.ante <= 0 or not self.current_hand:
            return
        hand = self.current_hand
        for p in self.players:
            if p.is_eliminated:
                continue
            a = min(self.ante, p.stack)
            p.stack -= a
            p.invested_this_hand += a
            hand.pot += a
            if p.stack <= 0:
                p.is_all_in = True

    def _post_blinds(self) -> None:
        hand = self.current_hand
        in_game = [i for i, p in enumerate(self.players) if not p.is_eliminated]
        n_in = len(in_game)
        if n_in < 2:
            return

        if n_in == 2:
            # HU: dealer = SB, other = BB
            sb_idx = self.dealer_idx
            bb_idx = next(i for i in in_game if i != self.dealer_idx)
        else:
            sb_idx = self._next_in_game(self.dealer_idx)
            bb_idx = self._next_in_game(sb_idx)

        sb = min(hand.small_blind, self.players[sb_idx].stack)
        self.players[sb_idx].stack -= sb
        self.players[sb_idx].current_bet = sb
        self.players[sb_idx].invested_this_hand += sb
        hand.pot += sb
        if self.players[sb_idx].stack <= 0:
            self.players[sb_idx].is_all_in = True

        bb = min(hand.big_blind, self.players[bb_idx].stack)
        self.players[bb_idx].stack -= bb
        self.players[bb_idx].current_bet = bb
        self.players[bb_idx].invested_this_hand += bb
        hand.pot += bb
        if self.players[bb_idx].stack <= 0:
            self.players[bb_idx].is_all_in = True

        hand.current_bet = hand.big_blind
        hand.last_full_raise_size = hand.big_blind
        hand.min_raise = hand.big_blind

    def _next_in_game(self, from_idx: int) -> int:
        n = self.num_players
        for step in range(1, n + 1):
            cand = (from_idx + step) % n
            if not self.players[cand].is_eliminated:
                return cand
        return from_idx

    # ── INTERNAL: BETTING ROUND ────────────────────────────────────

    def _build_action_queue(self, preflop: bool = False) -> None:
        """Build the initial action queue for current street."""
        hand = self.current_hand
        n = self.num_players
        in_game = [i for i, p in enumerate(self.players) if not p.is_eliminated]
        n_in = len(in_game)

        # First-to-act seat
        if preflop:
            if n_in == 2:
                start = self.dealer_idx  # SB acts first HU
            else:
                # UTG = SB+2 (i.e. dealer+3 in non-HU)
                bb = self._next_in_game(self._next_in_game(self.dealer_idx))
                start = self._next_in_game(bb)
        else:
            # Postflop: first active player left of dealer
            start = self._next_in_game(self.dealer_idx)

        self._action_queue = []
        cursor = start
        for _ in range(n):
            if self.players[cursor].is_active:
                self._action_queue.append(cursor)
            cursor = (cursor + 1) % n
            if cursor == start:
                break
        # Ensure all eligible active players are queued (in case `start` is folded/all-in)
        if not self._action_queue:
            for idx in range(n):
                cand = (start + idx) % n
                if self.players[cand].is_active:
                    self._action_queue.append(cand)
        self._last_aggressor = None

    def _on_raise_rebuild_queue(self, raiser_idx: int, reopens: bool) -> None:
        """After a raise, players who already acted (other than raiser) need to act again.
        If `reopens` is False (short all-in below min raise), already-acted players don't re-act.
        """
        n = self.num_players
        new_queue: List[int] = []
        cursor = (raiser_idx + 1) % n
        for _ in range(n):
            if cursor == raiser_idx:
                break
            p = self.players[cursor]
            if p.is_active and (reopens or not p.has_acted or p.current_bet < self.current_hand.current_bet):
                # If reopens: everyone else must act again. If not: only those who haven't matched the new bet.
                if reopens or p.current_bet < self.current_hand.current_bet:
                    new_queue.append(cursor)
            cursor = (cursor + 1) % n
        self._action_queue = new_queue
        if reopens:
            self._last_aggressor = raiser_idx
            for idx in new_queue:
                self.players[idx].has_acted = False

    def step_action(self) -> bool:
        """Process ONE engine step — a single bot action, street advance,
        or a queue-pop of an inactive seat.

        Returns:
            True  → work was done; call again to continue.
            False → engine is now either ``is_waiting_for_hero`` or the
                    hand is complete. Stop the loop.

        This is what `_run_until_hero_or_complete` calls in a tight loop.
        The UI can also call it directly with a QTimer between calls to
        pace bot decisions visually (UTG first, then UTG+1, …) instead
        of seeing every opponent's action materialise at once.
        """
        hand = self.current_hand
        if not hand or hand.is_complete:
            return False

        # If only one player remains in the hand, award pot
        if hand.active_count <= 1:
            self._finish_hand()
            return False

        # If betting is concluded, advance street
        if not self._action_queue:
            if self._betting_round_complete():
                if self._all_in_runout_needed():
                    self._runout_remaining_streets()
                    self._finish_hand()
                    return False
                if hand.street == Street.RIVER:
                    self._finish_hand()
                    return False
                self._advance_street()
                return True
            # Defensive rebuild
            self._build_action_queue(preflop=(hand.street == Street.PREFLOP))
            if not self._action_queue:
                if hand.street == Street.RIVER:
                    self._finish_hand()
                    return False
                self._advance_street()
                return True

        next_idx = self._action_queue[0]
        player = self.players[next_idx]
        if not player.is_active:
            self._action_queue.pop(0)
            return True
        # D294 (kullanıcı yakaladı: hero 0bb → UI yalnız FOLD sunup turnuvayı öldürüyor):
        # ALL-IN / 0-çip oyuncu aksiyon ALAMAZ. is_all_in bayrağı bir yolda kaçmış olabilir
        # (stack 0 ama is_active hâlâ True) → burada yakala: all-in işaretle, kuyruktan çıkar
        # (board açılır → showdown). Hero ASLA 0bb'de prompt almasın (yalnız-FOLD = forfeit =
        # yanlış bust). Savunma-guard: kökü ne olursa olsun 0-çip oyuncu prompt almaz.
        if player.stack <= 1e-9:
            player.is_all_in = True
            self._action_queue.pop(0)
            return True

        if player.is_hero:
            self._waiting_for_hero = True
            return False

        # Bot turn — one decision, one apply
        bot = self.bots.get(next_idx)
        if not bot:
            self._action_queue.pop(0)
            to_call = hand.to_call(next_idx)
            if to_call > 0:
                self._apply_action(next_idx, ActionType.FOLD, 0)
            else:
                self._apply_action(next_idx, ActionType.CHECK, 0)
            return True

        action_type, amount = bot.decide(hand, next_idx)
        action_type, amount = self._coerce_action(next_idx, action_type, amount)
        self._apply_action(next_idx, action_type, amount)
        return True

    def _run_until_hero_or_complete(self) -> None:
        """Synchronous: run all bots until hero acts or hand ends.

        Kept for backward-compat (existing tests rely on this). The UI
        now prefers paced stepping via ``step_action()`` to visualise
        the action order.
        """
        while self.step_action():
            pass

    def _betting_round_complete(self) -> bool:
        hand = self.current_hand
        for p in self.players:
            if not p.is_active:
                continue
            if p.current_bet < hand.current_bet:
                return False
            if not p.has_acted:
                return False
        return True

    def _all_in_runout_needed(self) -> bool:
        """If <=1 active players remain but multiple in hand, runout the board."""
        hand = self.current_hand
        return hand.active_count >= 2 and hand.can_act_count <= 1

    # ── INTERNAL: ACTION APPLICATION ───────────────────────────────

    def _coerce_action(self, player_idx: int, action_type: ActionType, amount: float) -> Tuple[ActionType, float]:
        """Ensure the action is legal; clamp amounts; convert raise<minraise to all-in."""
        hand = self.current_hand
        player = self.players[player_idx]
        to_call = hand.to_call(player_idx)

        if action_type == ActionType.FOLD:
            if to_call == 0:
                return ActionType.CHECK, 0.0
            return ActionType.FOLD, 0.0

        if action_type == ActionType.CHECK:
            if to_call > 0:
                return ActionType.FOLD, 0.0
            return ActionType.CHECK, 0.0

        if action_type == ActionType.CALL:
            call_amt = min(to_call, player.stack)
            if call_amt >= player.stack:
                return ActionType.ALL_IN, player.stack
            return ActionType.CALL, call_amt

        if action_type == ActionType.BET:
            if to_call > 0:
                # Not a bet — must be raise
                action_type = ActionType.RAISE
            else:
                amount = max(hand.big_blind, min(amount, player.stack))
                if amount >= player.stack:
                    return ActionType.ALL_IN, player.stack
                return ActionType.BET, amount

        if action_type == ActionType.RAISE:
            # `amount` is the chips to add (delta from current bet)
            # Total new bet level = player.current_bet + amount
            min_raise_to = hand.current_bet + max(hand.last_full_raise_size, hand.big_blind)
            min_amount_to_add = min_raise_to - player.current_bet
            amount = max(min_amount_to_add, amount)
            amount = min(amount, player.stack)
            if amount >= player.stack:
                return ActionType.ALL_IN, player.stack
            return ActionType.RAISE, amount

        if action_type == ActionType.ALL_IN:
            return ActionType.ALL_IN, player.stack

        return ActionType.CHECK, 0.0

    def _apply_action(self, player_idx: int, action_type: ActionType, amount: float) -> None:
        hand = self.current_hand
        player = self.players[player_idx]

        # Pop from queue
        if self._action_queue and self._action_queue[0] == player_idx:
            self._action_queue.pop(0)

        if action_type == ActionType.FOLD:
            player.is_folded = True
            player.has_acted = True

        elif action_type == ActionType.CHECK:
            player.has_acted = True

        elif action_type == ActionType.CALL:
            call_amt = min(amount, player.stack)
            player.stack -= call_amt
            player.current_bet += call_amt
            player.invested_this_hand += call_amt
            hand.pot += call_amt
            if player.stack <= 0:
                player.is_all_in = True
            player.has_acted = True

        elif action_type in (ActionType.BET, ActionType.RAISE):
            chips_added = min(amount, player.stack)
            player.stack -= chips_added
            new_bet = player.current_bet + chips_added
            raise_size = new_bet - hand.current_bet
            player.current_bet = new_bet
            player.invested_this_hand += chips_added
            hand.pot += chips_added

            # Full raise: reopens action
            reopens = raise_size >= hand.last_full_raise_size
            if raise_size > 0:
                if reopens:
                    hand.last_full_raise_size = raise_size
                hand.current_bet = new_bet
                hand.min_raise = hand.last_full_raise_size

            if player.stack <= 0:
                player.is_all_in = True

            player.has_acted = True
            self._on_raise_rebuild_queue(player_idx, reopens=reopens)

        elif action_type == ActionType.ALL_IN:
            chips_added = player.stack
            player.stack = 0
            new_bet = player.current_bet + chips_added
            raise_size = new_bet - hand.current_bet
            player.current_bet = new_bet
            player.invested_this_hand += chips_added
            hand.pot += chips_added
            player.is_all_in = True
            player.has_acted = True

            if raise_size > 0:
                reopens = raise_size >= hand.last_full_raise_size
                if reopens:
                    hand.last_full_raise_size = raise_size
                hand.current_bet = new_bet
                hand.min_raise = hand.last_full_raise_size
                self._on_raise_rebuild_queue(player_idx, reopens=reopens)
            # else: all-in for a partial call — no reopen

        # Record action
        hand.actions.append(Action(
            player_idx=player_idx,
            action_type=action_type,
            amount=round(amount, 2),
            street=hand.street,
            total_bet=round(player.current_bet, 2),
            pot_after=round(hand.pot, 2),
        ))

    # ── INTERNAL: STREETS ──────────────────────────────────────────

    def _advance_street(self) -> None:
        hand = self.current_hand
        for p in self.players:
            p.reset_for_street()
        hand.current_bet = 0.0
        hand.min_raise = hand.big_blind
        hand.last_full_raise_size = hand.big_blind

        nxt = hand.street.next_street
        if not nxt or nxt == Street.SHOWDOWN:
            hand.street = Street.SHOWDOWN
            return

        hand.street = nxt
        if nxt == Street.FLOP:
            self.deck.deal(1)
            hand.community.extend(self.deck.deal(3))
        elif nxt in (Street.TURN, Street.RIVER):
            self.deck.deal(1)
            hand.community.extend(self.deck.deal(1))

        self._build_action_queue(preflop=False)
        # If no one can act (all all-in), skip to next street via outer loop
        if not self._action_queue:
            return

    def _runout_remaining_streets(self) -> None:
        hand = self.current_hand
        while hand.street != Street.RIVER:
            self._advance_street()
            if hand.street == Street.SHOWDOWN:
                break

    # ── INTERNAL: SHOWDOWN & SIDE POTS ─────────────────────────────

    def _finish_hand(self) -> None:
        hand = self.current_hand
        hand.is_complete = True
        hand.street = Street.SHOWDOWN if hand.active_count > 1 else hand.street

        contestants = [i for i, p in enumerate(self.players) if p.is_in_hand]

        if len(contestants) == 1:
            # Last player standing — collect the whole pot
            winner_idx = contestants[0]
            hand.winners = [winner_idx]
            hand.winner_hand_name = "Uncontested"
            self.players[winner_idx].stack += hand.pot
            hand.pots = [{"amount": hand.pot, "winners": [winner_idx], "name": "Main pot"}]
        else:
            # Showdown — runout remaining streets if needed
            while len(hand.community) < 5:
                self.deck.deal(1)
                hand.community.extend(self.deck.deal(1))

            # Compute side pots
            side_pots = self._compute_side_pots(contestants)
            hand.winners = []
            hand.pots = []
            winner_hand_names: List[str] = []

            for sp in side_pots:
                eligible = sp["eligible"]
                if not eligible:
                    continue
                hands = [(i, self.players[i].hole_cards) for i in eligible]
                winners, hand_name = determine_winners(hands, hand.community)
                share = sp["amount"] / max(len(winners), 1)
                for w in winners:
                    self.players[w].stack += share
                for w in winners:
                    if w not in hand.winners:
                        hand.winners.append(w)
                hand.pots.append({
                    "amount": sp["amount"],
                    "winners": winners,
                    "name": sp.get("name", "Pot"),
                    "hand_name": hand_name,
                })
                winner_hand_names.append(hand_name)

            hand.winner_hand_name = " / ".join(dict.fromkeys(winner_hand_names)) or "Showdown"

        # Build result for hero
        hero_idx = hand.hero_idx
        hero = self.players[hero_idx]
        # Hero profit = (chips collected from pots) - invested
        chips_collected = 0.0
        for sp in hand.pots:
            if hero_idx in sp["winners"]:
                chips_collected += sp["amount"] / len(sp["winners"])
        hero_profit = chips_collected - hero.invested_this_hand

        _flags = hero_preflop_flags(hand, hero_idx)
        result = HandResult(
            hand_id=hand.hand_id,
            hero_cards=hero.cards_display,
            community=hand.community_display,
            pot=round(hand.pot, 2),
            winners=hand.winners,
            winner_hand_name=hand.winner_hand_name,
            hero_won=hero_idx in hand.winners,
            hero_profit=round(hero_profit, 2),
            actions=list(hand.actions),
            hero_invested=round(hero.invested_this_hand, 2),
            streets_seen=_count_streets(hand),
            hero_position=hero.position,
            final_stacks={i: round(p.stack, 2) for i, p in enumerate(self.players)},
            hero_vpip=_flags["vpip"],
            hero_pfr=_flags["pfr"],
            hero_3bet_opp=_flags["threebet_opp"],
            hero_3bet=_flags["threebet"],
            hero_postflop_aggr=_flags["postflop_aggr"],
            hero_postflop_passive=_flags["postflop_passive"],
        )
        self.hand_history.append(result)

    def _compute_side_pots(self, contestants: List[int]) -> List[dict]:
        """Compute main + side pots from invested_this_hand commitments."""
        invests = {i: self.players[i].invested_this_hand for i in range(self.num_players)}
        contestants = sorted(contestants, key=lambda i: invests[i])

        side_pots: List[dict] = []
        prev_level = 0.0

        # Compute pots level-by-level using sorted contestants
        contestant_set = set(contestants)
        used = set()
        # Include folded players' contributions: their chips go to the lowest pot
        # but they are not eligible to win it.
        sorted_invests = sorted(set(invests[i] for i in contestants))

        for level in sorted_invests:
            pot_amount = 0.0
            for j in range(self.num_players):
                contrib = min(invests[j], level) - min(invests[j], prev_level)
                if contrib > 0:
                    pot_amount += contrib
            eligible = [i for i in contestants if invests[i] >= level]
            if pot_amount > 0:
                side_pots.append({
                    "amount": round(pot_amount, 2),
                    "eligible": eligible,
                    "name": "Main pot" if not side_pots else f"Side pot {len(side_pots)}",
                })
            prev_level = level

        return side_pots

    # ── STATS ──────────────────────────────────────────────────────

    def get_session_stats(self) -> dict:
        if not self.hand_history:
            return {
                "hands": 0, "profit": 0, "profit_bb": 0, "vpip": 0, "pfr": 0,
                "wtsd": 0, "win_rate": 0, "biggest_pot": 0, "bb_per_100": 0,
                "showdowns": 0, "preflop_raises": 0,
            }
        total = len(self.hand_history)
        wins = sum(1 for h in self.hand_history if h.hero_won)
        profit = sum(h.hero_profit for h in self.hand_history)
        vpip_count = sum(
            1 for h in self.hand_history
            if any(
                a.player_idx == self.hero_seat and a.street == Street.PREFLOP
                and a.action_type in (ActionType.CALL, ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
        )
        pfr_count = sum(
            1 for h in self.hand_history
            if any(
                a.player_idx == self.hero_seat and a.street == Street.PREFLOP
                and a.action_type in (ActionType.BET, ActionType.RAISE, ActionType.ALL_IN)
                for a in h.actions
            )
        )
        showdown = sum(1 for h in self.hand_history if h.streets_seen >= 4)
        biggest = max(h.pot for h in self.hand_history)
        return {
            "hands": total,
            "profit": round(profit, 2),
            "profit_bb": round(profit / max(self.big_blind, 0.0001), 1),
            "vpip": round(100 * vpip_count / total, 1) if total else 0,
            "pfr": round(100 * pfr_count / total, 1) if total else 0,
            "wtsd": round(100 * showdown / total, 1) if total else 0,
            "win_rate": round(100 * wins / total, 1) if total else 0,
            "biggest_pot": round(biggest, 2),
            "bb_per_100": round(100 * profit / (total * self.big_blind), 1) if total else 0,
            "showdowns": showdown,
            "preflop_raises": pfr_count,
        }


def _count_streets(hand: HandState) -> int:
    streets = {a.street for a in hand.actions}
    return len(streets)
