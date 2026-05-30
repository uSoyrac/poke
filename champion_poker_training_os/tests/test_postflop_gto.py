"""Board-texture-aware postflop GTO beyni (Phase D3) testleri."""
from __future__ import annotations

from app.engine.hand_state import Card
from app.poker.postflop_gto import (
    classify_board, cbet_strategy, defend_strategy,
)


def _b(*codes) -> list:
    return [Card(c[0], c[1]) for c in codes]


# ── Board classification ──────────────────────────────────────────────
def test_dry_high_board():
    tex = classify_board(_b("Ac", "7d", "2h"))
    assert not tex.paired and not tex.monotone
    assert tex.wetness <= 0.35
    assert tex.label in ("dry", "semi-wet")
    assert tex.high_card == 12   # Ace


def test_wet_monotone_connected():
    tex = classify_board(_b("9s", "8s", "7s"))
    assert tex.monotone and tex.connected
    assert tex.wetness >= 0.7


def test_paired_board():
    tex = classify_board(_b("Kc", "Kd", "5h"))
    assert tex.paired and tex.label == "paired"


def test_two_tone_flag():
    tex = classify_board(_b("Ah", "Kh", "4c"))
    assert tex.two_tone and not tex.monotone


# ── C-bet strategy ────────────────────────────────────────────────────
def test_dry_board_high_cbet_small_size():
    tex = classify_board(_b("Ac", "7d", "2h"))
    freq, size = cbet_strategy(0.55, tex, in_position=True, has_initiative=True)
    assert freq >= 0.45            # range avantajı → yüksek c-bet
    assert size <= 0.4             # küçük size


def test_wet_board_lower_cbet_bigger_size():
    tex = classify_board(_b("9s", "8s", "7s"))
    freq, size = cbet_strategy(0.55, tex, in_position=True, has_initiative=True)
    assert size >= 0.6             # büyük/polarize size
    dry = classify_board(_b("Ac", "7d", "2h"))
    dry_freq, _ = cbet_strategy(0.55, dry, in_position=True, has_initiative=True)
    assert freq < dry_freq         # ıslakta daha az c-bet


def test_oop_checks_more_than_ip():
    tex = classify_board(_b("Ac", "7d", "2h"))
    ip, _ = cbet_strategy(0.40, tex, in_position=True, has_initiative=True)
    oop, _ = cbet_strategy(0.40, tex, in_position=False, has_initiative=True)
    assert oop < ip


def test_no_initiative_rarely_leads():
    tex = classify_board(_b("Ac", "7d", "2h"))
    with_init, _ = cbet_strategy(0.40, tex, in_position=True, has_initiative=True)
    no_init, _ = cbet_strategy(0.40, tex, in_position=True, has_initiative=False)
    assert no_init < with_init


def test_value_equity_bets_most():
    tex = classify_board(_b("Ac", "7d", "2h"))
    val, _ = cbet_strategy(0.80, tex, in_position=True, has_initiative=True)
    mid, _ = cbet_strategy(0.45, tex, in_position=True, has_initiative=True)
    assert val > mid               # value > showdown-value check region


# ── Defend strategy ───────────────────────────────────────────────────
def test_high_equity_raises():
    tex = classify_board(_b("Ac", "7d", "2h"))
    fold, call, raise_ = defend_strategy(0.82, tex, pot=10, to_call=5)
    assert raise_ > 0.2
    assert abs(fold + call + raise_ - 1.0) < 0.02


def test_low_equity_folds_when_priced_out():
    tex = classify_board(_b("Ac", "7d", "2h"))   # dry → few draws
    fold, call, raise_ = defend_strategy(0.12, tex, pot=10, to_call=9)
    assert fold >= 0.5


def test_wet_board_more_semibluff_raises_than_dry():
    wet = classify_board(_b("9s", "8s", "7s"))
    dry = classify_board(_b("Ac", "7d", "2h"))
    _, _, r_wet = defend_strategy(0.30, wet, pot=10, to_call=5)
    _, _, r_dry = defend_strategy(0.30, dry, pot=10, to_call=5)
    assert r_wet >= r_dry


def test_frequencies_sum_to_one():
    tex = classify_board(_b("Kc", "Kd", "5h"))
    for eq in (0.1, 0.3, 0.5, 0.7, 0.9):
        f, c, r = defend_strategy(eq, tex, pot=8, to_call=4)
        assert abs(f + c + r - 1.0) < 0.02


# ── Street barrel decay + multiway (D3+) ──────────────────────────────
def test_river_barrels_less_than_flop():
    tex = classify_board(_b("Ac", "7d", "2h"))
    flop, _ = cbet_strategy(0.40, tex, True, True, street="flop")
    river, _ = cbet_strategy(0.40, tex, True, True, street="river")
    assert river < flop


def test_later_street_bigger_size():
    tex = classify_board(_b("9s", "8s", "7s"))
    _, flop_sz = cbet_strategy(0.7, tex, True, True, street="flop")
    _, river_sz = cbet_strategy(0.7, tex, True, True, street="river")
    assert river_sz > flop_sz


def test_multiway_cbets_less():
    tex = classify_board(_b("Ac", "7d", "2h"))
    hu, _ = cbet_strategy(0.45, tex, True, True, n_active=2)
    mw, _ = cbet_strategy(0.45, tex, True, True, n_active=4)
    assert mw < hu


def test_multiway_defends_tighter():
    tex = classify_board(_b("Ac", "7d", "2h"))
    f_hu, _, _ = defend_strategy(0.30, tex, pot=10, to_call=5, n_active=2)
    f_mw, _, _ = defend_strategy(0.30, tex, pot=10, to_call=5, n_active=4)
    assert f_mw > f_hu


def test_defaults_unchanged_flop_headsup():
    # Varsayılan (flop, 2 oyuncu) D3 davranışını korumalı
    tex = classify_board(_b("Ac", "7d", "2h"))
    a, _ = cbet_strategy(0.55, tex, True, True)
    b, _ = cbet_strategy(0.55, tex, True, True, street="flop", n_active=2)
    assert abs(a - b) < 1e-9
