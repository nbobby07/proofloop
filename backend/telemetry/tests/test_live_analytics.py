"""Cloud API boundaries use doubles; no sponsor requests in tests."""

from datetime import datetime
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.api.main import create_app
from backend.api.schemas import AnalyticsResponse
from backend.storage.runs import RunStore
from backend.telemetry.client import TelemetryUnavailable
from backend.telemetry.delivery import TelemetryDelivery
from backend.tests.test_telemetry_delivery import record


def test_sql_snapshot_reports_pending_events_and_normalizes_utc(tmp_path):
    store = RunStore(tmp_path)
    store.save(record(3))
    store.save(record(2, source="fixture"))
    cloud = Mock()
    cloud.query_security_analytics.return_value = AnalyticsResponse(
        source="execution", run_count=1, verified_count=0, rejected_count=0, failure_patterns=[]
    )
    cloud.query_extended_metrics.return_value = {
        "event_count": 2,
        "incomplete_checks": 0,
        "mean_patch_attempts": None,
        "mean_verification_duration_ms": None,
        "latest_event_at": datetime(2026, 10, 9),
    }
    delivery = TelemetryDelivery(store, lambda: cloud)
    delivery.offsets["unit_execution"] = 2
    result = delivery.analytics()
    assert result.storage == "clickhouse"
    assert result.event_count == 2 and result.pending_events == 1
    assert result.latest_event_at.isoformat() == "2026-10-09T00:00:00+00:00"
    assert result.query_ms >= 0
    cloud.insert_security_events.assert_not_called()


def test_cloud_outage_never_returns_local_data_as_clickhouse(tmp_path, monkeypatch):
    monkeypatch.setenv("PROOFLOOP_RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("PROOFLOOP_TELEMETRY_ENABLED", "0")
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/telemetry/analytics").status_code == 503
        app.state.telemetry = Mock()
        app.state.telemetry.analytics.side_effect = TelemetryUnavailable("password=private-test")
        response = client.get("/api/telemetry/analytics")
        assert response.status_code == 503 and "private-test" not in response.text
        assert client.get("/api/analytics").status_code == 200
        assert client.get("/api/health").status_code == 200


def test_driver_access_is_serialized_with_delivery(tmp_path):
    import threading

    store = RunStore(tmp_path)
    store.save(record())
    delivery = TelemetryDelivery(store, lambda: Mock())
    entered = threading.Event()
    finished = threading.Event()

    def background_flush():
        entered.set()
        delivery.flush()
        finished.set()

    with delivery.lock:
        worker = threading.Thread(target=background_flush)
        worker.start()
        assert entered.wait(1)
        assert not finished.wait(0.02)
    worker.join(1)
    assert finished.is_set()
