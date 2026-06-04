"""GTO Range chart DİNAMİK node (Parça 1).

SS1/SS2: hero UTG+1 ile SB'nin 3-bet'ine karşı karar veriyordu ama 'GTO RANGE
ANALİZİ' dialog'u hardcoded scenario='RFI' ile hep açış range'i çiziyordu.
Artık live_gto_advice gerçek node'u (vs-3bet + 3-bet'çi pozisyonu) dışa açar,
dialog matrisi ona göre renklenir.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.engine.hand_state import (Action, ActionType, Card, HandState,
                                    PlayerSeat, Street)
from app.poker.gto_live_advice import live_gto_advice


def _vs_3bet_hand() -> HandState:
    h = HandState()
    h.big_blind = 1.0
    h.street = Street.PREFLOP
    h.current_bet = 13.6
    h.players = [
        PlayerSeat(name="hero", stack=107.0, position="MP", is_hero=True,
                   current_bet=2.5, hole_cards=[Card("A", "c"), Card("7", "c")]),
        PlayerSeat(name="sb", stack=86.0, position="SB", current_bet=13.6),
    ]
    h.pot = 2.5 + 13.6 + 1.0
    # Preflop: hero açtı (RAISE), SB 3-bet etti (RAISE) → vs 3-bet node
    h.actions = [
        Action(player_idx=0, action_type=ActionType.RAISE, amount=2.5,
               street=Street.PREFLOP),
        Action(player_idx=1, action_type=ActionType.RAISE, amount=13.6,
               street=Street.PREFLOP),
    ]
    return h


def test_live_advice_exposes_vs_3bet_node_and_aggressor():
    adv = live_gto_advice(_vs_3bet_hand(), 0, mode="cash")
    assert adv.scenario_key == "vs 3-bet", adv.scenario_key
    assert adv.vs_position == "SB", adv.vs_position
    # Görüntü etiketi de 3-bet'çiyi gösterir
    assert "3-bet" in adv.scenario and "SB" in adv.scenario


def test_rfi_node_when_first_to_act():
    h = _vs_3bet_hand()
    h.actions = []            # kimse açmadı → hero ilk konuşan
    h.current_bet = 1.0
    h.players[1].current_bet = 1.0
    adv = live_gto_advice(h, 0, mode="cash")
    assert adv.scenario_key == "RFI", adv.scenario_key


def _qapp():
    from app.main import prepare_qt_platform_plugins
    prepare_qt_platform_plugins()
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_matrix_set_action_range_reflects_scenario():
    """Matris widget'ı vs-3bet node'unu RFI'dan FARKLI renklendirir (in_range)."""
    from app.ui.components.gto_range_widget import _HandMatrixWidget
    _qapp()
    m = _HandMatrixWidget()
    m.set_action_range("MP", 107.0, mode="cash", scenario="RFI")
    rfi_in = set(m._in_range)
    m.set_action_range("MP", 107.0, mode="cash", scenario="vs 3-bet",
                       vs_position="SB")
    v3_in = set(m._in_range)
    assert rfi_in != v3_in, "matris vs-3bet'te RFI ile aynı kaldı (dinamik değil)"


def test_engine_range_differs_rfi_vs_3bet():
    """Matrisin gerçekten DEĞİŞTİĞİNİ kanıtla: en az bir el RFI≠vs-3bet."""
    from app.poker.gto_ranges import get_action
    diff = False
    for hk in ("AJs", "99", "KQs", "ATs", "TT", "AQo"):
        rfi = get_action("MP", hk, scenario="RFI", stack_depth=100, mode="cash")
        v3 = get_action("MP", hk, scenario="vs 3-bet", stack_depth=100,
                        mode="cash", vs_position="SB")
        if (round(rfi.get("raise", 0)), round(rfi.get("call", 0)),
                round(rfi.get("fold", 0))) != (
                round(v3.get("raise", 0)), round(v3.get("call", 0)),
                round(v3.get("fold", 0))):
            diff = True
            break
    assert diff, "vs-3bet range RFI ile aynı çıktı — node dinamik değil"
