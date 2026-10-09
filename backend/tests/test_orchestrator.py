"""Unit-test doubles only: none of these engines are installed in production."""

import asyncio
import hashlib

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.schemas import (
    BaselineResult,
    ChallengeRequest,
    CreateRunRequest,
    EvidenceReference,
    Finding,
    PatchProposal,
    VerificationSummary,
)
from backend.api.schemas import (
    RunStatus as S,
)
from backend.engine.orchestrator import (
    BaselineReceipt,
    InvalidTransition,
    Orchestrator,
    StageResult,
)
from backend.storage.runs import RunStore


class UnitTestEngine:
    """Synthetic unit-test double, never execution evidence or an application default."""

    def __init__(self, verdict=S.VERIFIED):
        self.verdict = verdict
        self.patches = []
        self.complete = True
        self.delay = 0
        self.calls = []

    async def discover(self, run_id, target):
        self.calls.append("discover")
        await asyncio.sleep(self.delay)
        return Finding(id="unit_finding", title="Unit test only", severity="high")

    async def reproduce(self, run_id, finding):
        return BaselineReceipt(
            result=BaselineResult(reproduced=True),
            evidence=[
                EvidenceReference(
                    artifact_id="unit_baseline",
                    sha256="b" * 64,
                    description="Unit-test double baseline only",
                )
            ],
        )

    async def generate_patch(self, run_id, finding, attempt, feedback):
        patch = PatchProposal(attempt=attempt, diff=f"unit-test-only-{attempt}")
        self.patches.append(patch)
        return patch

    async def apply_patch(self, run_id, patch):
        pass

    async def verify(self, run_id):
        return self.result()

    async def challenge(self, run_id, request):
        self.calls.append("challenge")
        await asyncio.sleep(self.delay)
        return self.result()

    def result(self):
        return StageResult(
            verdict=self.verdict,
            complete=self.complete,
            patch_sha256=hashlib.sha256(self.patches[-1].diff.encode()).hexdigest(),
            summary=VerificationSummary(
                security_passed=int(self.verdict == S.VERIFIED),
                security_total=1,
                functional_passed=1,
                functional_total=1,
                adversarial_passed=1,
                adversarial_total=1,
            ),
            evidence=[
                EvidenceReference(
                    artifact_id="unit_evidence",
                    sha256="a" * 64,
                    description="Unit-test double evidence only",
                )
            ],
        )


async def settle(service):
    await asyncio.gather(*list(service.tasks.values()))


def test_lifecycle_and_persistence(tmp_path):
    async def scenario():
        engine = UnitTestEngine()
        store = RunStore(tmp_path)
        service = Orchestrator(store, engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        assert response.status == S.PENDING
        await settle(service)
        record = RunStore(tmp_path).get(response.run_id)
        assert record.run.status == S.VERIFIED
        assert record.evidence and record.attempts[0].verification
        ids = [e.event_id for e in record.run.events]
        assert ids == sorted(set(ids))
        assert all(
            a.timestamp <= b.timestamp
            for a, b in zip(record.run.events, record.run.events[1:], strict=False)
        )
        assert [e.stage for e in record.run.events if e.event_type == "stage_started"] == [
            S.PENDING,
            S.DISCOVERING,
            S.REPRODUCING,
            S.GENERATING_PATCH,
            S.APPLYING_PATCH,
            S.VERIFYING,
            S.CHALLENGING,
            S.VERIFIED,
        ]
        with pytest.raises(InvalidTransition):
            service.transition(record, S.GENERATING_PATCH)

    asyncio.run(scenario())


@pytest.mark.parametrize("budget", [1, 3, 10])
def test_retry_limit(tmp_path, budget):
    async def scenario():
        engine = UnitTestEngine(S.REJECTED)
        service = Orchestrator(RunStore(tmp_path), engine)
        response = service.create(CreateRunRequest(target="LedgerLite", max_attempts=budget))
        await settle(service)
        record = service.store.get(response.run_id)
        assert record.run.status == S.REJECTED
        assert len(record.attempts) == len(engine.patches) == budget
        assert sum(e.event_type == "retry_scheduled" for e in record.run.events) == budget - 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("missing", S.INCONCLUSIVE),
        ("timeout", S.INCONCLUSIVE),
        ("exception", S.ERROR),
        ("unconfigured", S.ERROR),
    ],
)
def test_honest_failures(tmp_path, mode, expected):
    async def scenario():
        engine = UnitTestEngine()
        if mode == "missing":
            engine.complete = False
        if mode == "timeout":
            engine.delay = 1
        if mode == "exception":

            async def fail(*args):
                raise RuntimeError("SECRET_PROVIDER_KEY")

            engine.discover = fail
        service = Orchestrator(
            RunStore(tmp_path), None if mode == "unconfigured" else engine, stage_timeout=0.02
        )
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        record = service.store.get(response.run_id)
        assert record.run.status == expected
        assert "SECRET_PROVIDER_KEY" not in record.model_dump_json()

    asyncio.run(scenario())


