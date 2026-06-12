"""Tavla doubling-cube ↔ ICM (D191) — stage-aware jam/call range çarpanı + take-point."""
from app.poker.icm import cube_pressure_factor, cube_take_point
from app.poker.soyrac_advisor import soyrac_advice


def test_cube_factor_bubble_matches_old_flat():
    # Eski sabit 0.82 = bubble (stack-pressure yokken) — geri-uyum.
    assert abs(cube_pressure_factor("bubble", 15, 15) - 0.82) < 0.01


def test_cube_factor_monotonic_tightening():
    # Stage riski arttıkça çarpan DÜŞER (range daralır).
    chip = cube_pressure_factor("chipEV", 15, 15)
    bub = cube_pressure_factor("bubble", 15, 15)
    ft = cube_pressure_factor("final table", 15, 15)
    sat = cube_pressure_factor("satellite", 15, 15)
    assert chip >= bub >= ft >= sat
    assert chip >= 0.99 and sat < 0.7


def test_cube_factor_short_stack_extra_pressure():
    # Avg altı kısa stack ek baskı → daha sıkı.
    full = cube_pressure_factor("bubble", 20, 20)
    short = cube_pressure_factor("bubble", 8, 20)
    assert short < full


def test_cube_take_point_rises_with_pressure():
    assert cube_take_point("chipEV", 15, 15) < cube_take_point("bubble", 15, 15)
    assert cube_take_point("satellite", 12, 20) >= 0.50


def test_advice_stage_tightens_marginal_jam():
    # Marjinal jam: satellite bubble'dan daha sıkı (eşik yükselir / JAM→FOLD).
    bub = soyrac_advice("K8s", "BTN", "push", stack_bb=11, icm=True,
                        stage="bubble", avg_stack_bb=20)
    sat = soyrac_advice("K8s", "BTN", "push", stack_bb=11, icm=True,
                        stage="satellite", avg_stack_bb=20)
    assert sat["threshold"] >= bub["threshold"]


def test_advice_premium_jam_unaffected_by_stage():
    for stage in ("bubble", "final table", "satellite"):
        assert soyrac_advice("AA", "BTN", "push", stack_bb=11, icm=True,
                             stage=stage)["action"] == "JAM"


def test_advice_backward_compat_default_stage():
    # stage verilmezse icm=True eski bubble (0.82) davranışı — regresyon yok.
    a = soyrac_advice("K8s", "BTN", "push", stack_bb=11, icm=True)
    b = soyrac_advice("K8s", "BTN", "push", stack_bb=11, icm=True, stage="bubble")
    assert a["action"] == b["action"] and a["threshold"] == b["threshold"]
