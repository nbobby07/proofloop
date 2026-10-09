"""Provider DTOs for coordinating integrations, without implementing them."""

from backend.api.schemas import ContractModel, Finding, Identifier, JsonValue


class SourceSnapshot(ContractModel):
    snapshot_id: Identifier
    files: dict[str, str]


class PolicySource(ContractModel):
    policy_id: Identifier
    source_id: Identifier
    revision: str
    text: str
    authoritative: bool


class SecurityPolicy(ContractModel):
    policy_ids: list[Identifier]
    sources: list[PolicySource]


class ChallengeSpec(ContractModel):
    challenge_id: Identifier
    family: str
    target_id: Identifier
    policy_ids: list[Identifier]
    parameters: dict[str, JsonValue]
    # Parameters select allowlisted test templates, never shell commands or free-form code.


class ChallengeResult(ContractModel):
    challenge_id: Identifier
    outcome: str
    evidence_ids: list[Identifier]


class ScanResult(ContractModel):
    findings: list[Finding]
    scanner_version: str
    ruleset_hash: str
    complete: bool


class AnalyticsFilters(ContractModel):
    run_id: Identifier | None = None


class AudioArtifact(ContractModel):
    artifact_id: Identifier
    media_type: str
    evidence_run_id: Identifier