def test_rechallenge_invalidates_status_before_work(tmp_path):
    async def scenario():
        engine = UnitTestEngine()
        service = Orchestrator(RunStore(tmp_path), engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        engine.verdict = S.REJECTED
        service.rechallenge(response.run_id, ChallengeRequest())
        current = service.store.get(response.run_id)
        assert current.run.status == S.CHALLENGING
        assert current.run.verification is None
        await settle(service)
        assert service.store.get(response.run_id).run.status == S.REJECTED
        assert len(engine.patches) == 1

    asyncio.run(scenario())


def test_api_poll_report_and_unknown(tmp_path):
    service = Orchestrator(RunStore(tmp_path))
    with TestClient(create_app(orchestrator=service)) as client:
        response = client.post("/api/runs", json={"target": "LedgerLite"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert response.json()["status"] == "pending"
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "error"
        first = client.get(f"/api/runs/{run_id}/events?limit=1").json()
        second = client.get(
            f"/api/runs/{run_id}/events", params={"cursor": first["next_cursor"], "limit": 200}
        ).json()
        assert not set(e["event_id"] for e in first["events"]) & set(
            e["event_id"] for e in second["events"]
        )
        assert client.get(f"/api/runs/{run_id}/events?cursor=bad").status_code == 422
        assert client.get(f"/api/runs/{run_id}/report").json()["status"] == "error"
        assert client.post(f"/api/runs/{run_id}/challenge", json={}).status_code == 409
        assert client.get("/api/analytics").json()["run_count"] == 1
        for suffix in ("", "/events", "/report"):
            assert client.get(f"/api/runs/unknown{suffix}").status_code == 404
        assert client.post("/api/runs/unknown/challenge", json={}).status_code == 404
        assert client.get("/api/analytics?run_id=unknown").status_code == 404


def test_recover_interrupted_run(tmp_path):
    async def scenario():
        engine = UnitTestEngine()
        engine.delay = 10
        service = Orchestrator(RunStore(tmp_path), engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        # Snapshot of an interrupted process before shutdown mutates its manifest.
        record = service.store.get(response.run_id)
        await service.close()
        service.store.save(record)
        restarted = Orchestrator(RunStore(tmp_path))
        restarted.recover()
        assert restarted.store.get(response.run_id).failure_code == "execution_interrupted"

    asyncio.run(scenario())


def test_stale_hash_and_empty_evidence_cannot_verify(tmp_path):
    async def scenario():
        for mode in ("hash", "empty", "zero", "incomplete_rejection"):
            engine = UnitTestEngine()
            original = engine.result

            def invalid_receipt(original=original, mode=mode):
                receipt = original()
                if mode == "hash":
                    receipt.patch_sha256 = "0" * 64
                if mode == "empty":
                    receipt.evidence = []
                if mode == "zero":
                    receipt.summary.security_passed = receipt.summary.security_total = 0
                if mode == "incomplete_rejection":
                    receipt.verdict = S.REJECTED
                    receipt.complete = False
                return receipt

            engine.result = invalid_receipt
            service = Orchestrator(RunStore(tmp_path / mode), engine)
            response = service.create(CreateRunRequest(target="LedgerLite"))
            await settle(service)
            assert service.store.get(response.run_id).run.status == S.INCONCLUSIVE

    asyncio.run(scenario())


def test_slow_engine_does_not_block_api_and_active_conflicts(tmp_path):
    import time

    engine = UnitTestEngine()
    engine.delay = 5
    service = Orchestrator(RunStore(tmp_path), engine, max_active=1)
    with TestClient(create_app(orchestrator=service)) as client:
        start = time.monotonic()
        response = client.post("/api/runs", json={"target": "LedgerLite"})
        assert response.status_code == 202
        assert time.monotonic() - start < 1
        run_id = response.json()["run_id"]
        assert client.get("/api/health").status_code == 200
        assert client.get(f"/api/runs/{run_id}/report").status_code == 409
        assert client.post(f"/api/runs/{run_id}/challenge", json={}).status_code == 409
        assert client.post("/api/runs", json={"target": "LedgerLite"}).status_code == 409
    assert service.store.get(run_id).run.status == S.ERROR


def test_path_safety_and_verification_history(tmp_path):
    with pytest.raises(KeyError):
        RunStore(tmp_path).get("../escape")

    async def scenario():
        engine = UnitTestEngine()
        service = Orchestrator(RunStore(tmp_path), engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        service.rechallenge(response.run_id, ChallengeRequest())
        await settle(service)
        record = service.store.get(response.run_id)
        receipts = record.attempts[0].verifications
        assert len(receipts) == 3
        assert [v.challenge_generation for v in receipts] == [0, 0, 1]
        assert [v.phase for v in receipts] == ["verification", "challenge", "challenge"]

    asyncio.run(scenario())


def test_all_transition_edges_are_enforced(tmp_path):
    from backend.api.schemas import RunResponse
    from backend.engine.orchestrator import TRANSITIONS
    from backend.storage.runs import RunRecord

    service = Orchestrator(RunStore(tmp_path))
    for before in S:
        for after in S:
            record = RunRecord(
                request=CreateRunRequest(target="LedgerLite"),
                run=RunResponse(
                    run_id="unit_transition", status=before, target="LedgerLite", source="execution"
                ),
            )
            if after in TRANSITIONS[before]:
                service.transition(record, after)
                assert service.store.get(record.run.run_id).run.status == after
            else:
                with pytest.raises(InvalidTransition):
                    service.transition(record, after)


def test_challenge_rejection_retries_and_timeout_keeps_history(tmp_path):
    async def scenario():
        engine = UnitTestEngine()
        original = engine.challenge

        async def reject_first(run_id, request):
            receipt = await original(run_id, request)
            if len(engine.patches) == 1:
                receipt.verdict = S.REJECTED
                receipt.summary.adversarial_passed = 0
            return receipt

        engine.challenge = reject_first
        service = Orchestrator(RunStore(tmp_path), engine, stage_timeout=0.05)
        response = service.create(CreateRunRequest(target="LedgerLite", max_attempts=2))
        await settle(service)
        record = service.store.get(response.run_id)
        assert record.run.status == S.VERIFIED
        assert [a.verdict for a in record.attempts] == [S.REJECTED, S.VERIFIED]
        engine.delay = 1
        service.rechallenge(response.run_id, ChallengeRequest())
        await settle(service)
        record = service.store.get(response.run_id)
        assert record.run.status == S.INCONCLUSIVE
        assert record.run.verification is None
        assert record.attempts[-1].verifications[-1].verdict == S.INCONCLUSIVE
        assert record.attempts[-1].verifications[-2].verdict == S.VERIFIED

    asyncio.run(scenario())


def test_api_rechallenge_returns_202_and_invalidates_report(tmp_path):
    async def prepare():
        engine = UnitTestEngine()
        service = Orchestrator(RunStore(tmp_path), engine)
        response = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        engine.delay = 10
        return service, response.run_id

    service, run_id = asyncio.run(prepare())
    with TestClient(create_app(orchestrator=service)) as client:
        response = client.post(f"/api/runs/{run_id}/challenge", json={"max_challenges": 1})
        assert response.status_code == 202
        assert response.json() == {"run_id": run_id, "status": "challenging", "source": "execution"}
        current = client.get(f"/api/runs/{run_id}").json()
        assert current["status"] == "challenging"
        assert current["verification"] is None
        assert client.get(f"/api/runs/{run_id}/report").status_code == 409
        assert client.post(f"/api/runs/{run_id}/challenge", json={}).status_code == 409
        assert client.get("/api/analytics").json()["verified_count"] == 0
