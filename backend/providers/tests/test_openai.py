import json

import pytest

from backend.api.schemas import Finding
from backend.providers.contracts import SourceSnapshot
from backend.providers.errors import ProviderError
from backend.providers.http import HttpResponse
from backend.providers.openai_client import OpenAIDefender
from backend.providers.patch_validation import validate_patch

SOURCE = SourceSnapshot(snapshot_id="approved-1", files={"app.py": "query = 'unsafe'\n"})
FINDING = Finding(id="sql-injection", title="SQL injection", severity="high")
DIFF = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-query = 'unsafe'\n+query = 'bound'\n"


def completed(proposal=None):
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            proposal if proposal is not None else {"attempt": 1, "diff": DIFF}
                        ),
                    }
                ],
            }
        ],
    }


def defender(response, **kwargs):
    calls = []

    def transport(*args):
        calls.append(args)
        return HttpResponse(200, json.dumps(response).encode())

    return OpenAIDefender(
        allowed_files={"app.py"},
        api_key="test-secret",
        model="configured-model",
        transport=transport,
        **kwargs,
    ), calls


def test_valid_proposal_uses_strict_responses_and_preserves_snapshot():
    client, calls = defender(completed())
    proposal = client.generate_patch(SOURCE, FINDING, ["Previous security check failed"])
    assert proposal.diff == DIFF
    method, url, headers, body, timeout = calls[0]
    assert (method, url) == ("POST", "https://api.openai.com/v1/responses")
    payload = json.loads(body)
    assert payload["store"] is False and "tools" not in payload
    assert payload["text"]["format"]["strict"] is True
    assert payload["text"]["format"]["schema"]["additionalProperties"] is False
    assert json.loads(payload["input"])["feedback"] == ["Previous security check failed"]
    assert headers["Authorization"] == "Bearer test-secret" and timeout == 30
    assert SOURCE.files["app.py"] == "query = 'unsafe'\n"


@pytest.mark.parametrize(
    "proposal",
    [
        {"attempt": 1, "diff": DIFF, "verdict": "verified"},
        {"attempt": "1", "diff": DIFF},
        {"attempt": 2, "diff": DIFF},
        {"attempt": 1, "diff": ""},
        {"diff": DIFF},
    ],
)
def test_invalid_structured_proposals(proposal):
    client, calls = defender(completed(proposal))
    with pytest.raises(ProviderError):
        client.generate_patch(SOURCE, FINDING, [])
    assert len(calls) == 1


@pytest.mark.parametrize(
    "response,code",
    [
        ({"status": "incomplete", "output": []}, "incomplete_response"),
        ({"status": "failed", "error": {"message": "secret"}}, "incomplete_response"),
        ({"status": "completed", "output": []}, "invalid_response"),
        ({"status": "completed", "output": [{"type": "function_call"}]}, "unexpected_output"),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "refusal", "refusal": "secret"}],
                    }
                ],
            },
            "refused",
        ),
    ],
)
def test_incomplete_refused_and_tool_outputs(response, code):
    client, _ = defender(response)
    with pytest.raises(ProviderError, match=code) as error:
        client.generate_patch(SOURCE, FINDING, [])
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "path",
    [
        "../app.py",
        "/app.py",
        "a/../app.py",
        "tests/app.py",
        "policies/security.py",
        "backend/engine/verifier.py",
        ".env",
        "security.md",
        "app\\evil.py",
        "test_app.py",
    ],
)
def test_protected_allowlists(path):
    with pytest.raises(ValueError):
        OpenAIDefender(allowed_files={path})


@pytest.mark.parametrize(
    "diff",
    [
        DIFF.replace("app.py", "other.py"),
        DIFF.replace("app.py", "../app.py"),
        DIFF.replace("--- a/app.py", "--- /dev/null"),
        DIFF.replace("+++ b/app.py", "+++ /dev/null"),
        DIFF.replace("@@ -1 +1 @@", "@@ -1,2 +1 @@"),
        DIFF.replace("'unsafe'", "'wrong snapshot'"),
        "old mode 100644\nnew mode 100755\n" + DIFF,
        DIFF + DIFF,
        DIFF + "shell command\n",
        "diff --git a/app.py b/other.py\n" + DIFF,
    ],
)
def test_unsafe_or_malformed_diff(diff):
    with pytest.raises(ProviderError, match="unsafe_patch"):
        validate_patch(diff, SOURCE, {"app.py"})


def test_git_diff_and_no_newline_support():
    validate_patch(
        "diff --git a/app.py b/app.py\nindex 123..abc 100644\n" + DIFF, SOURCE, {"app.py"}
    )
    snapshot = SourceSnapshot(snapshot_id="one", files={"app.py": "x"})
    validate_patch(
        "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x\n"
        "\\ No newline at end of file\n+y\n\\ No newline at end of file\n",
        snapshot,
        {"app.py"},
    )


def test_missing_key_and_model(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    client = OpenAIDefender(allowed_files={"app.py"})
    with pytest.raises(ProviderError, match="missing_credentials"):
        client.generate_patch(SOURCE, FINDING, [])
    client = OpenAIDefender(allowed_files={"app.py"}, api_key="secret")
    with pytest.raises(ProviderError, match="missing_model"):
        client.generate_patch(SOURCE, FINDING, [])


def test_oversized_input_does_not_send_request():
    client, calls = defender(completed())
    source = SourceSnapshot(snapshot_id="one", files={"app.py": "x" * 1_000_001})
    with pytest.raises(ProviderError, match="request_too_large"):
        client.generate_patch(source, FINDING, [])
    assert calls == []


@pytest.mark.parametrize(
    "output", [[42], [{"type": "message", "role": "assistant", "content": [42]}]]
)
def test_malformed_output_items_fail_safely(output):
    client, _ = defender({"status": "completed", "output": output})
    with pytest.raises(ProviderError, match="invalid_response"):
        client.generate_patch(SOURCE, FINDING, [])
