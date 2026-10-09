"""ClickHouse implementation of the frozen telemetry protocol. No calls on import."""

import math
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.api.schemas import AnalyticsResponse, FailurePattern, SecurityEvent
from backend.providers.contracts import AnalyticsFilters


class TelemetryUnavailable(RuntimeError):
    """Safe error for the API boundary; never contains driver details or credentials."""


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str
    username: str
    password: str = field(repr=False)
    port: int = 8443
    database: str = "default"
    secure: bool = True

    def __post_init__(self) -> None:
        if not self.host or "://" in self.host or "/" in self.host:
            raise ValueError("ClickHouse requires a hostname without a URL scheme or path.")
        if not 1 <= self.port <= 65535:
            raise ValueError("Invalid ClickHouse port.")
        if not self.secure and self.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Remote ClickHouse connections require TLS.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", self.database):
            raise ValueError("Invalid ClickHouse database identifier.")

    @classmethod
    def from_env(cls) -> "ClickHouseConfig":
        host, user, password = (
            os.getenv(name, "")
            for name in ("CLICKHOUSE_HOST", "CLICKHOUSE_USER", "CLICKHOUSE_PASSWORD")
        )
        if not host or not user or not password:
            raise TelemetryUnavailable("ClickHouse credentials are not configured.")
        secure = os.getenv("CLICKHOUSE_SECURE", "true").lower() == "true"
        if not secure and host not in {"localhost", "127.0.0.1", "::1"}:
            raise TelemetryUnavailable("Remote ClickHouse connections require TLS.")
        if "://" in host or "/" in host:
            raise TelemetryUnavailable("CLICKHOUSE_HOST must contain only a hostname.")
        return cls(
            host,
            user,
            password,
            int(os.getenv("CLICKHOUSE_PORT", "8443")),
            os.getenv("CLICKHOUSE_DATABASE", "default"),
            secure,
        )


def _text(value: Any, maximum: int = 128) -> str:
    return value if isinstance(value, str) and len(value) <= maximum else ""


def _integer(value: Any, maximum: int = 2**63 - 1) -> int | None:
    return value if type(value) is int and 0 <= value <= maximum else None


def _duration(value: Any) -> float | None:
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return float(value)
    return None


