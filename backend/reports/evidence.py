"""Deterministic evidence identity and briefing text; no AI-derived verdicts."""

import hashlib
import json

from backend.api.schemas import ReportResponse

TERMINAL = {"verified", "rejected", "inconclusive", "error"}
SCRIPT_VERSION = "v2"
DEFAULT_LIMITATION = "Results cover only the frozen executed suites; not universal security."


def require_execution_report(report: ReportResponse) -> ReportResponse:
    report = ReportResponse.model_validate(report)
    if report.source != "execution" or report.status not in TERMINAL:
        raise ValueError("Only completed execution reports may be exported.")
    return report


def report_digest(report: ReportResponse) -> str:
    payload = json.dumps(
        report.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def briefing_script(report: ReportResponse) -> str:
    """A spoken decision summary; technical identities stay in the written report."""
    report = require_execution_report(report)
    outcomes = {
        "verified": "The patch passed independent verification.",
        "rejected": "The patch did not pass independent verification.",
        "inconclusive": "Verification is incomplete. There is not enough evidence for a verdict.",
        "error": "An execution error interrupted verification. No passing result was established.",
    }
    parts = [outcomes[report.status]]
    if report.verification:
        result = report.verification
        categories = ("security", "functional", "adversarial")
        passed = sum(getattr(result, name + "_passed") for name in categories)
        total = sum(getattr(result, name + "_total") for name in categories)
        if report.status == "verified" and total > 0 and passed == total:
            parts.append(
                f"All {total} recorded checks passed: {result.security_passed} security, "
                f"{result.functional_passed} functional, "
                f"and {result.adversarial_passed} adversarial."
            )
        elif total > 0:
            parts.append(f"The report records {passed} passing checks out of {total} required.")
            if report.status in {"inconclusive", "error"}:
                parts.append("Those counts do not establish a successful result.")
        else:
            parts.append("No check results are available in this report.")
    else:
        parts.append("Detailed check counts are unavailable in this report.")
    # Never read raw summary/limitations/IDs: these may contain hashes, paths or error codes.
    # The complete report stays unchanged and remains the authoritative detailed record.
    parts.append("Passing these checks does not prove universal security.")
    if any(limit.strip() != DEFAULT_LIMITATION for limit in report.limitations):
        parts.append("Review the written report for additional limitations before relying on it.")
    actions = {
        "verified": "You can inspect the evidence or run another challenge.",
        "rejected": "Inspect the failed checks before accepting this fix.",
        "inconclusive": "Review the missing evidence before trying again.",
        "error": "Check the audit trail for the cause before trying again.",
    }
    parts.append(actions[report.status])
    return " ".join(parts)
