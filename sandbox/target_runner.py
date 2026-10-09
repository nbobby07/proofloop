"""Fixed LedgerLite service entry point, executed only inside the target container."""

import sys

import uvicorn

sys.path.insert(0, "/source")
uvicorn.run(
    "demo_target.ledgerlite.app:app",
    host="127.0.0.1",
    port=8000,
    access_log=False,
    log_level="warning",
    workers=1,
)
