"""Workspace admission and evidence integrity; no candidate code executes in CI."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sandbox.workspace.protocol import Action, Case, Proposals, category, frozen_cases, sha
from sandbox.workspace.runner import make_job, parse_receipt, validate_receipt


def proposal():
    return {
        "challenges": [
            {
                "id": "foreign_read",
                "family": "tenant_isolation",
                "rationale": "Read another tenant",
                "actions": [{"actor": "alice", "operation": "read", "invoice_id": 201}],
            }
        ]
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "https://example.com"),
        ("code", "print(1)"),
        ("shell", "true"),
        ("expected_status", 200),
        ("tenant", 2),
    ],
)
def test_model_cannot_choose_destination_code_or_oracle(field, value):
    document = proposal()
    document["challenges"][0]["actions"][0][field] = value
    with pytest.raises(ValidationError):
        Proposals.model_validate(document)


@pytest.mark.parametrize(
    "changes",
    [
        {"actor": "admin"},
        {"invoice_id": True},
        {"invoice_id": -1},
        {"query": "x" * 121},
        {"invoice_ids": [False]},
        {"page_size": 100},
        {"operation": "execute"},
    ],
)
def test_request_grammar_is_bounded(changes):
    with pytest.raises(ValidationError):
        Action.model_validate({"actor": "alice", "operation": "read", **changes})


def test_sequences_ids_and_export_references():
    document = proposal()
    document["challenges"] *= 2
    with pytest.raises(ValidationError):
        Proposals.model_validate(document)
    document = proposal()
    document["challenges"][0]["actions"] *= 9
    with pytest.raises(ValidationError):
        Proposals.model_validate(document)
    document = proposal()
    document["challenges"][0]["actions"][0]["operation"] = "download"
    with pytest.raises(ValidationError):
        Proposals.model_validate(document)


def receipt():
    cases = [c.model_dump() for c in frozen_cases()[:2]]
    job = make_job("a" * 64, cases, "baseline")
    tests = [
        {
            "test_id": c["id"],
            "category": category(Case.model_validate(c)),
            "family": c["family"],
            "passed": True,
            "steps": [
                {"step": i, "passed": True, "observed_status": 200}
                for i, _ in enumerate(c["actions"])
            ],
        }
        for c in cases
    ]
    return job, {
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "suite_sha256": sha(cases),
        "results": [{**job["targets"][0], "tests": tests}],
    }


@pytest.mark.parametrize(
    "change",
    ["nonce", "suite", "source", "missing", "duplicate", "outcome", "missing_http", "category"],
)
def test_receipts_fail_closed(change):
    job, result = receipt()
    tests = result["results"][0]["tests"]
    if change == "nonce":
        result["nonce"] = "stale"
    if change == "suite":
        result["suite_sha256"] = "b" * 64
    if change == "source":
        result["results"][0]["source_sha256"] = "b" * 64
    if change == "missing":
        tests.pop()
    if change == "duplicate":
        tests[1] = copy.deepcopy(tests[0])
    if change == "outcome":
        tests[0]["steps"][0]["passed"] = False
    if change == "missing_http":
        tests[0]["steps"][0]["observed_status"] = None
    if change == "category":
        tests[0]["category"] = "security"
    with pytest.raises(ValueError):
        validate_receipt(result, job)


def test_single_complete_receipt_only():
    job, result = receipt()
    line = "PROOFLOOP_RECEIPT=" + json.dumps(result)
    assert parse_receipt(line, job) == result
    for raw in ("", line + "\n" + line):
        with pytest.raises(ValueError):
            parse_receipt(raw, job)


def test_original_generation_is_immutable_and_correctness_focused():
    root = Path(__file__).resolve().parents[2] / "demo_target/ledgerlite_workspace"
    source = (root / "original/app.py").read_bytes()
    provenance = json.loads((root / "original/provenance.json").read_text())
    assert hashlib.sha256(source).hexdigest() == provenance["source_sha256"]
    assert (root / "app.py").read_bytes() == source
    assert b"Do not deliberately introduce bugs" in (root / "original/prompt.txt").read_bytes()
    cases = frozen_cases()
    assert len(cases) == len({c.id for c in cases})
    assert {category(c) for c in cases} == {"security", "functional", "adversarial"}
