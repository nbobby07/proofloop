"""Stable narration protocol. Concrete REST implementation is in narrator.py."""

from typing import Protocol

from backend.api.schemas import ReportResponse
from backend.providers.contracts import AudioArtifact


class ElevenLabsNarrator(Protocol):
    def generate_incident_briefing(self, report: ReportResponse) -> AudioArtifact: ...
