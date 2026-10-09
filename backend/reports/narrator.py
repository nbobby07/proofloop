"""Official ElevenLabs REST adapter with evidence-bound, local MP3 caching."""

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from backend.api.schemas import ReportResponse
from backend.providers.contracts import AudioArtifact
from backend.reports.evidence import (
    SCRIPT_VERSION,
    briefing_script,
    report_digest,
    require_execution_report,
)


class NarrationUnavailable(RuntimeError):
    """Safe provider error without credentials or remote response bodies."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class NarrationConfig:
    api_key: str = field(repr=False)
    voice_id: str
    model_id: str = "eleven_multilingual_v2"

    @classmethod
    def from_env(cls) -> "NarrationConfig":
        key, voice = os.getenv("ELEVENLABS_API_KEY", ""), os.getenv("ELEVENLABS_VOICE_ID", "")
        if not key or not voice:
            raise NarrationUnavailable("ElevenLabs key and voice are not configured.")
        return cls(key, voice, os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"))


class ElevenLabsClient:
    def __init__(
        self,
        config: NarrationConfig,
        artifact_directory: Path,
        *,
        approved_for_export: bool = False,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", config.voice_id):
            raise ValueError("Invalid ElevenLabs voice identifier.")
        self.config = config
        self.directory = artifact_directory.resolve()
        self.approved_for_export = approved_for_export

    def _atomic_write(self, destination: Path, content: bytes) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=self.directory, prefix=".briefing-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def identity(self, report: ReportResponse) -> str:
        identity = json.dumps(
            [
                report_digest(report),
                self.config.voice_id,
                self.config.model_id,
                f"script-{SCRIPT_VERSION}",
            ]
        )
        return "briefing_" + hashlib.sha256(identity.encode()).hexdigest()

    def generate_incident_briefing(self, report: ReportResponse) -> AudioArtifact:
        report = require_execution_report(report)
        if not self.approved_for_export:
            raise NarrationUnavailable("Redacted report export to ElevenLabs is not enabled.")
        script = briefing_script(report)
        if len(script) > 10000:
            raise NarrationUnavailable("Briefing exceeds the bounded narration input size.")
        digest = report_digest(report)
        artifact_id = self.identity(report)
        audio_path = self.directory / f"{artifact_id}.mp3"
        metadata_path = self.directory / f"{artifact_id}.json"
        if any(path.is_symlink() for path in (audio_path, metadata_path)):
            raise NarrationUnavailable("Briefing cache paths must not be symlinks.")
        try:
            if audio_path.exists() and metadata_path.exists():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if (
                    metadata.get("report_sha256") == digest
                    and metadata.get("audio_sha256")
                    == hashlib.sha256(audio_path.read_bytes()).hexdigest()
                ):
                    return AudioArtifact(
                        artifact_id=artifact_id,
                        media_type="audio/mpeg",
                        evidence_run_id=report.run_id,
                    )
        except (OSError, ValueError):
            pass
        request = Request(
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.config.voice_id}?output_format=mp3_44100_128",
            data=json.dumps({"text": script, "model_id": self.config.model_id}).encode(),
            headers={
                "xi-api-key": self.config.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=30) as response:
                if response.headers.get_content_type() not in {"audio/mpeg", "audio/mp3"}:
                    raise NarrationUnavailable("ElevenLabs returned an unexpected media type.")
                audio = response.read(8 * 1024 * 1024 + 1)
                if not audio or len(audio) > 8 * 1024 * 1024:
                    raise NarrationUnavailable(
                        "ElevenLabs audio was empty or exceeded its size limit."
                    )
        except (HTTPError, URLError, TimeoutError, OSError):
            raise NarrationUnavailable(
                "ElevenLabs audio generation failed; evidence is unaffected."
            ) from None
        metadata = {
            "artifact_id": artifact_id,
            "run_id": report.run_id,
            "source": "execution",
            "report_sha256": digest,
            "audio_sha256": hashlib.sha256(audio).hexdigest(),
            "voice_id": self.config.voice_id,
            "model_id": self.config.model_id,
            "transcript": script,
            "script_version": SCRIPT_VERSION,
        }
        self._atomic_write(audio_path, audio)
        self._atomic_write(metadata_path, json.dumps(metadata, indent=2).encode())
        return AudioArtifact(
            artifact_id=artifact_id, media_type="audio/mpeg", evidence_run_id=report.run_id
        )

    def artifact_paths(self, artifact_id: str) -> tuple[Path, Path]:
        """For A's allowlisted media route; never accept a client-supplied host path."""
        if not re.fullmatch(r"briefing_[a-f0-9]{64}", artifact_id):
            raise ValueError("Invalid briefing artifact id.")
        paths = tuple(self.directory / f"{artifact_id}.{ext}" for ext in ("mp3", "json"))
        if any(
            path.is_symlink() or path.resolve().parent != self.directory or not path.is_file()
            for path in paths
        ):
            raise NarrationUnavailable("Saved briefing artifact is unavailable.")
        return paths
