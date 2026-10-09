"""Content-addressed private evidence artifacts; references never disclose host paths."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from backend.api.schemas import EvidenceReference


class EvidenceStore:
    def __init__(self, root: Path, secrets: tuple[str, ...] = ()):
        self.root = root
        self.secrets = tuple(value for value in secrets if value)

    def _redact(self, value):
        if isinstance(value, str):
            for secret in self.secrets:
                value = value.replace(secret, "[REDACTED]")
            return value
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact(item) for item in value]
        return value

    def save(self, payload: dict, description: str) -> EvidenceReference:
        data = json.dumps(
            self._redact(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        sha = hashlib.sha256(data).hexdigest()
        artifact_id = f"evidence_{sha}"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix=".evidence-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / f"{artifact_id}.json")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return EvidenceReference(artifact_id=artifact_id, sha256=sha, description=description)

    def read(self, reference: EvidenceReference) -> dict:
        if reference.artifact_id != f"evidence_{reference.sha256}":
            raise ValueError("Invalid artifact identity")
        data = (self.root / f"{reference.artifact_id}.json").read_bytes()
        if hashlib.sha256(data).hexdigest() != reference.sha256:
            raise ValueError("Evidence integrity failure")
        return json.loads(data)
