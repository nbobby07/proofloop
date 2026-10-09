"""Senso REST policy retrieval from explicitly approved, revision-pinned KB documents.

Authority comes from trusted application configuration, never Senso search rank,
editorial status, a model answer, or development memory. No ingestion or writes.
"""

import hashlib
import os
import re
from collections.abc import Sequence
from uuid import UUID

from pydantic import Field, ValidationError

from backend.api.schemas import ContractModel, Identifier
from backend.providers.contracts import PolicySource, SecurityPolicy
from backend.providers.errors import ProviderError
from backend.providers.http import JsonHttpClient, Transport, https_request
from backend.providers.policy_validation import validate_policy

BASE_URL = "https://apiv2.senso.ai/api/v1"


class ApprovedPolicyDocument(ContractModel):
    policy_id: Identifier
    content_id: Identifier
    kb_node_id: Identifier
    revision: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authoritative: bool


class SensoPolicyStore:
    def __init__(
        self,
        *,
        approved_documents: Sequence[ApprovedPolicyDocument],
        api_key: str | None = None,
        timeout: float = 20,
        retries: int = 1,
        transport: Transport = https_request,
    ):
        if not 1 <= len(approved_documents) <= 20:
            raise ValueError("1..20 explicitly approved policy documents required")
        self._documents = tuple(
            ApprovedPolicyDocument.model_validate(d.model_dump(), strict=True)
            for d in approved_documents
        )
        if len({d.content_id for d in self._documents}) != len(self._documents):
            raise ValueError("A content ID must have exactly one policy designation")
        if len({d.kb_node_id for d in self._documents}) != len(self._documents):
            raise ValueError("A KB node must have exactly one policy designation")
        for doc in self._documents:
            for identifier in [doc.content_id, doc.kb_node_id]:
                try:
                    if str(UUID(identifier)) != identifier:
                        raise ValueError
                except ValueError:
                    raise ValueError("Senso content and node IDs must be canonical UUIDs") from None
        self._api_key = api_key if api_key is not None else os.getenv("SENSO_API_KEY")
        self.http = JsonHttpClient("senso", timeout=timeout, retries=retries, transport=transport)

    def _headers(self):
        if not self._api_key:
            raise ProviderError("senso", "missing_credentials")
        return {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
            "X-Senso-Signals": "off",
        }

    def retrieve_security_policy(self, query: str) -> SecurityPolicy:
        if type(query) is not str or not query.strip() or len(query) > 2000:
            raise ProviderError("senso", "invalid_query")
        by_content = {d.content_id: d for d in self._documents}
        response = self.http.request(
            "POST",
            BASE_URL + "/org/search/context",
            self._headers(),
            {
                "query": query,
                "max_results": 20,
                "content_ids": list(by_content),
                "require_scoped_ids": True,
            },
        )
        try:
            chunks = response["results"]
            if not isinstance(chunks, list) or len(chunks) > 20:
                raise ProviderError("senso", "invalid_response")
            if not chunks:
                raise ProviderError("senso", "missing_policy_sources")
            versions = {}
            policy_ids = set()
            for chunk in chunks:
                doc = by_content.get(chunk["content_id"])
                if doc is None or chunk["kb_node_id"] != doc.kb_node_id:
                    raise ProviderError("senso", "unapproved_policy_source")
                version_id = chunk["version_id"]
                if not isinstance(version_id, str) or not re.fullmatch(
                    r"[A-Za-z0-9_-]{1,128}", version_id
                ):
                    raise ProviderError("senso", "invalid_response")
                if doc.content_id in versions and versions[doc.content_id] != version_id:
                    raise ProviderError("senso", "conflicting_policy_sources")
                versions[doc.content_id] = version_id
                if type(chunk["chunk_text"]) is not str or not chunk["chunk_text"].strip():
                    raise ProviderError("senso", "invalid_response")
                policy_ids.add(doc.policy_id)
            sources = self.retrieve_policy_sources(sorted(policy_ids))
            source_texts = {s.source_id: s.text for s in sources}
            if any(
                chunk["chunk_text"] not in source_texts[chunk["content_id"]] for chunk in chunks
            ):
                raise ProviderError("senso", "stale_policy_search")
            return validate_policy(
                SecurityPolicy(policy_ids=sorted(policy_ids), sources=sources), "senso"
            )
        except (KeyError, TypeError, AttributeError, ValidationError):
            raise ProviderError("senso", "invalid_response") from None

    def retrieve_policy_sources(self, policy_ids: list[str]) -> list[PolicySource]:
        if (
            not policy_ids
            or len(policy_ids) > 20
            or len(set(policy_ids)) != len(policy_ids)
            or not set(policy_ids) <= {d.policy_id for d in self._documents}
        ):
            raise ProviderError("senso", "unapproved_policy")
        sources = []
        for doc in self._documents:
            if doc.policy_id not in policy_ids:
                continue
            response = self.http.request(
                "GET",
                f"{BASE_URL}/org/kb/nodes/{doc.kb_node_id}/content?version={doc.revision}",
                self._headers(),
            )
            try:
                if (
                    response["id"] != doc.content_id
                    or type(response["version_num"]) is not int
                    or response["version_num"] != doc.revision
                ):
                    raise ProviderError("senso", "policy_revision_mismatch")
                if response["processing_status"] != "complete":
                    raise ProviderError("senso", "policy_not_ready")
                text = response["text"]
                if type(text) is not str or not text.strip() or len(text.encode()) > 100_000:
                    raise ProviderError("senso", "missing_policy_text")
                if hashlib.sha256(text.encode()).hexdigest() != doc.sha256:
                    raise ProviderError("senso", "policy_hash_mismatch")
                sources.append(
                    PolicySource(
                        policy_id=doc.policy_id,
                        source_id=doc.content_id,
                        revision=str(doc.revision),
                        text=text,
                        authoritative=doc.authoritative,
                    )
                )
            except (KeyError, TypeError, UnicodeError, ValidationError):
                raise ProviderError("senso", "invalid_response") from None
        return validate_policy(
            SecurityPolicy(policy_ids=policy_ids, sources=sources), "senso"
        ).sources
