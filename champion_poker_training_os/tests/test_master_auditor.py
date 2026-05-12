"""MasterAuditorAgent — end-to-end coverage agent."""
from __future__ import annotations

from app.agents import AuditReport, CheckResult, MasterAuditorAgent


def test_master_auditor_runs_all_checks():
    auditor = MasterAuditorAgent()
    result = auditor.run()
    assert "report" in result.data
    report = result.data["report"]
    assert isinstance(report, AuditReport)
    # We expect 9 distinct checks at minimum
    assert len(report.checks) >= 9


def test_audit_passes_in_clean_repo():
    result = MasterAuditorAgent().run()
    report = result.data["report"]
    assert report.failed == 0, f"Audit failures:\n{report.to_markdown()}"


def test_audit_check_result_dataclass():
    cr = CheckResult(name="x", passed=True, detail="ok")
    assert cr.name == "x"
    assert cr.passed
    assert cr.samples == []


def test_audit_markdown_export_includes_status():
    result = MasterAuditorAgent().run()
    md = result.data["markdown"]
    assert "Master Audit Report" in md
    assert "Status:" in md
    assert "Checks" in md


def test_audit_summary_describes_outcome():
    result = MasterAuditorAgent().run()
    assert "Audit:" in result.summary
    assert "passed" in result.summary
