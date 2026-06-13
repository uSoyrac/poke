"""SENARYO TESPİTİ güvencesi (D216) — koçun gerçek-oyunda DOĞRU senaryoyu seçtiğini
test eder. BUG (canlı yakalandı): BB 9.4bb raise yediği halde koç 'RFI' sanıp yanlış
eşik veriyordu (handoff _adv None → 'RFI' default). Bu test o regresyon'u yakalar.

ÖNCEKİ EKSİK: test_book_equation senaryo VERİLDİĞİNDE eşiği test ediyordu ama
senaryo-TESPİTİNİ (RFI mi vs-raise mi) hiç test etmiyordu. Bu onu kapatır.
"""
import types
import pytest
from app.engine.hand_state import Street, ActionType, card_from_str
from app.poker.soyrac_advisor import soyrac_advice


def _mk_hand(actions_seq, hero_idx, positions):
    """actions_seq: [(player_idx, ActionType)]; positions: {idx: 'SB'...}"""
    players = [types.SimpleNamespace(position=positions.get(i, "?")) for i in range(len(positions))]
    actions = [types.SimpleNamespace(street=Street.PREFLOP, action_type=at, player_idx=pid)
               for pid, at in actions_seq]
    return types.SimpleNamespace(players=players, actions=actions, hero_idx=hero_idx)


def test_count_raises_bb_vs_sb_open():
    """SB açtı, hero BB → 1 raise → vs RFI (RFI DEĞİL)."""
    from app.poker.gto_live_advice import _count_preflop_raises_before_hero
    hand = _mk_hand([(0, ActionType.RAISE)], hero_idx=2, positions={0: "SB", 1: "BTN", 2: "BB"})
    n, raiser = _count_preflop_raises_before_hero(hand, 2)
    assert n == 1, f"SB-açış → 1 raise beklenir, {n} çıktı"


def test_count_raises_bb_vs_3bet():
    """BTN açtı, SB 3-bet, hero BB → 2 raise → vs 3-bet."""
    from app.poker.gto_live_advice import _count_preflop_raises_before_hero
    hand = _mk_hand([(1, ActionType.RAISE), (0, ActionType.RAISE)], hero_idx=2,
                    positions={0: "SB", 1: "BTN", 2: "BB"})
    n, raiser = _count_preflop_raises_before_hero(hand, 2)
    assert n == 2, f"BTN-açış + SB-3bet → 2 raise beklenir, {n} çıktı"


@pytest.mark.parametrize("scenario", ["vs RFI", "vs 3-bet"])
def test_short_stack_facing_raise_not_rfi(scenario):
    """KRİTİK regresyon: kısa-stack (9.4bb) BB raise'e karşı → RFI-açış DEĞİL,
    Call-vs-Jam (Nash call-off) olmalı. Bug: RFI sanıp yanlış eşik veriyordu."""
    a = soyrac_advice("A4s", "BB", scenario=scenario, vs_position="SB",
                      stack_bb=9.4, tourney=True, n_active=12)
    assert a["scenario"] != "RFI", f"{scenario} spotu RFI'ye düşmemeli, {a['scenario']} çıktı"
    assert "Jam" in a["scenario"] or "vs" in a["scenario"].lower(), \
        f"facing-raise senaryosu bekleniyordu, {a['scenario']} çıktı"
    # A4s 9.4bb iyi fiyatta → CALL (atılmamalı)
    assert a["action"] == "CALL", f"A4s 9.4bb facing → CALL beklenir, {a['action']} çıktı"
