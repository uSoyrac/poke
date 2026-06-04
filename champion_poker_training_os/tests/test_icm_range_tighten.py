"""ICM range tightening katmanı (Parça 2 — ölçülü).

Bubble/FT'de marjinal call'lar fold'a kayar (call-off range daralır). KRİTİK
INVARIANT: risk_premium=0 (cash/early/chipEV) → KİMLİK → base chip-EV GTO
değişmez → gto_accuracy korunur. Value-raise ve push/fold (allin) dokunulmaz.
"""
from __future__ import annotations

from app.poker.icm import icm_tighten, risk_premium


def test_identity_at_zero_risk_premium():
    f = {"raise": 30, "call": 40, "fold": 30}
    out = icm_tighten(f, 0.0)
    assert out == {"raise": 30.0, "call": 40.0, "fold": 30.0, "allin": 0.0}


def test_moves_marginal_call_to_fold():
    f = {"raise": 20, "call": 50, "fold": 30}
    out = icm_tighten(f, 0.12)            # shift = min(0.5, 0.30) = 0.30
    assert abs(out["call"] - 35.0) < 1e-9      # 50 * 0.70
    assert abs(out["fold"] - 45.0) < 1e-9      # 30 + 15
    assert out["raise"] == 20.0                # value-raise dokunulmaz
    assert abs(sum(v for k, v in out.items() if k != "allin") - 100) < 1e-9


def test_shift_is_capped_moderate():
    out = icm_tighten({"raise": 0, "call": 100, "fold": 0}, 1.0)
    assert out["call"] == 50.0 and out["fold"] == 50.0   # shift cap 0.5


def test_pushfold_allin_untouched():
    out = icm_tighten({"raise": 0, "call": 0, "fold": 40, "allin": 60}, 0.2)
    assert out["allin"] == 60.0 and out["fold"] == 40.0


def test_risk_premium_zero_for_chipev_gates_icm():
    assert risk_premium(50, 50, "chipEV") == 0.0     # early/chipEV → ICM kapalı
    assert risk_premium(20, 40, "bubble") > 0        # bubble + kısa stack → açık
    assert risk_premium(20, 40, "final table") > risk_premium(20, 40, "bubble")
