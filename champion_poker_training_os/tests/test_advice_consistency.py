"""GTO advice TUTARLILIK guard'ı — header (live) ≠ reveal (snapshot) çelişkisini
kalıcı önler. Tek kaynak: live_gto_advice → decision_capture snapshot.

Bug (D111): hero açışa karşı raise edince header 'vs 3-bet→RAISE', reveal
'vs RFI→CALL' diyordu (hero'nun kendi raise'i sayılıyordu). Bu testler senaryo
+ aksiyonun tek kaynaktan gelip ayrışmadığını garanti eder.
"""
from __future__ import annotations

from app.engine.hand_state import (Action, ActionType, Card, HandState,
                                    PlayerSeat, Street)
from app.poker.decision_capture import make_snapshot
from app.poker.gto_live_advice import live_gto_advice


def _hj_faces_utg_open():
    """HJ KQo, UTG açtı — hero KARAR anında (henüz raise etmedi)."""
    h = HandState()
    h.big_blind = 1.0
    h.street = Street.PREFLOP
    h.current_bet = 3.0
    h.players = [
        PlayerSeat(name="hero", stack=94.0, position="HJ", is_hero=True,
                   current_bet=0.0, hole_cards=[Card("K", "d"), Card("Q", "h")]),
        PlayerSeat(name="utg", stack=97.0, position="UTG", current_bet=3.0),
    ]
    h.pot = 4.5
    h.actions = [Action(player_idx=1, action_type=ActionType.RAISE, amount=3.0,
                        street=Street.PREFLOP)]
    return h


def test_snapshot_scenario_equals_live_advice():
    """Reveal snapshot'ı ile canlı advice AYNI senaryoyu taşır (tek kaynak)."""
    h = _hj_faces_utg_open()
    adv = live_gto_advice(h, 0, mode="cash")
    snap = make_snapshot(h, 0, adv, bb=1.0)
    assert snap["scenario"] == adv.scenario     # ayrışamaz
    assert adv.scenario_key == "vs RFI"


def test_post_hero_raise_still_vs_rfi():
    """Hero raise ettikten SONRA da (header re-render) senaryo vs RFI kalır —
    'vs 3-bet'e KAYMAZ (D111 çelişki regresyonu)."""
    h = _hj_faces_utg_open()
    h.actions.append(Action(player_idx=0, action_type=ActionType.RAISE,
                            amount=9.0, street=Street.PREFLOP))
    h.players[0].current_bet = 9.0
    h.current_bet = 9.0
    adv = live_gto_advice(h, 0, mode="cash")
    assert adv.scenario_key == "vs RFI", adv.scenario_key
    # advice senaryoyla tutarlı: vs-RFI'da KQo agresif-raise baskın aksiyon değil
    assert adv.raise_ <= max(adv.call, adv.fold) + 1e-9


def test_pot_type_is_table_relative_not_hero():
    """pot_type masa-bazlı: hero raise edince 3BP olur (doğru — kim raise ederse).
    Senaryo (hero-bazlı) ise vs RFI kalır → ikisi farklı kavram, ikisi de doğru."""
    from app.poker.decision_capture import preflop_pot_type
    h = _hj_faces_utg_open()
    assert preflop_pot_type(h) == "SRP"          # tek açış
    h.actions.append(Action(player_idx=0, action_type=ActionType.RAISE,
                            amount=9.0, street=Street.PREFLOP))
    assert preflop_pot_type(h) == "3BP"          # iki raise → 3-bet potu (masa)