class ClickHouseClient:
    """Use from A's worker/threadpool. Persist first; replay failed batches from storage.

    Metadata names are a proposed producer convention documented in README.md.
    Unrecognized metadata and all free-form messages are excluded from export.
    """

    columns = [
        "run_id",
        "event_id",
        "timestamp",
        "stage",
        "event_type",
        "severity",
        "source",
        "sequence",
        "target",
        "challenge_family",
        "test_execution_id",
        "suite",
        "outcome",
        "executed",
        "attempt",
        "duration_ms",
        "patch_hash",
        "suite_hash",
        "policy_hash",
        "finding_key",
        "baseline_reproduced",
        "provider",
        "activity",
        "target_revision",
        "environment",
        "model",
        "cost_reservation_usd",
        "measured_cost_usd",
        "inserted_at",
    ]

    def __init__(self, client: Any, database: str = "default"):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", database):
            raise ValueError("Invalid ClickHouse database identifier.")
        self.client = client
        self.table = f"{database}.proofloop_events"
        self.last_query_ms: float | None = None
        self.last_insert_at: datetime | None = None

    @classmethod
    def connect(cls, config: ClickHouseConfig) -> "ClickHouseClient":
        try:
            import clickhouse_connect

            client = clickhouse_connect.get_client(
                host=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                database=config.database,
                secure=config.secure,
                connect_timeout=5,
                send_receive_timeout=15,
                autogenerate_session_id=False,
                settings={"max_execution_time": 10, "max_result_rows": 10000},
            )
            return cls(client, config.database)
        except Exception:
            raise TelemetryUnavailable("ClickHouse connection unavailable.") from None

    def initialize_schema(self) -> None:
        """Explicit migration; no schema creation from request handlers or imports."""
        sql = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        try:
            self.client.command(sql.format(table=self.table))
        except Exception:
            raise TelemetryUnavailable("ClickHouse schema initialization failed.") from None

    def insert_security_events(self, events: list[SecurityEvent]) -> None:
        if not events:
            return
        if len(events) > 1000:
            raise ValueError("Telemetry batches are limited to 1000 events.")
        checked = [SecurityEvent.model_validate(e) for e in events]
        if any(e.source != "execution" or e.metadata.get("fixture") is True for e in checked):
            raise ValueError("Fixture data cannot enter production telemetry.")
        now = datetime.now(UTC)
        rows = []
        for event in checked:
            meta = event.metadata
            outcome = meta.get("outcome")
            outcome = (
                outcome
                if isinstance(outcome, str)
                and outcome in {"pass", "fail", "timeout", "error", "skipped", "missing"}
                else "unknown"
            )
            if outcome in {"pass", "fail"} and meta.get("executed") is not True:
                outcome = "unknown"
            hashes = [
                _text(meta.get(name), 64) for name in ("patch_hash", "suite_hash", "policy_hash")
            ]
            hashes = [value if re.fullmatch(r"[a-f0-9]{64}", value) else "" for value in hashes]
            rows.append(
                [
                    event.run_id,
                    event.event_id,
                    event.timestamp.astimezone(UTC),
                    event.stage.value,
                    event.event_type.value,
                    event.severity.value,
                    event.source.value,
                    _integer(meta.get("sequence")),
                    _text(meta.get("target")),
                    _text(meta.get("challenge_family")),
                    _text(meta.get("test_execution_id")),
                    _text(meta.get("suite")),
                    outcome,
                    int(meta.get("executed") is True),
                    _integer(meta.get("attempt"), 10),
                    _duration(meta.get("duration_ms")),
                    *hashes,
                    _text(meta.get("finding_key")),
                    int(meta["reproduced"])
                    if type(meta.get("reproduced")) is bool and meta.get("executed") is True
                    else None,
                    _text(meta.get("provider")),
                    _text(meta.get("activity")),
                    _text(meta.get("target_revision"), 64),
                    _text(meta.get("environment")),
                    _text(meta.get("model")),
                    _duration(meta.get("cost_reservation_usd")),
                    _duration(meta.get("measured_cost_usd")),
                    now,
                ]
            )
        try:
            self.client.insert(self.table, rows, column_names=self.columns)
        except Exception:
            raise TelemetryUnavailable(
                "Telemetry ingestion failed; replay persisted events."
            ) from None
        self.last_insert_at = now

    def _query(self, sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        start = perf_counter()
        try:
            return list(self.client.query(sql, parameters=parameters or {}).named_results())
        except Exception:
            raise TelemetryUnavailable("ClickHouse analytics query unavailable.") from None
        finally:
            self.last_query_ms = (perf_counter() - start) * 1000

    def _events(self, run_id: str | None = None) -> tuple[str, dict[str, Any]]:
        where = "source = 'execution'"
        parameters: dict[str, Any] = {}
        if run_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
                raise ValueError("Invalid run id.")
            where += " AND run_id = {run_id:String}"
            parameters["run_id"] = run_id
        return f"SELECT * FROM {self.table} FINAL WHERE {where}", parameters

    def _patterns(self, run_id: str | None = None) -> list[FailurePattern]:
        events, params = self._events(run_id)
        rows = self._query(
            f"""
            WITH outcomes AS (
                SELECT run_id, test_execution_id,
                       any(challenge_family) AS family, any(outcome) AS result
                FROM ({events})
                WHERE event_type = 'test_completed' AND test_execution_id != ''
                      AND challenge_family != ''
                GROUP BY run_id, test_execution_id
                HAVING uniqExact(outcome) = 1 AND uniqExact(challenge_family) = 1
            )
            SELECT family AS challenge_family, countIf(result = 'fail') AS failures,
                   count() AS executions
            FROM outcomes GROUP BY family ORDER BY failures DESC, family
        """,
            params,
        )
        return [FailurePattern.model_validate(row) for row in rows]

    def query_security_analytics(self, filters: AnalyticsFilters) -> AnalyticsResponse:
        events, params = self._events(filters.run_id)
        # Missing/tied sequence data cannot establish a current terminal status.
        rows = self._query(
            f"""
            WITH runs AS (
                SELECT run_id, argMax(stage, sequence) AS latest,
                       countIf(isNull(sequence)) AS unordered,
                       count() - uniqExact(sequence) AS duplicate_sequence
                FROM ({events}) GROUP BY run_id
            )
            SELECT count() AS run_count,
                   countIf(latest = 'verified' AND unordered = 0
                           AND duplicate_sequence = 0) AS verified_count,
                   countIf(latest = 'rejected' AND unordered = 0
                           AND duplicate_sequence = 0) AS rejected_count
            FROM runs
        """,
            params,
        )
        return AnalyticsResponse(
            source="execution", **rows[0], failure_patterns=self._patterns(filters.run_id)
        )

    def query_failure_patterns(self, run_id: str) -> list[FailurePattern]:
        """Historical results restricted to the run's target, suite and policy context."""
        events, params = self._events(run_id)
        context = self._query(
            f"""
            SELECT DISTINCT target, suite_hash, policy_hash FROM ({events})
            WHERE target != '' AND suite_hash != '' AND policy_hash != ''
        """,
            params,
        )
        if len(context) != 1:
            return []
        context_params = context[0]
        rows = self._query(
            f"""
            WITH outcomes AS (
                SELECT run_id, test_execution_id, any(challenge_family) AS family,
                       any(outcome) AS result
                FROM {self.table} FINAL
                WHERE source = 'execution' AND event_type = 'test_completed'
                  AND target = {{target:String}} AND suite_hash = {{suite_hash:String}}
                  AND policy_hash = {{policy_hash:String}}
                  AND timestamp >= now() - INTERVAL 30 DAY
                  AND test_execution_id != '' AND challenge_family != ''
                GROUP BY run_id, test_execution_id
                HAVING uniqExact(outcome) = 1 AND uniqExact(challenge_family) = 1
            )
            SELECT family AS challenge_family, countIf(result = 'fail') AS failures,
                   count() AS executions FROM outcomes GROUP BY family
            HAVING executions >= 3
            ORDER BY failures / executions DESC, failures DESC, family LIMIT 10
        """,
            context_params,
        )
        return [FailurePattern.model_validate(row) for row in rows]

    def query_extended_metrics(self, filters: AnalyticsFilters) -> dict[str, Any]:
        """Internal result only; not an unapproved API response extension."""
        events, params = self._events(filters.run_id)
        coverage = self._query(
            f"""
            SELECT count() AS event_count, countIf(isNull(sequence)) AS unordered_events,
                   countIf(event_type = 'test_completed' AND test_execution_id = '')
                     AS unclassified_test_events, max(timestamp) AS latest_event_at
            FROM ({events})
        """,
            params,
        )[0]
        metrics = self._query(
            f"""
            WITH outcomes AS (
                SELECT run_id, test_execution_id, any(suite) AS selected_suite,
                       any(outcome) AS result, any(executed) AS was_executed,
                       any(duration_ms) AS selected_duration_ms
                FROM ({events}) WHERE event_type = 'test_completed'
                  AND test_execution_id != '' GROUP BY run_id, test_execution_id
                HAVING uniqExact(tuple(outcome, suite, executed)) = 1
            )
            SELECT countIf(selected_suite = 'security' AND was_executed = 1)
                     AS executed_security_tests,
                   countIf(result NOT IN ('pass', 'fail')) AS incomplete_checks,
                   count() AS recorded_checks,
                   avgOrNullIf(selected_duration_ms, result IN ('pass', 'fail'))
                     AS mean_test_duration_ms
            FROM outcomes
        """,
            params,
        )[0]
        attempts = self._query(
            f"""
            SELECT avgOrNull(attempts) AS mean_patch_attempts FROM (
                SELECT run_id, uniqExactIf(attempt, event_type = 'patch_proposed'
                       AND attempt IS NOT NULL) AS attempts FROM ({events}) GROUP BY run_id
            )
        """,
            params,
        )[0]
        baselines = self._query(
            f"""
            SELECT count() AS baseline_attempts,
                   countIf(reproduced = 1) AS reproduced_baselines FROM (
                SELECT run_id, test_execution_id, any(baseline_reproduced) AS reproduced
                FROM ({events}) WHERE event_type = 'test_completed' AND suite = 'baseline'
                  AND test_execution_id != '' GROUP BY run_id, test_execution_id
                HAVING uniqExact(tuple(baseline_reproduced)) = 1
            )
        """,
            params,
        )[0]
        verification = self._query(
            f"""
            SELECT avgOrNullIf(duration, starts = 1 AND ends = 1 AND duration >= 0)
                     AS mean_verification_duration_ms,
                   countIf(starts != 1 OR ends != 1 OR duration < 0)
                     AS incomplete_verification_attempts
            FROM (
                SELECT run_id, attempt,
                       countIf(event_type = 'stage_started') AS starts,
                       countIf(event_type = 'stage_completed') AS ends,
                       dateDiff('millisecond',
                           minIf(timestamp, event_type = 'stage_started'),
                           maxIf(timestamp, event_type = 'stage_completed')) AS duration
                FROM ({events}) WHERE stage = 'verifying' AND attempt IS NOT NULL
                  AND event_type IN ('stage_started', 'stage_completed')
                GROUP BY run_id, attempt
            )
        """,
            params,
        )[0]
        buckets = self._query(
            f"""
            SELECT toStartOfMinute(recorded_at) AS minute, result AS outcome,
                   count() AS outcomes FROM (
                SELECT run_id, test_execution_id, any(outcome) AS result,
                       min(timestamp) AS recorded_at FROM ({events})
                WHERE event_type = 'test_completed' AND test_execution_id != ''
                GROUP BY run_id, test_execution_id HAVING uniqExact(outcome) = 1
            ) GROUP BY minute, result ORDER BY minute, result LIMIT 1000
        """,
            params,
        )
        return {
            "source": "execution",
            **coverage,
            **metrics,
            **attempts,
            **baselines,
            **verification,
            "outcomes_over_time": buckets,
            "query_ms": self.last_query_ms,
            "limitations": [
                "Only recorded outcomes are observable; absent required checks "
                "need explicit missing records from the verifier.",
                "Latency measures the last SQL request, not end-to-end ingestion.",
            ],
        }

    def close(self) -> None:
        self.client.close()
