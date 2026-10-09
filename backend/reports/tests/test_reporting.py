import hashlib
import io
import json
from email.message import Message
from unittest.mock import Mock

import pytest

from backend.api.schemas import ReportResponse, VerificationSummary
from backend.reports.evidence import briefing_script, report_digest
from backend.reports.narrator import ElevenLabsClient, NarrationConfig, NarrationUnavailable


def report(source="execution", status="verified", summary="Recorded unit evidence"):
    return ReportResponse(
        run_id="run_unit",
        source=source,
        status=status,
        summary=summary,
        limitations=["Unit input; no security execution"],
    )


@pytest.mark.parametrize("source,status", [("fixture", "verified"), ("execution", "verifying")])
def test_narration_rejects_fixture_and_unfinished_reports_before_network(tmp_path, source, status):
    client = ElevenLabsClient(NarrationConfig("unit-key", "unit-voice"), tmp_path)
    with pytest.raises(ValueError):
        client.generate_incident_briefing(report(source, status))
    assert list(tmp_path.iterdir()) == []


def test_export_is_explicit_and_credentials_are_not_repr_visible(tmp_path):
    config = NarrationConfig("private-key", "voice")
    assert "private-key" not in repr(config)
    with pytest.raises(NarrationUnavailable, match="not enabled"):
        ElevenLabsClient(config, tmp_path).generate_incident_briefing(report())


def test_report_identity_changes_with_evidence_and_script_points_to_written_limits():
    original = report()
    assert report_digest(original) != report_digest(report(summary="Different recorded evidence"))
    script = briefing_script(original)
    assert "additional limitations" in script
    assert "check counts are unavailable" in script
    assert "does not prove universal security" in script


@pytest.mark.parametrize("status", ["verified", "rejected", "inconclusive", "error"])
def test_spoken_summary_is_short_and_never_reads_technical_identifiers(status):
    digest = "a1" * 32
    original = report(status=status, summary=f"Run run_{digest}. Patch SHA256 {digest}.")
    original.run_id = f"run_{digest}"
    original.limitations = [f"See artifact_{digest} for restricted scope."]
    original.verification = VerificationSummary(
        security_passed=6,
        security_total=6,
        functional_passed=22,
        functional_total=22,
        adversarial_passed=16,
        adversarial_total=16,
    )
    before = original.model_dump()
    script = briefing_script(original)
    assert digest not in script
    assert "run_" not in script and "SHA256" not in script and "artifact_" not in script
    assert len(script.split()) <= 80
    assert original.model_dump() == before
    if status == "verified":
        assert (
            "All 44 recorded checks passed: 6 security, 22 functional, and 16 adversarial" in script
        )
    else:
        assert "All 44" not in script
        assert "patch passed" not in script
    if status in {"inconclusive", "error"}:
        assert "do not establish a successful result" in script


def test_rejected_summary_keeps_partial_counts_without_calling_unpassed_checks_failed():
    original = report(status="rejected")
    original.verification = VerificationSummary(
        security_passed=0,
        security_total=6,
        functional_passed=16,
        functional_total=22,
        adversarial_passed=15,
        adversarial_total=16,
    )
    script = briefing_script(original)
    assert "31 passing checks out of 44 required" in script
    assert "did not pass independent verification" in script
    assert "Inspect the failed checks" in script


def test_new_script_cannot_reuse_verbose_audio_cache(tmp_path):
    client = ElevenLabsClient(NarrationConfig("unit-key", "voice"), tmp_path)
    original = report()
    old_identity = json.dumps(
        [report_digest(original), "voice", "eleven_multilingual_v2", "script-v1"]
    )
    old_artifact = "briefing_" + hashlib.sha256(old_identity.encode()).hexdigest()
    assert client.identity(original) != old_artifact


def test_audio_cache_is_evidence_bound_and_integrity_checked(tmp_path, monkeypatch):
    calls = []

    def open_audio(request, timeout):
        calls.append(request)
        response = io.BytesIO(b"ID3-unit-audio")
        response.headers = Message()
        response.headers["Content-Type"] = "audio/mpeg"
        return response

    monkeypatch.setattr(
        "backend.reports.narrator.build_opener", lambda *args: Mock(open=open_audio)
    )
    client = ElevenLabsClient(
        NarrationConfig("unit-key", "voice"), tmp_path, approved_for_export=True
    )
    first = client.generate_incident_briefing(report())
    assert client.generate_incident_briefing(report()).artifact_id == first.artifact_id
    assert len(calls) == 1
    audio_path, _ = client.artifact_paths(first.artifact_id)
    audio_path.write_bytes(b"corrupt")
    client.generate_incident_briefing(report())
    assert len(calls) == 2
    other = client.generate_incident_briefing(report(summary="Another saved report"))
    assert other.artifact_id != first.artifact_id


def test_audio_route_cannot_take_host_paths(tmp_path):
    client = ElevenLabsClient(NarrationConfig("unit-key", "voice"), tmp_path)
    with pytest.raises(ValueError, match="artifact id"):
        client.artifact_paths("../../private.env")
