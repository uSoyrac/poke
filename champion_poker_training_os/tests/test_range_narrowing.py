"""Bridge Negatif-Çıkarım Motoru (D190) — villain range'ini YAPMADIKLARINDAN daralt."""
from app.poker.range_narrowing import (
    narrow, starting_range, narrow_line, BUCKETS, NarrowResult)


def test_starting_open_vs_flat_caps_premium():
    # Açış range'i premium içerir; FLAT (3-bet yapmadı) premium'u büyük ölçüde siler.
    op = starting_range("CO", "open")
    fl = starting_range("CO", "call")
    assert op["premium"] >= 0.9
    assert fl["premium"] < 0.2          # flat = capped (3-bet'lerdi)


def test_starting_3bet_polarized():
    r = starting_range("BTN", "3bet")
    assert r["premium"] >= 0.9 and r["suited_ax"] >= 0.5   # value + blocker blöf
    assert r["broadway"] < 0.5                              # orta düşük (polarize)


def test_flat_then_check_is_capped():
    # CO açtı, 3-bet yedi+call etti, flop'u cbet etmedi → CAPPED
    r = narrow("CO", [("preflop", "facing_3bet", "call"),
                      ("flop", "aggressor", "check")], first_action="open")
    assert r.shape == "capped"
    assert r.buckets["premium"] < 0.2
    assert any("3-bet YAPMADI" in c for c in r.chain)
    assert any("CBET ETMEDİ" in c for c in r.chain)


def test_check_raise_is_polarized():
    r = narrow("BB", [("flop", "caller", "check_raise")], first_action="call")
    assert r.shape in ("polarized", "strong")
    assert any("check-raise" in c.lower() for c in r.chain)


def test_triple_barrel_polarized():
    r = narrow("BTN", [("flop", "aggressor", "bet"), ("turn", "aggressor", "barrel"),
                       ("river", "aggressor", "bet")], first_action="3bet")
    assert r.shape == "polarized"


def test_give_up_barrel_weak():
    # cbet sonra turn check (barrel etmedi) → güçlü value düşer
    r = narrow("UTG", [("flop", "aggressor", "bet"),
                       ("turn", "aggressor", "check")], first_action="open")
    assert r.shape in ("weak", "capped")


def test_chain_and_summary_present():
    r = narrow("CO", [("preflop", "facing_3bet", "call")], first_action="open")
    assert isinstance(r, NarrowResult)
    assert len(r.chain) >= 2 and r.summary
    assert r.shape in ("capped", "polarized", "strong", "wide", "weak")


def test_narrow_line_string():
    s = narrow_line("BB", [("flop", "caller", "check_raise")], first_action="call")
    assert "→" in s and "POLARİZE" in s.upper()


def test_buckets_complete():
    r = narrow("BTN", [], first_action="open")
    assert set(r.buckets.keys()) == set(BUCKETS)
