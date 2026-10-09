import io
from email.message import Message
from unittest.mock import Mock

import pytest

from backend.api.schemas import ReportResponse
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


def test_report_identity_changes_with_evidence_and_script_preserves_limits():
    original = report()
    assert report_digest(original) != report_digest(report(summary="Different recorded evidence"))
    script = briefing_script(original)
    assert "Unit input; no security execution" in script
    assert "no verification counts" in script
    assert "does not prove universal security" in script


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
