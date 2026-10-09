"""Explicit one-shot generation; preserve original bytes and API provenance before audit."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from backend.providers.http import JsonHttpClient, decode_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / "demo_target/ledgerlite_workspace"
    if (destination / "original/app.py").exists():
        raise SystemExit("Original already exists; never overwrite generation provenance")
    prompt = (ROOT / "docs/ledgerlite-workspace-spec.md").read_text()
    model = os.environ["OPENAI_MODEL"]
    payload = {
        "model": model,
        "store": False,
        "reasoning": {"effort": "none"},
        "max_output_tokens": 14000,
        "instructions": (
            "Implement the supplied specification correctly. Return the complete module."
        ),
        "input": prompt,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "workspace_source",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"source": {"type": "string"}},
                    "required": ["source"],
                },
            }
        },
    }
    response = JsonHttpClient("openai", timeout=60, retries=0).request(
        "POST",
        "https://api.openai.com/v1/responses",
        {
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        payload,
    )
    if response.get("status") != "completed":
        raise SystemExit("Generation incomplete; nothing installed")
    texts = [
        c["text"]
        for i in response["output"]
        if i["type"] == "message"
        for c in i["content"]
        if c["type"] == "output_text"
    ]
    if len(texts) != 1:
        raise SystemExit("Unexpected generation response")
    document = decode_json(texts[0], "openai")
    if set(document) != {"source"} or not isinstance(document["source"], str):
        raise SystemExit("Invalid source response")
    source = document["source"].encode()
    if len(source) > 200_000:
        raise SystemExit("Source exceeds target budget")
    compile(source, "app.py", "exec")  # Parse only; never execute model output on the host.
    original = destination / "original"
    original.mkdir(parents=True, exist_ok=True)
    (original / "app.py").write_bytes(source)
    (destination / "app.py").write_bytes(source)
    (original / "prompt.txt").write_text(prompt)
    provenance = {
        "source": "execution",
        "provider": "openai",
        "model": response.get("model", model),
        "request_id": response["id"],
        "generated_at": datetime.now(UTC).isoformat(),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "usage": response.get("usage", {}),
        "intent": "correctness-focused generation",
        "audited": False,
    }
    (original / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        json.dumps(
            {
                "bytes": len(source),
                "model": provenance["model"],
                "source_sha256": provenance["source_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
