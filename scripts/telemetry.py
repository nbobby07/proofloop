"""Explicit ClickHouse schema migration, durable-event replay, and read-only queries."""

import argparse
import json
import os
from pathlib import Path

from backend.providers.contracts import AnalyticsFilters
from backend.storage.runs import RunStore
from backend.telemetry.client import ClickHouseClient, ClickHouseConfig, TelemetryUnavailable
from backend.telemetry.delivery import TelemetryDelivery
from scripts.dev_backend import load_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("initialize", "replay", "query"))
    parser.add_argument("--run-id")
    args = parser.parse_args()
    load_environment()
    client = None
    try:
        client = ClickHouseClient.connect(ClickHouseConfig.from_env())
        if args.operation == "initialize":
            client.initialize_schema()
            print("ClickHouse schema initialized.")
        elif args.operation == "replay":
            store = RunStore(Path(os.getenv("PROOFLOOP_RUNS_DIR", "runs")))
            count = TelemetryDelivery(store, connect=lambda: client).flush()
            print(f"Acknowledged {count} persisted execution events; queries deduplicate replays.")
        else:
            filters = AnalyticsFilters(run_id=args.run_id)
            result = client.query_security_analytics(filters)
            print(json.dumps(result.model_dump(mode="json"), indent=2))
    except (TelemetryUnavailable, ValueError):
        parser.exit(
            1, "ClickHouse unavailable or invalid configuration; local execution is unaffected.\n"
        )
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
