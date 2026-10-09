from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from backend.api.schemas import SecurityEvent
from backend.telemetry.client import ClickHouseClient, ClickHouseConfig, TelemetryUnavailable


def event(source="execution", **metadata):
    return SecurityEvent(
        event_id="event_unit",
        run_id="run_unit",
        source=source,
        timestamp=datetime.now(UTC),
        stage="verifying",
        event_type="test_completed",
        severity="info",
        message="Unit telemetry input",
        metadata=metadata,
    )


def test_fixture_batch_is_rejected_before_any_database_write():
    driver = Mock()
    with pytest.raises(ValueError, match="Fixture"):
        ClickHouseClient(driver).insert_security_events([event(), event("fixture")])
    driver.insert.assert_not_called()


def test_fixture_metadata_cannot_bypass_the_source_boundary():
    driver = Mock()
    with pytest.raises(ValueError, match="Fixture"):
        ClickHouseClient(driver).insert_security_events([event(fixture=True)])
    driver.insert.assert_not_called()


def test_unexecuted_passes_are_unknown_and_arbitrary_metadata_is_not_exported():
    driver = Mock()
    client = ClickHouseClient(driver)
    client.insert_security_events([event(outcome="pass", executed=False, secret="private-key")])
    rows = driver.insert.call_args.args[1]
    record = dict(zip(client.columns, rows[0], strict=True))
    assert record["outcome"] == "unknown"
    assert record["executed"] == 0
    assert "private-key" not in str(rows)


def test_malformed_optional_json_metadata_does_not_become_a_success():
    driver = Mock()
    client = ClickHouseClient(driver)
    client.insert_security_events([event(outcome={"claim": "pass"}, executed=True)])
    record = dict(zip(client.columns, driver.insert.call_args.args[1][0], strict=True))
    assert record["outcome"] == "unknown"


def test_remote_connections_require_verified_tls():
    with pytest.raises(ValueError, match="TLS"):
        ClickHouseConfig("example.com", "unit", "unit-password", secure=False)
    assert "unit-password" not in repr(ClickHouseConfig("localhost", "unit", "unit-password"))


def test_database_errors_never_expose_driver_credentials():
    driver = Mock()
    driver.insert.side_effect = RuntimeError("password=private-key")
    with pytest.raises(TelemetryUnavailable) as raised:
        ClickHouseClient(driver).insert_security_events([event()])
    assert "private-key" not in str(raised.value)


def test_run_filter_rejects_injection_before_querying():
    driver = Mock()
    with pytest.raises(ValueError, match="run id"):
        ClickHouseClient(driver).query_failure_patterns("run'; DROP TABLE events")
    driver.query.assert_not_called()
