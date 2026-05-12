"""UISimulationAgent — end-to-end UX walker tests."""
from __future__ import annotations

import os
import pytest

PYSIDE6 = pytest.importorskip("PySide6", reason="PySide6 not installed")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.agents import UIAuditReport, UIIssue, UISimulationAgent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_simulator_runs_without_crash(qapp):
    report = UISimulationAgent().run_full_audit()
    assert isinstance(report, UIAuditReport)


def test_simulator_finds_no_blockers_in_clean_repo(qapp):
    report = UISimulationAgent().run_full_audit()
    blockers = [i.detail for i in report.blockers]
    assert not blockers, f"UI blockers found: {blockers}"


def test_simulator_passes_minimum_count_of_checks(qapp):
    report = UISimulationAgent().run_full_audit()
    # At least 12 passing checks expected on a healthy build
    assert len(report.passed) >= 12, (
        f"Only {len(report.passed)} passed checks; report:\n{report.to_markdown()}"
    )


def test_simulator_markdown_export(qapp):
    report = UISimulationAgent().run_full_audit()
    md = report.to_markdown()
    assert "UI Simulation Report" in md
    assert "Status" in md


def test_ui_issue_dataclass_shape():
    issue = UIIssue(severity="high", screen="Test", detail="x", fix_hint="y")
    assert issue.severity == "high"
    assert issue.fix_hint == "y"
