"""PLANNED narration; only completed execution evidence may drive incident briefings."""

from typing import Protocol

from backend.api.schemas import ReportResponse
from backend.providers.contracts import AudioArtifact


class ElevenLabsNarrator(Protocol):
    def generate_incident_briefing(self, report: ReportResponse) -> AudioArtifact: ...
