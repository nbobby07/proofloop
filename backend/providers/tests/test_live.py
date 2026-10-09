"""Explicit opt-in network checks; never required in credential-free CI."""

import json
import os

import pytest

from backend.api.schemas import Finding
from backend.providers.akash_client import AkashAttacker, ChallengeTemplate
from backend.providers.contracts import PolicySource, SecurityPolicy, SourceSnapshot
from backend.providers.openai_client import OpenAIDefender
from backend.providers.senso_client import ApprovedPolicyDocument, SensoPolicyStore


@pytest.mark.skipif(os.getenv("PROOFLOOP_LIVE_OPENAI") != "1", reason="Opt-in paid OpenAI call")
def test_live_openai():
    # Synthetic source is caller-approved test input, not a fake provider response.
    source = SourceSnapshot(
        snapshot_id="live-adapter-check",
        files={
            "app.py": (
                "def lookup(db, value):\n"
                '    return db.execute(f"SELECT * FROM invoices WHERE id = {value}")\n'
            )
        },
    )
    client = OpenAIDefender(allowed_files={"app.py"}, retries=0)
    result = client.generate_patch(
        source, Finding(id="live-sql", title="SQL string interpolation", severity="high"), []
    )
    assert result.attempt == 1 and result.diff


@pytest.mark.skipif(os.getenv("PROOFLOOP_LIVE_AKASH") != "1", reason="Opt-in paid AkashML call")
def test_live_akash():
    policy = SecurityPolicy(
        policy_ids=["authz"],
        sources=[
            PolicySource(
                policy_id="authz",
                source_id="approved-adapter-test",
                revision="1",
                text="Only invoice owners may view invoices.",
                authoritative=True,
            )
        ],
    )
    template = ChallengeTemplate(
        family="invoice_authorization",
        policy_ids=["authz"],
        parameter_sets=[{"actor": "other_user", "invoice": 1}],
    )
    client = AkashAttacker(approved_targets={"LedgerLite": [template]}, retries=0)
    assert client.generate_challenges("LedgerLite", policy, [])


@pytest.mark.skipif(
    os.getenv("PROOFLOOP_LIVE_SENSO") != "1", reason="Opt-in approved Senso retrieval"
)
def test_live_senso():
    # Trusted operator supplies existing KB IDs, revisions and exact approved text hashes.
    documents = [
        ApprovedPolicyDocument.model_validate(d)
        for d in json.loads(os.environ["SENSO_APPROVED_DOCUMENTS_JSON"])
    ]
    client = SensoPolicyStore(approved_documents=documents, retries=0)
    assert client.retrieve_security_policy(os.environ["SENSO_POLICY_QUERY"]).sources
