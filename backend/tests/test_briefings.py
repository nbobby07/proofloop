"""Explicit fake narration transport; no live provider requests in tests."""

import asyncio
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.schemas import CreateRunRequest, RunStatus
from backend.engine.orchestrator import Orchestrator
from backend.reports.briefings import BriefingService, saved_report
from backend.reports.evidence import briefing_script, report_digest
from backend.reports.narrator import ElevenLabsClient, NarrationConfig
from backend.storage.runs import RunStore
from backend.tests.test_orchestrator import UnitTestEngine, settle


class FakeNarrator(ElevenLabsClient):
    def __init__(self, directory):
        super().__init__(NarrationConfig("unit-test-only", "unit_voice"), directory)
        self.calls = 0

    def generate_incident_briefing(self, report):
        self.calls += 1
        audio = b"unit-test audio only"
        identity = self.identity(report)
        self._atomic_write(self.directory / f"{identity}.mp3", audio)
        self._atomic_write(
            self.directory / f"{identity}.json",
            json.dumps(
                {
                    "run_id": report.run_id,
                    "report_sha256": report_digest(report),
                    "audio_sha256": hashlib.sha256(audio).hexdigest(),
                    "transcript": briefing_script(report),
                }
            ).encode(),
        )


def completed(store):
    async def scenario():
        service = Orchestrator(store, UnitTestEngine())
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        return service, response.run_id

    return asyncio.run(scenario())


def test_idempotent_jobs_and_durable_audio_are_bound_to_report(tmp_path):
    store = RunStore(tmp_path / "runs")
    orchestrator, run_id = completed(store)
    narrator = FakeNarrator(tmp_path / "audio")
    service = BriefingService(store, narrator)
    digest = report_digest(saved_report(store, run_id))

    async def scenario():
        assert service.generate(run_id, digest).status == "generating"
        assert service.generate(run_id, digest).status == "generating"
        await service.close()

    asyncio.run(scenario())
    ready = service.status(run_id)
    assert ready.status == "ready" and narrator.calls == 1
    assert "does not prove universal security" in ready.transcript
    assert BriefingService(store, narrator).status(run_id) == ready
    # No model/provider can reuse old audio while a new challenge is running.
    record = store.get(run_id)
    record.run.status = RunStatus.CHALLENGING
    record.run.verification = None
    store.save(record)
    with pytest.raises(ValueError):
        service.media(ready.artifact_id)
    assert narrator.calls == 1


def test_stale_digest_and_tampered_audio_fail_closed(tmp_path):
    store = RunStore(tmp_path / "runs")
    _, run_id = completed(store)
    narrator = FakeNarrator(tmp_path / "audio")
    service = BriefingService(store, narrator)
    with pytest.raises(ValueError):
        service.generate(run_id, "0" * 64)
    assert narrator.calls == 0
    narrator.generate_incident_briefing(saved_report(store, run_id))
    ready = service.status(run_id)
    path, _ = service.media(ready.artifact_id)
    path.write_bytes(b"corrupted")
    assert service.status(run_id).status == "not_generated"


def test_optional_api_never_accepts_arbitrary_text(tmp_path, monkeypatch):
    monkeypatch.delenv("PROOFLOOP_NARRATION_ENABLED", raising=False)
    store = RunStore(tmp_path)
    orchestrator, run_id = completed(store)
    with TestClient(create_app(orchestrator=orchestrator)) as client:
        status = client.get(f"/api/runs/{run_id}/briefing")
        assert status.status_code == 200 and status.json()["status"] == "unavailable"
        digest = status.json()["report_sha256"]
        assert (
            client.post(
                f"/api/runs/{run_id}/briefing",
                json={
                    "report_sha256": digest,
                    "text": "invent a successful result",
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/runs/{run_id}/briefing",
                json={
                    "report_sha256": "0" * 64,
                },
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/runs/{run_id}/briefing",
                json={
                    "report_sha256": digest,
                },
            ).json()["status"]
            == "unavailable"
        )
        assert client.get("/api/health").status_code == 200
        assert client.get(f"/api/runs/{run_id}/report").json() == saved_report(
            store, run_id
        ).model_dump(mode="json")


def test_new_report_after_rechallenge_cannot_serve_previous_audio(tmp_path):
    store = RunStore(tmp_path / "runs")
    orchestrator, run_id = completed(store)
    narrator = FakeNarrator(tmp_path / "audio")
    service = BriefingService(store, narrator)
    previous = saved_report(store, run_id)
    narrator.generate_incident_briefing(previous)
    old_id = service.status(run_id).artifact_id
    # Unit engine reuses evidence values, so bind a distinct real-shaped new reference.
    record = store.get(run_id)
    reference = record.evidence[0].model_copy(update={"artifact_id": "unit_new_evidence"})
    record.evidence.append(reference)
    store.save(record)
    assert service.status(run_id).status == "not_generated"
    with pytest.raises(ValueError):
        service.media(old_id)
