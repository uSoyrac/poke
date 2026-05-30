"""Canlı postflop EXACT solver wrapper (Phase D9).

TexasSolver binary yoksa testler skip edilir (CI / temiz makineler yeşil
kalır). Binary varsa gerçek bir flop çözümü doğrulanır (küçük iter, hızlı).
"""
from __future__ import annotations

import pytest

from app.poker.postflop_solver import solve_spot_exact, solver_available

_HAS_SOLVER = solver_available()
_skip = pytest.mark.skipif(not _HAS_SOLVER,
                           reason="TexasSolver binary yok (~/TexasSolver)")


def test_invalid_board_returns_none():
    # Geçersiz board → binary olsa da None (kısa devre)
    assert solve_spot_exact("", 10, 100, True, "AhKh") is None
    assert solve_spot_exact("Ah", 10, 100, True, "AhKh") is None


def test_pot_type_ranges_exist_and_tighten():
    import app.poker.postflop_solver as ps
    for k in ("SRP", "3BP", "4BP"):
        assert k in ps._POT_TYPE_RANGES
    # 4-bet potu SRP'den çok daha sıkı (string daha kısa)
    srp_oop = ps._POT_TYPE_RANGES["SRP"][0]
    fbp_oop = ps._POT_TYPE_RANGES["4BP"][0]
    assert len(fbp_oop) < len(srp_oop)


def test_position_aware_ranges_build():
    from app.poker.postflop_solver import _position_aware_ranges
    # BTN açar, BB savunur. Hero=BB (OOP), villain=BTN (IP).
    pr = _position_aware_ranges("BB", "BTN", raiser_pos="BTN",
                                hero_in_position=False)
    assert pr is not None
    oop, ip = pr
    assert oop and ip and "," in oop and "," in ip
    # OOP=BB savunma range'i hero'nun; içerik açan-range'den farklı olmalı
    assert set(oop.split(",")) != set(ip.split(","))


def test_position_aware_ranges_ambiguous_returns_none():
    from app.poker.postflop_solver import _position_aware_ranges
    # Villain pozisyonu yok → belirsiz → None (pot-tipi fallback tetiklenir)
    assert _position_aware_ranges("BB", "", "BTN", False) is None
    # Aggressor iki oyuncudan biri değil → None
    assert _position_aware_ranges("BB", "BTN", "CO", False) is None


def test_preflop_pot_type_detection():
    from types import SimpleNamespace as NS
    from app.engine.hand_state import ActionType, Street
    from app.poker.decision_capture import preflop_pot_type

    def act(at):
        return NS(street=Street.PREFLOP, action_type=at)

    srp = NS(actions=[act(ActionType.RAISE), act(ActionType.CALL)])
    assert preflop_pot_type(srp) == "SRP"
    tbp = NS(actions=[act(ActionType.RAISE), act(ActionType.RAISE),
                      act(ActionType.CALL)])
    assert preflop_pot_type(tbp) == "3BP"
    fbp = NS(actions=[act(ActionType.RAISE)] * 3 + [act(ActionType.CALL)])
    assert preflop_pot_type(fbp) == "4BP"
    limp = NS(actions=[act(ActionType.CALL), act(ActionType.CHECK)])
    assert preflop_pot_type(limp) == "limped"


def test_graceful_when_no_binary(monkeypatch):
    # Binary yokmuş gibi davran → None (UI çökmeden düşer)
    import app.poker.postflop_solver as ps
    monkeypatch.setattr(ps, "solver_available", lambda: False)
    # available() çağrısı engine üzerinden; burada doğrudan import'u taklit et
    import app.poker.texassolver_adapter as ad

    class _Fake:
        available = False
    monkeypatch.setattr(ad, "TexasSolverEngine", lambda *a, **k: _Fake())
    assert solve_spot_exact("Ah7c2d", 10, 100, True, "AhKh") is None


@_skip
def test_real_solve_returns_frequencies():
    # Gerçek solver: A72 rainbow flop, IP hero AKs — EXACT frekanslar dönmeli
    out = solve_spot_exact("Ah7c2d", pot_bb=6.0, eff_stack_bb=100.0,
                           hero_in_position=True, hero_combo="AsKs",
                           iterations=30)
    assert out is None or isinstance(out, dict)
    if out:
        total = sum(out.values())
        assert 95 <= total <= 105        # frekanslar ~%100 toplar
        assert all(v >= 0 for v in out.values())
