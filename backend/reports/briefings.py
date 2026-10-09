"""Optional narration jobs bound to the exact current persisted evidence report."""

import asyncio
import hashlib
import json
from pathlib import Path

from backend.api.schemas import BriefingResponse, ReportResponse
from backend.reports.evidence import report_digest
from backend.reports.narrator import ElevenLabsClient, NarrationUnavailable
from backend.storage.runs import TERMINAL, RunStore


def saved_report(store: RunStore, run_id: str) -> ReportResponse:
    record = store.get(run_id)
    if record.run.status not in TERMINAL or record.run.source != "execution":
        raise ValueError("A completed execution report is required.")
    return ReportResponse(
        run_id=run_id,
        source=record.run.source,
        status=record.run.status,
        summary=f"Run {record.run.status}."
        + (f" Failure code: {record.failure_code}." if record.failure_code else ""),
        verification=record.run.verification,
        evidence=record.evidence,
        limitations=["Results cover only the frozen executed suites; not universal security."],
    )


class BriefingService:
    def __init__(self, store: RunStore, client: ElevenLabsClient | None):
        self.store, self.client = store, client
        self.tasks: dict[str, asyncio.Task] = {}
        self.errors: set[str] = set()

    def _identity(self, report):
        return self.client.identity(report)

    def media(self, artifact_id: str) -> tuple[Path, dict]:
        if not self.client:
            raise NarrationUnavailable("Narration is not configured.")
        audio, sidecar = self.client.artifact_paths(artifact_id)
        meta = json.loads(sidecar.read_text())
        report = saved_report(self.store, meta["run_id"])
        if meta["report_sha256"] != report_digest(report):
            raise ValueError("The audio belongs to an earlier report.")
        if meta["audio_sha256"] != hashlib.sha256(audio.read_bytes()).hexdigest():
            raise NarrationUnavailable("Saved audio integrity check failed.")
        return audio, meta

    def status(self, run_id: str) -> BriefingResponse:
        report = saved_report(self.store, run_id)
        digest = report_digest(report)
        result = BriefingResponse(run_id=run_id, report_sha256=digest, status="unavailable")
        if not self.client:
            return result
        identity = self._identity(report)
        if identity in self.tasks:
            return result.model_copy(update={"status": "generating"})
        if identity in self.errors:
            return result.model_copy(update={"status": "error"})
        try:
            _, meta = self.media(identity)
            return result.model_copy(
                update={
                    "status": "ready",
                    "artifact_id": identity,
                    "audio_path": f"/api/audio/{identity}",
                    "transcript": meta["transcript"],
                }
            )
        except (OSError, ValueError, KeyError, NarrationUnavailable):
            return result.model_copy(update={"status": "not_generated"})

    def generate(self, run_id: str, expected_digest: str) -> BriefingResponse:
        status = self.status(run_id)
        if status.report_sha256 != expected_digest:
            raise ValueError("Report changed before narration was requested.")
        if status.status in {"ready", "generating", "unavailable"}:
            return status
        if len(self.tasks) >= 2:
            raise ValueError("Narration capacity reached.")
        report = saved_report(self.store, run_id)
        identity = self._identity(report)
        self.errors.discard(identity)

        async def execute():
            try:
                await asyncio.to_thread(self.client.generate_incident_briefing, report)
            except Exception:
                self.errors.add(identity)
            finally:
                self.tasks.pop(identity, None)

        self.tasks[identity] = asyncio.create_task(execute())
        return status.model_copy(update={"status": "generating"})

    async def close(self):
        # Provider IO is bounded; do not start duplicate jobs by abandoning live workers.
        await asyncio.gather(*list(self.tasks.values()), return_exceptions=True)
