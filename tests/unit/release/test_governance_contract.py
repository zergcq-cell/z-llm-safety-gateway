"""Open-source governance contracts for the v0.1.1 release."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIVATE_REPORT_URL = "https://github.com/zergcq-cell/z-llm-safety-gateway/security/advisories/new"


def test_security_policy_defines_private_coordinated_disclosure() -> None:
    """TC-GOV-001: security policy covers support, privacy, and response timing."""
    policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for required in (
        PRIVATE_REPORT_URL,
        "Supported Versions",
        "3 business days",
        "7 business days",
        "coordinated disclosure",
    ):
        assert required in policy
    assert "Do not open a public issue" in policy
    assert "exploit" in policy.lower()


def test_code_of_conduct_is_complete_and_enforceable() -> None:
    """TC-GOV-002: Contributor Covenant includes scope and four enforcement levels."""
    conduct = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    for required in (
        "Contributor Covenant Code of Conduct",
        "Our Pledge",
        "Our Standards",
        "Enforcement Responsibilities",
        "Scope",
        "Enforcement Guidelines",
        "1. Correction",
        "2. Warning",
        "3. Temporary Ban",
        "4. Permanent Ban",
        "Private moderation contact requested",
    ):
        assert required in conduct
    assert PRIVATE_REPORT_URL not in conduct


def test_contribution_and_feedback_entry_points_are_consistent() -> None:
    """TC-GOV-003: contribution, templates, and feedback routes are linked."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for link in ("SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"):
        assert f"]({link})" in readme
    assert "https://github.com/zergcq-cell/z-llm-safety-gateway/issues/new/choose" in readme
    assert "](CODE_OF_CONDUCT.md)" in contributing

    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.md").is_file()
    assert (ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md").is_file()
    assert (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()
