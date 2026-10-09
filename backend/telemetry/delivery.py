"""Optional delivery of durable canonical events. SQL never runs on the API loop."""

import asyncio
import logging
import os

from backend.storage.runs import RunStore
from backend.telemetry.client import ClickHouseClient, ClickHouseConfig

logger = logging.getLogger(__name__)


class TelemetryDelivery:
    """Replay after restart is safe: ClickHouse FINAL deduplicates (run_id, event_id).

    Local manifests are the durable outbox. A cursor advances only after an acknowledged
    insert; an ambiguous failure is replayed. A single worker serializes driver access.
    No database schema is created here, and no fixture event is delivered.
    """

    def __init__(self, store: RunStore, connect=None, interval: float = 5):
        self.store = store
        self.connect = connect or (lambda: ClickHouseClient.connect(ClickHouseConfig.from_env()))
        self.interval = interval
        self.client = None
        self.offsets: dict[str, int] = {}
        self.stop = asyncio.Event()
        self.task = None
        self.last_error: str | None = None

    def flush(self) -> int:
        # This method is synchronous and must be called from a worker or the CLI.
        if self.client is None:
            self.client = self.connect()
        delivered = 0
        for record in self.store.all():
            if record.run.source != "execution":
                continue
            events = record.run.events
            offset = self.offsets.get(record.run.run_id, 0)
            while offset < len(events):
                batch = events[offset : offset + 1000]
                self.client.insert_security_events(batch)
                offset += len(batch)
                self.offsets[record.run.run_id] = offset
                delivered += len(batch)
        return delivered

    async def _run(self) -> None:
        while not self.stop.is_set():
            try:
                await asyncio.to_thread(self.flush)
                self.last_error = None
            except Exception:
                # Never log driver details, configuration or request contents.
                if self.last_error is None:
                    logger.warning("ClickHouse delivery unavailable; local evidence is retained.")
                self.last_error = "telemetry_unavailable"
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=self.interval)
            except TimeoutError:
                pass

    def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def close(self) -> None:
        self.stop.set()
        if self.task:
            await self.task
        if self.client:
            try:
                await asyncio.to_thread(self.client.close)
            except Exception:
                pass


def configured_delivery(store: RunStore) -> TelemetryDelivery | None:
    if os.getenv("PROOFLOOP_TELEMETRY_ENABLED") != "1":
        return None
    return TelemetryDelivery(store)
