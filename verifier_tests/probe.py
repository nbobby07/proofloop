"""Read-only deterministic reproduction; run only against authorized synthetic code."""

import importlib.util
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def main():
    spec = importlib.util.spec_from_file_location("ledgerlite_probe", Path(sys.argv[1]))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.create_app()) as client:
        response = client.get("/invoices/inv-2047", headers={"X-Synthetic-Identity": "alice"})
    body = response.json()
    print(
        json.dumps(
            {
                "request": {
                    "method": "GET",
                    "path": "/invoices/inv-2047",
                    "synthetic_identity": "alice",
                },
                "response": {"status_code": response.status_code, "body": body},
                "unauthorized_access_reproduced": response.status_code == 200
                and body
                == {
                    "id": "inv-2047",
                    "owner_id": "bob",
                    "amount_cents": 48750,
                    "currency": "USD",
                    "status": "paid",
                    "source": "fixture",
                },
            }
        )
    )


if __name__ == "__main__":
    main()
