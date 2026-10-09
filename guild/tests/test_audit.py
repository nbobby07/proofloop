import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from backend.api.schemas import ReportResponse, SecurityEvent
from guild.client import GuildClient, GuildConfig, GuildUnavailable

SESSION = "12345678-1234-1234-1234-123456789012"


def packet():
    report = ReportResponse(
        run_id="run_unit",
        source="execution",
        status="verified",
        summary="Unit evidence",
        limitations=["Unit input; no security execution"],
    )
    event = SecurityEvent(
        event_id="event_unit",
        run_id="run_unit",
        source="execution",
        timestamp=datetime.now(UTC),
        stage="verified",
        event_type="run_completed",
        severity="info",
        message="Unit event",
        metadata={"secret": "private-key"},
    )
    return report, event


def client():
    return GuildClient(GuildConfig("unit:secret", "workspace", "agent"), approved_for_export=True)


def test_hosted_packet_excludes_arbitrary_metadata_and_declares_omitted_artifacts():
    adapter = client()
    adapter._request = Mock(return_value={"id": SESSION})
    report, event = packet()
    job = adapter.start_audit(report, [event])
    prompt = adapter._request.call_args.args[1]["initial_prompt"]
    assert "private-key" not in prompt
    assert "Artifact contents are not fetched" in prompt
    assert job.session_id == SESSION


def test_audit_cannot_export_mixed_fixture_events():
    adapter = client()
    adapter._request = Mock()
    report, event = packet()
    event = event.model_copy(update={"source": "fixture"})
    with pytest.raises(ValueError, match="match"):
        adapter.start_audit(report, [event])
    adapter._request.assert_not_called()


@pytest.mark.parametrize("citation", ["unknown_receipt", "event_unit"])
def test_hosted_output_is_bound_to_known_evidence(citation):
    adapter = client()
    adapter._request = Mock(return_value={"id": SESSION})
    report, event = packet()
    job = adapter.start_audit(report, [event])
    response = {
        "run_id": job.run_id,
        "evidence_digest": job.evidence_digest,
        "summary": "Advisory unit review",
        "supported_claims": [{"claim": "An event was supplied", "evidence_ids": [citation]}],
        "unsupported_claims": [],
        "missing_evidence": [],
        "limitations": [],
    }
    adapter._request.return_value = {
        "items": [
            {"id": SESSION, "type": "runtime_done", "content": {"text": json.dumps(response)}}
        ]
    }
    if citation == "unknown_receipt":
        with pytest.raises(GuildUnavailable, match="validation"):
            adapter.poll_audit(job)
    else:
        assert adapter.poll_audit(job).summary == "Advisory unit review"


def test_export_must_be_enabled_and_complete_key_remains_private():
    config = GuildConfig("unit:private-key", "workspace", "agent")
    assert "private-key" not in repr(config)
    adapter = GuildClient(config)
    report, event = packet()
    with pytest.raises(GuildUnavailable, match="not enabled"):
        adapter.start_audit(report, [event])
