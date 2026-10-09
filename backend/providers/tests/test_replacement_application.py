"""Exact generated-diff interoperability with the independent A2 patcher, never source execution.

In the integrated repository this runs automatically. A provider-only checkout can use
PROOFLOOP_A2_PATCHER_PATH to select the trusted finalized A2 module for local verification.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from backend.api.schemas import Finding, PatchProposal
from backend.providers.contracts import SourceSnapshot
from backend.providers.http import HttpResponse
from backend.providers.openai_client import OpenAIDefender

APP_PATH = "demo_target/ledgerlite/app.py"


@pytest.fixture
def a2_patcher(monkeypatch):
    location = os.getenv("PROOFLOOP_A2_PATCHER_PATH")
    if location:
        # Explicit trusted developer module, never a model-selected path or target source.
        spec = importlib.util.spec_from_file_location("_proofloop_a2_patcher_test", Path(location))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    else:
        from backend.engine import patcher as module
    if not hasattr(module, "apply_unified_diff"):
        pytest.skip("Requires integrated A2 patcher or explicit trusted A2 module path")
    return module


def request_replacements(source, replacements):
    body = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "attempt": 1,
                                "replacements": [
                                    {"path": path, "content": content}
                                    for path, content in replacements.items()
                                ],
                            }
                        ),
                    }
                ],
            }
        ],
    }
    client = OpenAIDefender(
        allowed_files=set(replacements),
        api_key="test-secret",
        model="gpt-6-luna",
        timeout=30,
        retries=0,
        reasoning_effort="none",
        transport=lambda *args: HttpResponse(200, json.dumps(body).encode()),
    )
    return client.generate_patch(
        source, Finding(id="test-finding", title="Synthetic source change", severity="high"), []
    )


@pytest.mark.parametrize(
    "before,after",
    [
        (
            "def allowed(owner, actor):\n    return True\n",
            "def allowed(owner, actor):\n    return owner == actor\n",
        ),
        ("value = 1", "value = 2"),
        ("value = 1\n", "value = 2"),
        ("value = 1", "value = 2\n"),
        ("value = 1\n", ""),
        ("", "value = 1\n"),
        (
            "\n".join(f"value_{i} = {i}" for i in range(30)) + "\n",
            "\n".join(f"value_{i} = {i + 1 if i in {1, 25} else i}" for i in range(30)) + "\n",
        ),
    ],
)
def test_model_replacements_produce_diff_that_a2_applies_exactly(a2_patcher, before, after):
    source = SourceSnapshot(snapshot_id="approved-test", files={APP_PATH: before})
    proposal = request_replacements(source, {APP_PATH: after})
    assert isinstance(proposal, PatchProposal)
    frozen = a2_patcher.SourceSnapshot(((APP_PATH, before.encode()),))
    prepared = a2_patcher.apply_unified_diff(frozen, proposal.diff, allowed_files=(APP_PATH,))
    assert prepared.patched.files == ((APP_PATH, after.encode()),)
    assert prepared.original.files == ((APP_PATH, before.encode()),)
    assert prepared.unified_diff == proposal.diff
    assert source.files == {APP_PATH: before}


def test_multiple_files_have_deterministic_diff_order_and_apply_exactly(a2_patcher):
    paths = {"z.py": "value = 1\n", "a.py": "value = 2\n", "unchanged.py": "value = 3\n"}
    source = SourceSnapshot(snapshot_id="multiple", files=paths)
    replacements = {"z.py": "value = 10\n", "a.py": "value = 20\n"}
    proposal = request_replacements(source, replacements)
    reversed_proposal = request_replacements(source, dict(reversed(list(replacements.items()))))
    assert proposal.diff == reversed_proposal.diff
    assert proposal.diff.index("--- a/a.py") < proposal.diff.index("--- a/z.py")
    frozen = a2_patcher.SourceSnapshot(
        tuple(sorted((p, text.encode()) for p, text in paths.items()))
    )
    prepared = a2_patcher.apply_unified_diff(
        frozen, proposal.diff, allowed_files=tuple(sorted(replacements))
    )
    assert dict(prepared.patched.files) == {
        "z.py": b"value = 10\n",
        "a.py": b"value = 20\n",
        "unchanged.py": b"value = 3\n",
    }
