"""PLANNED OpenAI-compatible adapter: https://api.akashml.com/v1."""

from typing import Protocol

from backend.providers.contracts import ChallengeResult, ChallengeSpec, SecurityPolicy


class AkashAttacker(Protocol):
    def generate_challenges(
        self, target: str, policy: SecurityPolicy, previous_results: list[ChallengeResult]
    ) -> list[ChallengeSpec]: ...
