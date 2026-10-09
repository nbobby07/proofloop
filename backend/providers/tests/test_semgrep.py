import json
import os
import subprocess

import pytest

from backend.providers.errors import ProviderError
from backend.providers.semgrep_client import SemgrepScanner


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path.resolve() / "source"
    root.mkdir()
    (root / "app.py").write_text("eval(user_input)\n")
    return root


def raw_scan():
    return {
        "version": "1.180.0",
        "results": [
            {
                "check_id": "proofloop.python.dynamic-eval",
                "path": "app.py",
                "start": {"line": 1},
                "end": {"line": 1},
                "extra": {"severity": "ERROR", "message": "secret-source"},
            }
        ],
        "errors": [],
        "paths": {"scanned": ["app.py"]},
        "skipped_rules": [],
    }


def scanner(workspace, raw=None, exit_code=0):
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        body = b"1.180.0\n" if "--version" in argv else json.dumps(raw or raw_scan()).encode()
        return subprocess.CompletedProcess(argv, 0 if "--version" in argv else exit_code, body, b"")

    return SemgrepScanner(approved_roots=[workspace], runner=runner), calls


def test_normalization_preserves_real_rule_id_and_limits_env(workspace, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    client, calls = scanner(workspace)
    report = client.scan_with_details(workspace)
    assert report.result.complete and report.result.findings[0].severity == "high"
    assert report.locations[0].rule_id == "proofloop.python.dynamic-eval"
    assert report.scanned_paths == ("app.py",)
    assert report.result.scanner_version == "1.180.0"
    assert len(report.result.ruleset_hash) == 64
    argv, kwargs = calls[-1]
    assert "--json" in argv and "--metrics=off" in argv and "--disable-nosem" in argv
    assert argv[-2:] == ["--", str(workspace)]
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert "secret-source" not in str(report)
    assert client.scan_repository(workspace).findings[0].id == report.result.findings[0].id


@pytest.mark.parametrize(
    "change,code",
    [
        ({"errors": [{"code": 3, "message": "secret"}]}, "scan_error_3"),
        ({"skipped_rules": [{"id": "one"}]}, "skipped_rules"),
        ({"paths": {"scanned": []}}, "no_scanned_files"),
        ({"paths": {"scanned": ["app.py"], "skipped": [{"path": "app.py"}]}}, "skipped_paths"),
        ({"version": "other"}, "invalid_scan_output"),
        ({"paths": {"scanned": ["../outside.py"]}}, "invalid_scan_output"),
    ],
)
def test_incomplete_scans(workspace, change, code):
    raw = raw_scan()
    raw.update(change)
    client, _ = scanner(workspace, raw)
    report = client.scan_with_details(workspace)
    assert not report.result.complete and code in report.diagnostics


def test_clean_scan_scoped_to_rules(workspace):
    raw = raw_scan()
    raw["results"] = []
    client, _ = scanner(workspace, raw)
    report = client.scan_with_details(workspace)
    assert report.result.complete and not report.result.findings
    assert "not a security verdict" in report.limitations[0]


def test_nonzero_exit_preserves_findings(workspace):
    client, _ = scanner(workspace, exit_code=2)
    report = client.scan_with_details(workspace)
    assert not report.result.complete and report.result.findings
    assert report.exit_code == 2


@pytest.mark.parametrize(
    "exception,code",
    [
        (FileNotFoundError(), "scanner_or_rules_missing"),
        (ProviderError("semgrep", "timeout"), "timeout"),
        (ProviderError("semgrep", "output_too_large"), "output_too_large"),
    ],
)
def test_scanner_failures(workspace, exception, code):
    def runner(*args, **kwargs):
        raise exception

    result = SemgrepScanner(approved_roots=[workspace], runner=runner).scan_with_details(workspace)
    assert not result.result.complete and result.diagnostics == (code,)


def test_authorization_and_symlinks(workspace):
    client, _ = scanner(workspace)
    with pytest.raises(ProviderError, match="unapproved_workspace"):
        client.scan_repository(workspace.parent)
    (workspace / "escape").symlink_to(workspace.parent, target_is_directory=True)
    with pytest.raises(ProviderError, match="unsafe_workspace_entry"):
        client.scan_repository(workspace)


def test_rules_are_pinned(workspace):
    rules = workspace.parent / "trusted.yml"
    rules.write_text("rules: []")
    client = SemgrepScanner(approved_roots=[workspace], rules=[rules])
    rules.write_text("rules: [changed]")
    report = client.scan_with_details(workspace)
    assert not report.result.complete and report.diagnostics == ("ruleset_changed",)


@pytest.mark.skipif(not os.getenv("PROOFLOOP_RUN_LOCAL_SEMGREP"), reason="Opt-in local CLI check")
def test_real_local_semgrep_detects_match_then_clean(workspace):
    executable = os.getenv("SEMGREP_EXECUTABLE", "semgrep")
    client = SemgrepScanner(approved_roots=[workspace], executable=executable)
    report = client.scan_with_details(workspace)
    assert report.result.complete, report.diagnostics
    assert [loc.rule_id for loc in report.locations] == ["proofloop.python.dynamic-eval"]
    (workspace / "app.py").write_text("value = 1\n")
    report = client.scan_with_details(workspace)
    assert report.result.complete and not report.result.findings, report.diagnostics
    (workspace / "app.py").write_text(
        "def lookup(db, value):\n"
        '    return db.execute(f"SELECT * FROM invoices WHERE id = {value}")\n'
    )
    report = client.scan_with_details(workspace)
    assert report.result.complete, report.diagnostics
    assert [loc.rule_id for loc in report.locations] == ["proofloop.python.sql-formatted-query"]
    (workspace / "hidden.py").write_text("eval(user_input)\n")
    (workspace / ".semgrepignore").write_text("hidden.py\n")
    report = client.scan_with_details(workspace)
    assert not report.result.complete and "required_sources_not_scanned" in report.diagnostics


def test_partially_ignored_sources_cannot_appear_complete(workspace):
    (workspace / "hidden.py").write_text("eval(user_input)\n")
    client, _ = scanner(workspace)
    report = client.scan_with_details(workspace)
    assert not report.result.complete
    assert "required_sources_not_scanned" in report.diagnostics
