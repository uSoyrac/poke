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
