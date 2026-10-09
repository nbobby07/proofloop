"""Deterministic evidence identity and briefing text; no AI-derived verdicts."""

import hashlib
import json

from backend.api.schemas import ReportResponse

TERMINAL = {"verified", "rejected", "inconclusive", "error"}


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
    report = require_execution_report(report)
    outcomes = {
        "verified": "The independent verifier reported verified for the executed suite.",
        "rejected": "The independent verifier rejected the remediation.",
        "inconclusive": "Verification is inconclusive because required evidence is incomplete.",
        "error": "The run ended with an execution error. No passing verdict is established.",
    }
    parts = [
        f"ProofLoop incident briefing. Run {report.run_id}.",
        "Saved report summary:",
        report.summary,
        outcomes[report.status],
    ]
    if report.verification:
        result = report.verification
        for name in ("security", "functional", "adversarial"):
            parts.append(
                f"{name.capitalize()} checks: {getattr(result, name + '_passed')} "
                f"reported passing out of {getattr(result, name + '_total')} total."
            )
    else:
        parts.append("The saved report supplies no verification counts.")
    # API v1 has no structured baseline/patch/challenge details in ReportResponse.
    parts.append("Detailed reproduction and patch claims are limited to the saved summary.")
    parts.append(
        "Limitations: "
        + (
            " ".join(report.limitations)
            if report.limitations
            else "No specific limitations were supplied in this report."
        )
    )
    parts.append("Passing the executed suite does not prove universal security.")
    return " ".join(parts)
