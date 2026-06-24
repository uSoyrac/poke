"""D-A (SAYIM-MVP çekirdek read_count): tip-prior + gözlenen dizi → tek-sayı R.
READ-GATED identity + prior-tek-başına-sapma-yok (bot fidelity güvenliği)."""
from app.poker.opponent_typology import HELLMUTH_PRIOR, type_prior
from app.poker.range_narrowing import narrow
from app.poker.read_count import read_count


def test_prior_table():
    assert type_prior("elephant") == 1 and type_prior("mouse") == 1 and type_prior("eagle") == 1
    assert type_prior("lion") == 0 and type_prior("jackal") == -1
    assert type_prior(None) == 0 and type_prior("unknown") == 0
    assert all(-1 <= v <= 1 for v in HELLMUTH_PRIOR.values()), "prior ±1 cap"


def test_identity_no_villain_no_events():
    """READ-GATED: villain yok + dizi yok → R=0, low güven, GTO (bot identity korunur)."""
    rc = read_count(None, [])
    assert rc.R == 0 and rc.confidence == "low" and "GTO" in rc.deviation


def test_prior_alone_no_deviation():
    """Prior TEK BAŞINA (±1) asla sapma açmaz — gözlenen dizi şart."""
    for t in ("elephant", "mouse", "eagle", "jackal"):
        rc = read_count(t, [])           # dizi yok
        assert abs(rc.R) < 2 and "GTO" in rc.deviation, f"{t} prior-tek-başına sapma açmamalı"
        assert rc.confidence == "low"


def test_sequence_opens_value_deviation():
    """Gözlenen dizi (check-raise +2, prior=0 lion) → high güven + value-sapma."""
    rc = read_count("lion", [("flop", "caller", "check_raise")], first_action="open")
    assert rc.R >= 2 and rc.confidence == "high" and "VALUE" in rc.deviation


def test_capped_sequence():
    """flat (−2, prior=0 lion) → capped sapma (R≤−2)."""
    rc = read_count("lion", [("preflop", "facing_raise", "call")], first_action="flat")
    assert rc.R <= -2 and "CAPPED" in rc.deviation and rc.confidence == "high"


def test_scale_single_source():
    """read_count R'si = prior + motor running_count (panel=insan=motor TEK ölçek)."""
    evs = [("flop", "caller", "check_raise")]
    nr = narrow("BTN", evs, "open")
    rc = read_count("jackal", evs, first_action="open")
    assert rc.R == type_prior("jackal") + nr.running_count
    assert rc.steps == list(nr.rc_steps)
