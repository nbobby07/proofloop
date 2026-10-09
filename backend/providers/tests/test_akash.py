import json

import pytest

from backend.providers.akash_client import AkashAttacker, ChallengeTemplate
from backend.providers.contracts import ChallengeResult, PolicySource, SecurityPolicy
from backend.providers.errors import ProviderError
from backend.providers.http import HttpResponse

POLICY = SecurityPolicy(
    policy_ids=["authz"],
    sources=[
        PolicySource(
            policy_id="authz",
            source_id="approved-policy",
            revision="1",
            text="Only account owners may read an invoice.",
            authoritative=True,
        )
    ],
)
TEMPLATE = ChallengeTemplate(
    family="invoice_authorization",
    policy_ids=["authz"],
    parameter_sets=[{"actor": "other_user", "invoice": 1}],
)
SPEC = {
    "challenge_id": "new-1",
    "family": "invoice_authorization",
    "target_id": "LedgerLite",
    "policy_ids": ["authz"],
    "parameters": {"actor": "other_user", "invoice": 1},
}


def attacker(specs=None, response=None):
    calls = []
    body = (
        response
        if response is not None
        else {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": json.dumps({"challenges": [SPEC] if specs is None else specs}),
                    },
                }
            ]
        }
    )

    def transport(*args):
        calls.append(args)
        return HttpResponse(200, json.dumps(body).encode())

    return AkashAttacker(
        approved_targets={"LedgerLite": [TEMPLATE]},
        api_key="secret",
        model="configured-model",
        transport=transport,
    ), calls


def test_valid_proposals_use_bounded_schema_and_never_execute():
    client, calls = attacker()
    specs = client.generate_challenges("LedgerLite", POLICY, [])
    assert specs[0].model_dump() == SPEC
    assert calls[0][1] == "https://api.akashml.com/v1/chat/completions"
    payload = json.loads(calls[0][3])
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["max_tokens"] == 4096 and "tools" not in payload
    assert (
        payload["response_format"]["json_schema"]["schema"]["properties"]["challenges"]["maxItems"]
        == 2
    )
    assert "verdict" not in specs[0].model_dump()


@pytest.mark.parametrize(
    "change",
    [
        {"target_id": "unauthorized"},
        {"family": "shell"},
        {"policy_ids": []},
        {"policy_ids": ["memory"]},
        {"policy_ids": ["authz", "authz"]},
        {"parameters": {"command": "anything"}},
        {"parameters": {"actor": "other_user", "invoice": True}},
        {"parameters": {"actor": "other_user", "invoice": 999}},
        {"outcome": "successful_attack"},
    ],
)
def test_unsafe_specs(change):
    client, _ = attacker([{**SPEC, **change}])
    with pytest.raises(ProviderError):
        client.generate_challenges("LedgerLite", POLICY, [])


@pytest.mark.parametrize("specs", [[], [SPEC] * 3, [SPEC, SPEC]])
def test_count_and_duplicate_bounds(specs):
    client, _ = attacker(specs)
    with pytest.raises(ProviderError):
        client.generate_challenges("LedgerLite", POLICY, [])


def test_previous_challenge_cannot_be_reused():
    client, _ = attacker()
    with pytest.raises(ProviderError, match="duplicate_challenge_id"):
        client.generate_challenges(
            "LedgerLite",
            POLICY,
            [
                ChallengeResult(
                    challenge_id="new-1", outcome="failed", evidence_ids=["actual-execution"]
                )
            ],
        )


def test_target_and_policy_are_validated_before_network():
    client, calls = attacker()
    with pytest.raises(ProviderError, match="unapproved_target"):
        client.generate_challenges("https://remote", POLICY, [])
    policy = POLICY.model_copy(deep=True)
    policy.sources[0].authoritative = False
    with pytest.raises(ProviderError, match="missing_authoritative_policy"):
        client.generate_challenges("LedgerLite", policy, [])
    assert calls == []


def test_policy_conflicts_block_requests():
    client, calls = attacker()
    policy = POLICY.model_copy(deep=True)
    policy.sources.append(
        PolicySource(
            policy_id="authz",
            source_id="conflicting",
            revision="1",
            text="Everyone may read invoices.",
            authoritative=True,
        )
    )
    with pytest.raises(ProviderError, match="conflicting_policy_sources"):
        client.generate_challenges("LedgerLite", policy, [])
    assert calls == []


@pytest.mark.parametrize(
    "response,code",
    [
        ({"choices": [{"finish_reason": "length"}]}, "incomplete_response"),
        ({"choices": []}, "incomplete_response"),
        (
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "refusal": "secret"}}
                ]
            },
            "refused",
        ),
        (
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"role": "assistant", "tool_calls": [{}]}}
                ]
            },
            "unexpected_output",
        ),
    ],
)
def test_nonfinal_or_executable_outputs(response, code):
    client, _ = attacker(response=response)
    with pytest.raises(ProviderError, match=code):
        client.generate_challenges("LedgerLite", POLICY, [])


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("AKASH_API_KEY", raising=False)
    client = AkashAttacker(approved_targets={"LedgerLite": [TEMPLATE]})
    with pytest.raises(ProviderError, match="missing_credentials"):
        client.generate_challenges("LedgerLite", POLICY, [])


@pytest.mark.parametrize(
    "parameters",
    [
        {"command": "bad"},
        {"count": 10001},
        {"actor": "x" * 257},
        {"nested": {"code": "bad"}},
        {"count": 1.5},
    ],
)
def test_invalid_trusted_template_config(parameters):
    template = TEMPLATE.model_copy(update={"parameter_sets": [parameters]})
    with pytest.raises(ValueError):
        AkashAttacker(approved_targets={"LedgerLite": [template]})


def test_malformed_message_fails_safely():
    client, _ = attacker(response={"choices": [{"finish_reason": "stop", "message": 42}]})
    with pytest.raises(ProviderError, match="invalid_response"):
        client.generate_challenges("LedgerLite", POLICY, [])
