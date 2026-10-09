"""PLANNED defender adapter; backend-only credentials and validated proposals."""

from typing import Protocol

from backend.api.schemas import Finding, PatchProposal
from backend.providers.contracts import SourceSnapshot


class OpenAIDefender(Protocol):
    def generate_patch(
        self, source: SourceSnapshot, finding: Finding, feedback: list[str]
    ) -> PatchProposal: ...
