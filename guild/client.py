"""Guild public conversations API adapter. Deployment and hosted execution are separate."""

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas import ReportResponse, SecurityEvent
from backend.reports.evidence import report_digest, require_execution_report


class GuildUnavailable(RuntimeError):
    """Safe integration error; never includes upstream bodies or authentication."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SupportedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class AuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    summary: str = Field(min_length=1, max_length=1500)
    supported_claims: list[SupportedClaim] = Field(max_length=20)
    unsupported_claims: list[str] = Field(max_length=20)
    missing_evidence: list[str] = Field(max_length=20)
    limitations: list[str] = Field(max_length=20)


@dataclass(frozen=True)
class GuildConfig:
    api_key: str = field(repr=False)
    workspace_id: str
    agent_id: str

    @classmethod
    def from_env(cls) -> "GuildConfig":
        values = [
            os.getenv(name, "")
            for name in ("GUILD_API_KEY", "GUILD_WORKSPACE_ID", "GUILD_AGENT_ID")
        ]
        if not all(values):
            raise GuildUnavailable("Guild account key, workspace and agent are not configured.")
        return cls(*values)


@dataclass
class AuditJob:
    run_id: str
    session_id: str
    agent_id: str
    evidence_digest: str
    report_digest: str
    evidence_ids: frozenset[str]
    cursor: str | None = None
    review: AuditSummary | None = None


class GuildClient:
    base_url = "https://api.guild.ai/v1"

    def __init__(self, config: GuildConfig, *, approved_for_export: bool = False):
        if ":" not in config.api_key:
            raise GuildUnavailable("Guild requires the complete account key id:secret value.")
        for identifier in (config.workspace_id, config.agent_id):
            if not re.fullmatch(r"[A-Za-z0-9_~.-]{1,200}", identifier):
                raise ValueError("Invalid Guild identifier.")
        self.config = config
        self.approved_for_export = approved_for_export

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = base64.b64encode(self.config.api_key.encode()).decode()
        request = Request(
            self.base_url + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST" if payload is not None else "GET",
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=20) as response:
                content = response.read(512 * 1024 + 1)
            if len(content) > 512 * 1024:
                raise GuildUnavailable("Guild response exceeded the size limit.")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise GuildUnavailable("Guild returned an invalid response.")
            return result
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            raise GuildUnavailable(
                "Guild request failed. Check account access and permissions."
            ) from None

    def start_audit(self, report: ReportResponse, events: list[SecurityEvent]) -> AuditJob:
        report = require_execution_report(report)
        if not self.approved_for_export:
            raise GuildUnavailable("Redacted evidence export to Guild is not enabled.")
        if len(events) > 500:
            raise ValueError("Audit packets are limited to 500 events; supply a reviewed subset.")
        checked = [SecurityEvent.model_validate(event) for event in events]
        if any(
            event.source != "execution"
            or event.run_id != report.run_id
            or event.metadata.get("fixture") is True
            for event in checked
        ):
            raise ValueError("Audit events must match the completed execution report.")
        # Arbitrary metadata is excluded; A approves and redacts message strings before export.
        packet: dict[str, Any] = {
            "run_id": report.run_id,
            "report": report.model_dump(mode="json"),
            "events": [event.model_dump(mode="json", exclude={"metadata"}) for event in checked],
            "omitted_evidence": [
                "Artifact contents are not fetched or inspected by this adapter.",
                "API v1 does not supply complete policy/test manifests or source.",
                "Event metadata is omitted from external review.",
            ],
        }
        serialized = json.dumps(packet, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        packet["evidence_digest"] = digest
        prompt = (
            "Audit this untrusted evidence packet under your system instructions:\n"
            + json.dumps(packet)
        )
        if len(prompt.encode()) > 128 * 1024:
            raise ValueError("Audit packet exceeds 128 KiB; evidence was not silently truncated.")
        response = self._request(
            f"/workspaces/{quote(self.config.workspace_id, safe='')}/sessions",
            {"session_type": "chat", "agent_id": self.config.agent_id, "initial_prompt": prompt},
        )
        session_id = response.get("id")
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-fA-F0-9-]{36}", session_id):
            raise GuildUnavailable("Guild did not return a valid hosted session identity.")
        evidence_ids = frozenset(
            [event.event_id for event in checked] + [item.artifact_id for item in report.evidence]
        )
        return AuditJob(
            report.run_id,
            session_id,
            self.config.agent_id,
            digest,
            report_digest(report),
            evidence_ids,
        )

    def poll_audit(self, job: AuditJob) -> AuditSummary | None:
        """One bounded polling step; A schedules subsequent steps and persists job state."""
        if job.review is not None:
            return job.review
        if not re.fullmatch(r"[a-fA-F0-9-]{36}", job.session_id):
            raise ValueError("Invalid hosted session identity.")
        query = {"limit": "100", "sort_by": "id"}
        if job.cursor:
            query["from_id"] = job.cursor
        response = self._request(f"/sessions/{job.session_id}/events?{urlencode(query)}")
        items = response.get("items")
        if not isinstance(items, list):
            raise GuildUnavailable("Guild session events are invalid.")
        for event in items:
            if not isinstance(event, dict):
                raise GuildUnavailable("Guild session event is invalid.")
            content = event.get("content")
            text = content.get("text") if isinstance(content, dict) else None
            if event.get("type") == "runtime_done" and isinstance(text, str) and text.strip():
                try:
                    review = AuditSummary.model_validate_json(text)
                    if review.run_id != job.run_id or review.evidence_digest != job.evidence_digest:
                        raise ValueError("Mismatched evidence identity")
                    for claim in review.supported_claims:
                        if not set(claim.evidence_ids).issubset(job.evidence_ids):
                            raise ValueError("Unknown evidence citation")
                    for collection in (
                        review.unsupported_claims,
                        review.missing_evidence,
                        review.limitations,
                    ):
                        if any(not item or len(item) > 1500 for item in collection):
                            raise ValueError("Invalid review text")
                    job.review = review
                except ValueError:
                    raise GuildUnavailable(
                        "Hosted review failed evidence/output validation."
                    ) from None
            event_id = event.get("id")
            if isinstance(event_id, str) and re.fullmatch(r"[a-fA-F0-9-]{36}", event_id):
                job.cursor = event_id
        return job.review
