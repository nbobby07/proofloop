"""PLANNED telemetry adapter; schema source is contracts/events.schema.json."""

from typing import Protocol

from backend.api.schemas import AnalyticsResponse, FailurePattern, SecurityEvent
from backend.providers.contracts import AnalyticsFilters


class ClickHouseTelemetry(Protocol):
    def insert_security_events(self, events: list[SecurityEvent]) -> None: ...

    def query_security_analytics(self, filters: AnalyticsFilters) -> AnalyticsResponse: ...

    def query_failure_patterns(self, run_id: str) -> list[FailurePattern]: ...
