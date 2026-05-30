"""Utility: build LivePokerTable state from a spot-drill dict or a hand-review dict.

All trainer screens that have a PokerTableView.set_hand() call should instead call
render_spot_on_table() or render_hand_on_table() from this module.
"""
from __future__ import annotations

from app.engine.hand_state import POSITIONS_BY_SIZE
from app.ui.components.poker_table import LivePokerTable, SeatState

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_cards(s: str | None) -> list[str]:
    """Kart string'ini ['As','Kh'] gibi tek-kartlık listeye ayır.

    Hem boşluklu ('As Kh', 'A♦ K♥') hem BİTİŞİK ('AsKh', '7c2d9s') formatları
    destekler — eskiden bitişik formatı tek token sanıp masada kapalı kart
    gösteriyordu (ICM/Math spotlarında hero eli görünmüyordu). Boş/preflop → [].
    """
    if not s or s.strip().lower() in ("", "preflop", "—", "-"):
        return []
    s = s.strip()
    if " " in s:
        return [c.strip() for c in s.split() if c.strip()]
    # Bitişik: her kart = 2 karakter (rank + suit; 'T' kullanılır, '10' değil)
    return [s[i:i + 2] for i in range(0, len(s) - 1, 2)]


def _table_size(table_str: str) -> int:
    t = table_str.upper()
    if "HU" in t or "2-MAX" in t:
        return 2
    if "9" in t:
        return 9
    return 6  # default 6-max


def _seats_from_spot(spot: dict) -> tuple[list[SeatState], int, int]:
    """Build seat list from spot-drill dict.

    Returns (seats, hero_slot_idx=0, dealer_slot_idx).
    Slot 0 is always hero at bottom-center (LivePokerTable convention).
    """
    num_players = _table_size(spot.get("table", "6-max"))
    positions: list[str] = list(POSITIONS_BY_SIZE.get(num_players, POSITIONS_BY_SIZE[6]))
    hero_pos = spot.get("position", "BTN")
    hero_stack = float(spot.get("stack_bb", 100))
    action_hist = spot.get("action_history", "").lower()

    # Villain positions (everything except hero)
    villain_positions = [p for p in positions if p != hero_pos]

    seats: list[SeatState] = [
        SeatState(pos=hero_pos, name="Hero", stack=hero_stack, is_hero=True)
    ]

    for i, pos in enumerate(villain_positions):
        p_lo = pos.lower()
        folded = p_lo in action_hist and (
            f"{p_lo} fold" in action_hist or f"{p_lo} folds" in action_hist
        )
        seats.append(SeatState(
            pos=pos,
            name="Bot",
            stack=hero_stack,
            is_folded=folded,
            is_villain=(i == 0 and not folded),
        ))

    # Dealer button at BTN slot
    dealer_slot = 0
    for i, s in enumerate(seats):
        if s.pos in ("BTN", "SB/BTN"):
            dealer_slot = i
            break

    return seats, 0, dealer_slot


def _default_seats(hero_pos: str = "BTN", hero_stack: float = 100.0) -> tuple[list[SeatState], int, int]:
    """Minimal 6-max seats for hand-review mode (no villain action info)."""
    positions = list(POSITIONS_BY_SIZE[6])
    villain_positions = [p for p in positions if p != hero_pos]

    seats: list[SeatState] = [
        SeatState(pos=hero_pos, name="Hero", stack=hero_stack, is_hero=True)
    ]
    for i, pos in enumerate(villain_positions):
        seats.append(SeatState(pos=pos, name="Bot", stack=hero_stack, is_villain=(i == 0)))

    dealer_slot = next((i for i, s in enumerate(seats) if s.pos in ("BTN", "SB/BTN")), 0)
    return seats, 0, dealer_slot


# ── public API ────────────────────────────────────────────────────────────────

def render_spot_on_table(table: LivePokerTable, spot: dict) -> None:
    """Populate LivePokerTable from a spot-drill dict (spot_trainer, combat, etc.)."""
    board = parse_cards(spot.get("board", ""))
    hero_cards = parse_cards(spot.get("hero_cards", ""))
    seats, hero_slot, dealer_slot = _seats_from_spot(spot)
    street = (spot.get("street") or "preflop").capitalize()
    table_label = spot.get("table", "6-max")
    pot = float(spot.get("pot_bb", 3.5))

    table.render_state(
        seats=seats,
        hero_slot_idx=hero_slot,
        dealer_slot_idx=dealer_slot,
        street=street,
        board=board,
        pot=pot,
        hero_cards=hero_cards or None,
        note=f"BLINDS 0.5 / 1  ·  {table_label}",
        show_opponent_backs=True,
    )


def render_hand_on_table(
    table: LivePokerTable,
    hero_cards: str,
    board: str,
    pot: float,
    position: str = "BTN",
    stack: float = 100.0,
) -> None:
    """Populate LivePokerTable from hand-review data (hand_analyzer, etc.)."""
    board_cards = parse_cards(board)
    hero_card_list = parse_cards(hero_cards)
    seats, hero_slot, dealer_slot = _default_seats(position, stack)

    street = (
        "River" if len(board_cards) == 5 else
        "Turn" if len(board_cards) == 4 else
        "Flop" if len(board_cards) >= 3 else
        "Preflop"
    )

    table.render_state(
        seats=seats,
        hero_slot_idx=hero_slot,
        dealer_slot_idx=dealer_slot,
        street=street,
        board=board_cards,
        pot=pot,
        hero_cards=hero_card_list or None,
        note=f"BLINDS 0.5 / 1  ·  6-max",
        show_opponent_backs=True,
    )
