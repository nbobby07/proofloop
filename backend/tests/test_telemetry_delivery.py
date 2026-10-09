"""Synthetic telemetry boundaries only; these tests make no live database calls."""

import asyncio
import threading
from datetime import UTC, datetime

import pytest

from backend.api.schemas import CreateRunRequest, RunResponse, SecurityEvent
from backend.engine.orchestrator import Orchestrator
from backend.storage.runs import RunRecord, RunStore
from backend.telemetry.client import ClickHouseClient, TelemetryUnavailable
from backend.telemetry.delivery import TelemetryDelivery
from backend.tests.test_orchestrator import UnitTestEngine, settle


def record(count=1, source="execution"):
    return RunRecord(
        request=CreateRunRequest(target="LedgerLite"),
        run=RunResponse(
            run_id=f"unit_{source}",
            target="LedgerLite",
            status="pending",
            source=source,
            events=[
                SecurityEvent(
                    event_id=f"event_{i}",
                    run_id=f"unit_{source}",
                    timestamp=datetime.now(UTC),
                    stage="pending",
                    event_type="stage_started",
                    severity="info",
                    source=source,
                    message="secret request content must not leave storage",
                    metadata={"sequence": i + 1, "target": "LedgerLite", "secret": "hidden"},
                )
                for i in range(count)
            ],
        ),
    )


class Driver:
    def __init__(self):
        self.rows = {}
        self.sizes = []
        self.fail_after_insert = False

    def insert(self, table, rows, column_names):
        self.sizes.append(len(rows))
        for row in rows:
            data = dict(zip(column_names, row, strict=True))
            self.rows[(data["run_id"], data["event_id"])] = data
        if self.fail_after_insert:
            raise RuntimeError("private driver failure")

    def close(self):
        pass


def test_persist_first_bounded_replay_and_secret_projection(tmp_path):
    store = RunStore(tmp_path)
    driver = Driver()
    delivery = TelemetryDelivery(store, lambda: ClickHouseClient(driver))
    assert delivery.flush() == 0
    store.save(record(1001))
    store.save(record(source="fixture"))
    driver.fail_after_insert = True
    with pytest.raises(TelemetryUnavailable):
        delivery.flush()
    assert delivery.offsets == {}
    driver.fail_after_insert = False
    assert delivery.flush() == 1001
    assert delivery.flush() == 0
    # A fresh worker replays, and database identity remains unchanged.
    assert TelemetryDelivery(store, lambda: ClickHouseClient(driver)).flush() == 1001
    assert len(driver.rows) == 1001
    assert max(driver.sizes) == 1000
    serialized = str(driver.rows)
    assert "hidden" not in serialized and "secret request" not in serialized
    assert {row["sequence"] for row in driver.rows.values()} == set(range(1, 1002))


def test_mixed_fixture_batch_is_rejected_atomically():
    driver = Driver()
    client = ClickHouseClient(driver)
    with pytest.raises(ValueError, match="Fixture"):
        client.insert_security_events(record().run.events + record(source="fixture").run.events)
    assert driver.rows == {}


def test_database_work_is_off_loop_and_outage_retains_manifests(tmp_path):
    async def scenario():
        store = RunStore(tmp_path)
        store.save(record())
        main_thread = threading.get_ident()
        called = threading.Event()

        def unavailable():
            assert threading.get_ident() != main_thread
            called.set()
            raise TelemetryUnavailable("Unit-test outage")

        delivery = TelemetryDelivery(store, unavailable, interval=0.01)
        delivery.start()
        for _ in range(100):
            if delivery.last_error:
                break
            await asyncio.sleep(0.01)
        await delivery.close()
        assert called.is_set() and delivery.last_error == "telemetry_unavailable"
        assert len(store.get("unit_execution").run.events) == 1
        assert delivery.offsets == {}

    asyncio.run(scenario())


def test_canonical_sequence_and_round_identity_across_rechallenge(tmp_path):
    async def scenario():
        from backend.api.schemas import ChallengeRequest

        store = RunStore(tmp_path)
        service = Orchestrator(store, UnitTestEngine())
        created = service.create(CreateRunRequest(target="LedgerLite"))
        await settle(service)
        initial = store.get(created.run_id)
        service.rechallenge(created.run_id, ChallengeRequest())
        assert store.get(created.run_id).run.verification is None
        await settle(service)
        events = store.get(created.run_id).run.events
        assert [e.metadata["sequence"] for e in events] == list(range(1, len(events) + 1))
        assert events[: len(initial.run.events)] == initial.run.events
        rounds = [e for e in events if "test_execution_id" in e.metadata]
        assert len(rounds) == 3
        assert len({e.metadata["test_execution_id"] for e in rounds}) == 3
        assert all(e.metadata["outcome"] == "pass" for e in rounds)
        assert all(e.metadata["patch_hash"] for e in rounds)

    asyncio.run(scenario())
