"""Validate trusted policy designation and report missing/conflicting sources."""

from pydantic import ValidationError

from backend.providers.contracts import SecurityPolicy
from backend.providers.errors import ProviderError


def validate_policy(policy: SecurityPolicy, provider: str) -> SecurityPolicy:
    try:
        policy = SecurityPolicy.model_validate(policy.model_dump(), strict=True)
    except (ValidationError, AttributeError):
        raise ProviderError(provider, "invalid_policy") from None
    if (
        not policy.policy_ids
        or len(policy.policy_ids) > 20
        or len(policy.sources) > 40
        or len(set(policy.policy_ids)) != len(policy.policy_ids)
    ):
        raise ProviderError(provider, "invalid_policy")
    source_ids = {}
    for source in policy.sources:
        try:
            text_size = len(source.text.encode())
        except UnicodeError:
            raise ProviderError(provider, "invalid_policy") from None
        if (
            source.policy_id not in policy.policy_ids
            or not source.revision.strip()
            or len(source.revision) > 128
            or not source.text.strip()
            or text_size > 100_000
        ):
            raise ProviderError(provider, "invalid_policy")
        designation = (source.policy_id, source.revision, source.text, source.authoritative)
        if source.source_id in source_ids and source_ids[source.source_id] != designation:
            raise ProviderError(provider, "conflicting_policy_sources")
        source_ids[source.source_id] = designation
    for policy_id in policy.policy_ids:
        sources = [s for s in policy.sources if s.policy_id == policy_id and s.authoritative]
        if not sources:
            raise ProviderError(provider, "missing_authoritative_policy")
        # Conservative: multiple differently worded sources require trusted resolution.
        if len({s.text.strip() for s in sources}) > 1:
            raise ProviderError(provider, "conflicting_policy_sources")
    return policy
