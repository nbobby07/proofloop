"""Export canonical schemas from Pydantic; --check detects drift without writing."""

import argparse
import json
from pathlib import Path

from backend.api.main import app
from backend.api.schemas import RunResponse, SecurityEvent

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = {
        "openapi.json": app.openapi(),
        "events.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **SecurityEvent.model_json_schema(),
        },
        "run.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **RunResponse.model_json_schema(),
        },
    }
    for filename, data in documents.items():
        path = ROOT / "contracts" / filename
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Contract drift: regenerate {path.relative_to(ROOT)}")
        else:
            path.write_text(text, encoding="utf-8")
    print("Contracts are current." if args.check else "Contracts exported.")


if __name__ == "__main__":
    main()
