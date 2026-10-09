"""PLANNED source-grounded policy retrieval; no automatic organization creation."""

from typing import Protocol

from backend.providers.contracts import PolicySource, SecurityPolicy


class SensoPolicyStore(Protocol):
    def retrieve_security_policy(self, query: str) -> SecurityPolicy: ...

    def retrieve_policy_sources(self, policy_ids: list[str]) -> list[PolicySource]: ...
