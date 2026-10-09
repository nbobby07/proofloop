import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from backend.api.main import app
from backend.api.schemas import RunResponse, SecurityEvent, VerificationSummary

REPO = Path(__file__).resolve().parents[2]


def load_contract(name):
    return json.loads((REPO / "contracts" / name).read_text(encoding="utf-8"))


def test_example_run_is_explicitly_fixture_data():
    raw = load_contract("example-run.json")
    run = RunResponse.model_validate(raw)
    assert run.source == "fixture"
    assert all(event.source == "fixture" for event in run.events)
    Draft202012Validator(load_contract("run.schema.json"), format_checker=FormatChecker()).validate(
        raw
    )


def test_event_schema_matches_pydantic():
    schema = load_contract("events.schema.json")
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **SecurityEvent.model_json_schema(),
    }
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for event in load_contract("example-run.json")["events"]:
        validator.validate(event)


def test_openapi_is_current_and_has_all_routes():
    assert load_contract("openapi.json") == app.openapi()
    assert set(app.openapi()["paths"]) == {
        "/api/health",
        "/api/runs",
        "/api/runs/{run_id}",
        "/api/runs/{run_id}/events",
        "/api/runs/{run_id}/report",
        "/api/runs/{run_id}/challenge",
        "/api/analytics",
    }


def test_counts_cannot_exceed_total():
    counts = load_contract("example-run.json")["verification"]
    counts["security_passed"] = counts["security_total"] + 1
    with pytest.raises(ValidationError):
        VerificationSummary.model_validate(counts)


def test_fixture_events_cannot_be_attached_to_execution_runs():
    raw = load_contract("example-run.json")
    raw["source"] = "execution"
    with pytest.raises(ValidationError):
        RunResponse.model_validate(raw)


def test_event_timestamp_requires_timezone():
    event = load_contract("example-run.json")["events"][0]
    event["timestamp"] = "2026-10-09T11:00:00"
    with pytest.raises(ValidationError):
        SecurityEvent.model_validate(event)


def test_env_example_contains_no_credentials():
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and (key.endswith("_KEY") or key.endswith("_PASSWORD")):
            assert not value.strip(), f"Credential placeholder must be blank: {key}"
