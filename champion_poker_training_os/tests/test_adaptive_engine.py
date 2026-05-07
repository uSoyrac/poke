"""Tests for AdaptiveEngine and SolverLibrary."""
from __future__ import annotations

from app.solver.csv_importer import SolverLibrary, parse_solver_csv
from app.training.adaptive_engine import (
    SECONDS_PER_DAY,
    SR_INTERVALS_DAYS,
    AdaptiveEngine,
    SpotState,
)


# --- Adaptive Engine ---------------------------------------------------------

def test_correct_answer_promotes_interval():
    e = AdaptiveEngine()
    e._now = 1000.0
    state = e.record_attempt("S1", correct=True, ev_loss=0.0)
    assert state.interval_idx == 1
    assert state.correct_streak == 1
    assert state.next_due_ts == 1000.0 + SR_INTERVALS_DAYS[1] * SECONDS_PER_DAY


def test_incorrect_answer_demotes_and_queues_mistake():
    e = AdaptiveEngine()
    e._now = 1000.0
    # Build up some streak first
    for _ in range(3):
        e.record_attempt("S1", correct=True, ev_loss=0.0)
    pre = e.spots["S1"].interval_idx
    state = e.record_attempt("S1", correct=False, ev_loss=0.8)
    assert state.interval_idx <= max(0, pre - 2)
    assert "S1" in e.mistake_queue
    assert state.correct_streak == 0


def test_low_ev_loss_does_not_queue_mistake():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=False, ev_loss=0.05)
    assert "S1" not in e.mistake_queue


def test_mistake_queue_returns_first_when_in_candidates():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=False, ev_loss=0.9)
    e.record_attempt("S2", correct=False, ev_loss=0.9)
    # Most recent miss surfaces first (insert(0))
    nxt = e.next_drill(["S1", "S2", "S3"])
    assert nxt == "S2"


def test_correct_streak_two_clears_from_mistake_queue():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=False, ev_loss=0.9)
    assert "S1" in e.mistake_queue
    e.record_attempt("S1", correct=True, ev_loss=0.0)
    e.record_attempt("S1", correct=True, ev_loss=0.0)
    assert "S1" not in e.mistake_queue


def test_due_for_review_chosen_over_unseen():
    e = AdaptiveEngine()
    e._now = 1000.0
    # S1 attempted long ago and now due
    e.record_attempt("S1", correct=True, ev_loss=0.0)
    e._now = 1000.0 + SR_INTERVALS_DAYS[1] * SECONDS_PER_DAY + 10
    nxt = e.next_drill(["S1", "S99"])  # S99 unseen, S1 due
    assert nxt == "S1"


def test_unseen_returned_when_nothing_due():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=True, ev_loss=0.0)
    nxt = e.next_drill(["S1", "S99"])  # S1 just attempted, not due yet
    assert nxt == "S99"


def test_weakness_summary_ranks_by_rolling_ev_loss():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=False, ev_loss=0.4)
    e.record_attempt("S2", correct=False, ev_loss=1.2)
    e.record_attempt("S3", correct=True, ev_loss=0.0)
    summary = e.weakness_summary(top_n=3)
    assert summary[0]["spot_id"] == "S2"  # worst rolling EV loss
    assert summary[0]["rolling_ev_loss"] >= summary[1]["rolling_ev_loss"]


def test_queue_size_metrics():
    e = AdaptiveEngine()
    e._now = 1000.0
    e.record_attempt("S1", correct=False, ev_loss=0.9)
    sizes = e.queue_size()
    assert sizes["tracked"] == 1
    assert sizes["mistakes_pending"] == 1


# --- Solver CSV Importer -----------------------------------------------------

SAMPLE_CSV = """spot_id,action,frequency,ev,sizing,best,source
SPOT-001,fold,0.05,0.0,,0,GTO
SPOT-001,check,0.40,1.10,,0,GTO
SPOT-001,bet small,0.45,1.32,33% pot,1,GTO
SPOT-001,bet medium,0.10,1.18,66% pot,0,GTO
SPOT-002,fold,0.65,0.0,,1,GTO
SPOT-002,call,0.30,-0.18,,0,GTO
SPOT-002,raise,0.05,-0.42,2.4x,0,GTO
"""

PERCENTAGE_CSV = """spot_id,action,frequency,ev
SPOT-X,check,55,0.95
SPOT-X,bet,45,1.30
"""


def test_parse_solver_csv_basic():
    parsed = parse_solver_csv(SAMPLE_CSV)
    assert "SPOT-001" in parsed and "SPOT-002" in parsed
    s1 = parsed["SPOT-001"]
    assert s1.best_action == "bet small"
    assert all(0 <= a.frequency <= 1 for a in s1.actions)
    # Frequencies normalised
    assert abs(sum(a.frequency for a in s1.actions) - 1.0) < 0.01


def test_parse_solver_csv_handles_percentages():
    parsed = parse_solver_csv(PERCENTAGE_CSV)
    assert "SPOT-X" in parsed
    s = parsed["SPOT-X"]
    assert abs(sum(a.frequency for a in s.actions) - 1.0) < 0.01


def test_parse_solver_csv_picks_highest_ev_when_no_best_flag():
    csv = "spot_id,action,frequency,ev\nA,fold,0.5,0.0\nA,call,0.5,0.85\n"
    parsed = parse_solver_csv(csv)
    assert parsed["A"].best_action == "call"


def test_parse_solver_csv_empty_and_garbage():
    assert parse_solver_csv("") == {}
    assert parse_solver_csv("not,a,csv") == {}
    assert parse_solver_csv("only,a,header,row") == {}


def test_solver_library_import_replaces_results():
    lib = SolverLibrary()
    lib.import_csv_text(SAMPLE_CSV, source_name="GTO Wizard")
    assert lib.size() == 2
    assert lib.has("SPOT-001")
    assert "GTO Wizard" in lib.sources()
    lib.clear()
    assert lib.size() == 0
