import hashlib
import json

import pytest

from backend.providers.errors import ProviderError
from backend.providers.http import HttpResponse
from backend.providers.senso_client import ApprovedPolicyDocument, SensoPolicyStore

CONTENT = "11111111-1111-4111-8111-111111111111"
NODE = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
TEXT = "Only owners may read invoices."
DOCUMENT = ApprovedPolicyDocument(
    policy_id="authz",
    content_id=CONTENT,
    kb_node_id=NODE,
    revision=2,
    sha256=hashlib.sha256(TEXT.encode()).hexdigest(),
    authoritative=True,
)


def search():
    return {
        "results": [
            {"content_id": CONTENT, "kb_node_id": NODE, "version_id": VERSION, "chunk_text": TEXT}
        ]
    }


def detail():
    return {"id": CONTENT, "version_num": 2, "processing_status": "complete", "text": TEXT}


def store(search_response=None, content_response=None, documents=None):
    calls = []

    def transport(method, url, headers, body, timeout):
        calls.append((method, url, headers, body, timeout))
        response = (
            (search() if search_response is None else search_response)
            if method == "POST"
            else (detail() if content_response is None else content_response)
        )
        return HttpResponse(200, json.dumps(response).encode())

    client = SensoPolicyStore(
        approved_documents=documents or [DOCUMENT], api_key="secret", transport=transport
    )
    return client, calls


def test_retrieval_returns_full_pinned_authoritative_source():
    client, calls = store()
    policy = client.retrieve_security_policy("invoice authorization")
    assert policy.policy_ids == ["authz"]
    source = policy.sources[0]
    assert source.source_id == CONTENT and source.revision == "2"
    assert source.authoritative is True and source.text == TEXT
    assert calls[0][1] == "https://apiv2.senso.ai/api/v1/org/search/context"
    payload = json.loads(calls[0][3])
    assert payload["content_ids"] == [CONTENT] and payload["require_scoped_ids"] is True
    assert calls[0][2]["X-API-Key"] == "secret"
    assert calls[1][1].endswith(f"/org/kb/nodes/{NODE}/content?version=2")
    assert calls[1][0] == "GET"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"version_num": 3}, "policy_revision_mismatch"),
        ({"version_num": "2"}, "policy_revision_mismatch"),
        ({"processing_status": "processing"}, "policy_not_ready"),
        ({"text": ""}, "missing_policy_text"),
        ({"text": "Different policy."}, "policy_hash_mismatch"),
        ({"id": NODE}, "policy_revision_mismatch"),
    ],
)
def test_content_failures(change, code):
    client, _ = store(content_response={**detail(), **change})
    with pytest.raises(ProviderError, match=code):
        client.retrieve_policy_sources(["authz"])


@pytest.mark.parametrize(
    "response,code",
    [
        ({"results": []}, "missing_policy_sources"),
        ({"results": [{}]}, "invalid_response"),
        ({"results": [{**search()["results"][0], "content_id": NODE}]}, "unapproved_policy_source"),
        (
            {"results": [{**search()["results"][0], "kb_node_id": CONTENT}]},
            "unapproved_policy_source",
        ),
        (
            {"results": [{**search()["results"][0], "chunk_text": "Stale text."}]},
            "stale_policy_search",
        ),
    ],
)
def test_search_failures(response, code):
    client, _ = store(search_response=response)
    with pytest.raises(ProviderError, match=code):
        client.retrieve_security_policy("authz")


def test_conflicting_search_revisions():
    chunks = search()["results"]
    chunks.append({**chunks[0], "version_id": CONTENT})
    client, _ = store(search_response={"results": chunks})
    with pytest.raises(ProviderError, match="conflicting_policy_sources"):
        client.retrieve_security_policy("authz")


def test_development_memory_cannot_be_promoted_by_remote_flag():
    doc = DOCUMENT.model_copy(update={"authoritative": False})
    client, _ = store(content_response={**detail(), "authoritative": True}, documents=[doc])
    with pytest.raises(ProviderError, match="missing_authoritative_policy"):
        client.retrieve_security_policy("authz")


def test_unknown_policy_is_rejected_before_network():
    client, calls = store()
    with pytest.raises(ProviderError, match="unapproved_policy"):
        client.retrieve_policy_sources(["development-memory"])
    assert calls == []


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("SENSO_API_KEY", raising=False)
    client = SensoPolicyStore(approved_documents=[DOCUMENT])
    with pytest.raises(ProviderError, match="missing_credentials"):
        client.retrieve_security_policy("authz")


def test_traversal_in_node_configuration():
    document = DOCUMENT.model_copy(update={"kb_node_id": "../secret"})
    with pytest.raises(ValueError):
        SensoPolicyStore(approved_documents=[document])


def test_multiple_authoritative_documents_with_different_text_conflict():
    other_text = "All users may read invoices."
    other = DOCUMENT.model_copy(
        update={
            "content_id": "44444444-4444-4444-8444-444444444444",
            "kb_node_id": "55555555-5555-4555-8555-555555555555",
            "sha256": hashlib.sha256(other_text.encode()).hexdigest(),
        }
    )

    def transport(method, url, headers, body, timeout):
        if other.kb_node_id in url:
            response = {**detail(), "id": other.content_id, "text": other_text}
        else:
            response = detail()
        return HttpResponse(200, json.dumps(response).encode())

    client = SensoPolicyStore(
        approved_documents=[DOCUMENT, other], api_key="secret", transport=transport
    )
    with pytest.raises(ProviderError, match="conflicting_policy_sources"):
        client.retrieve_policy_sources(["authz"])
