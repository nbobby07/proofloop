"""Trusted pytest plugin: retain every phase, including errors and skips."""

import json
import os
from pathlib import Path

RESULTS = {}
COLLECTED = []


def pytest_collection_finish(session):
    COLLECTED.extend(item.nodeid for item in session.items)


def pytest_runtest_logreport(report):
    result = RESULTS.setdefault(report.nodeid, {"test_id": report.nodeid, "phases": []})
    result["phases"].append(
        {
            "phase": report.when,
            "outcome": report.outcome,
            "duration_seconds": report.duration,
            "failure": str(report.longrepr) if report.failed or report.skipped else None,
        }
    )


def pytest_sessionfinish(session, exitstatus):
    Path(os.environ["LEDGERLITE_RESULTS_FILE"]).write_text(
        json.dumps(
            {
                "pytest_exit_code": int(exitstatus),
                "collected": COLLECTED,
                "results": list(RESULTS.values()),
            },
            indent=2,
        )
        + "\n"
    )
