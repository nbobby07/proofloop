import base64
import json
import os
import sys
import time
from dataclasses import replace

import pytest

from sandbox.models import ExecutionLimits, ProcessEvidence
from sandbox.runner import DockerRunner, _Process, freeze_suite
from sandbox.tests.helpers import IMAGE, evidence, good_evidence, inputs, payload


def test_no_host_fallback_when_docker_unavailable(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    runner = DockerRunner(
        IMAGE, workspace_parent=tmp_path / "runs", docker_binary=str(tmp_path / "no-docker-exists")
    )
    result = runner.run(original, suite, manifest, phase="baseline")
    assert result.status == "infrastructure_error"
    assert "no code was executed on host" in result.reason
    assert result.tests == () and result.process is None
    assert not list((tmp_path / "runs").iterdir())


def test_frozen_suite_rejects_edits_and_links(tmp_path):
    _, suite, manifest = inputs(tmp_path)
    assert freeze_suite(suite, manifest)
    path = suite / "verifier_tests/test_checks.py"
    path.write_text("def test_forged(): pass")
    with pytest.raises(ValueError, match="changed"):
        freeze_suite(suite, manifest)
    path.unlink()
    path.symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError):
        freeze_suite(suite, manifest)


def test_isolation_arguments_and_image_admission(tmp_path):
    runner = DockerRunner(IMAGE)
    args = runner._create_args(
        "unique", "none", 10001, [(tmp_path / "source", "/source")], ExecutionLimits()
    )
    for required in (
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--pull=never",
        "--log-driver=none",
        "--ipc=private",
        "-I",
        "-B",
        "-i",
    ):
        assert required in args
    for option, value in {
        "--user": "10001:10001",
        "--network": "none",
        "--cpus": "1.0",
        "--memory": "256m",
        "--memory-swap": "256m",
        "--pids-limit": "64",
    }.items():
        assert args[args.index(option) + 1] == value
    mount = args[args.index("--mount") + 1]
    assert mount.endswith("dst=/source,readonly")
    assert not any(
        x in args for x in ("--privileged", "--publish", "-v", "--env-file", "--pid=host")
    )
    assert not any("docker.sock" in x or "/Users/" in x for x in args if x != mount)
    tester = runner._create_args("tests", "container:unique", 10002, [], ExecutionLimits())
    assert tester[tester.index("--network") + 1] == "container:unique"
    for image in ("python:latest", "sha256:" + "g" * 64):
        with pytest.raises(ValueError):
            DockerRunner(image)
    with pytest.raises(ValueError):
        DockerRunner(IMAGE, docker_host="tcp://remote:2375")


def test_actual_bounded_capture_exit_status_and_non_utf8():
    # Trusted harness test snippets, NOT target execution or a fallback runner.
    proc = _Process(
        [
            sys.executable,
            "-c",
            "import os; os.write(1,b'\\xffout'); os.write(2,b'err'); raise SystemExit(7)",
        ],
        {"PATH": os.defpath},
        4096,
    )
    result = proc.wait(time.monotonic() + 5)
    assert result.status == "completed" and result.exit_code == 7
    assert base64.b64decode(result.stdout_base64) == b"\xffout"
    assert result.stderr == "err"


def test_actual_process_timeout_and_output_limit():
    for code, expected, timeout in (
        ("import time; time.sleep(10)", "timeout", 0.05),
        ("import os; os.write(1, b'x' * 100000)", "output_limit", 5),
    ):
        proc = _Process([sys.executable, "-c", code], {"PATH": os.defpath}, 4096)
        result = proc.wait(time.monotonic() + timeout)
        assert result.status == expected and result.exit_code is not None
        assert len(base64.b64decode(result.stdout_base64)) <= 4096


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda p: p.update(collected=p["collected"] + p["collected"][:1]),
        lambda p: p.update(collected=p["collected"][:-1]),
        lambda p: p.update(execution_id="forged"),
        lambda p: p.update(source_sha256="f" * 64),
        lambda p: p.update(manifest_sha256="f" * 64),
        lambda p: p.update(pytest_exit_code=1),
        lambda p: p.update(probe={}),
        lambda p: p.update(results={}),
    ],
)
def test_machine_results_reject_incomplete_or_forged_identity(tmp_path, corrupt):
    _, _, manifest, _, patched = good_evidence(tmp_path)
    data = payload(patched, manifest)
    corrupt(data)
    process = replace(patched.process, stdout=json.dumps(data))
    assert DockerRunner._parse(patched, process, manifest).status == "runner_error"


def test_machine_results_preserve_raw_output_and_phase_details(tmp_path):
    _, _, manifest, _, patched = good_evidence(tmp_path)
    data = payload(patched, manifest)
    data["results"][manifest.required_test_ids[0]][1]["stdout"] = "raw target response"
    process = replace(patched.process, stdout=json.dumps(data), stderr="stderr remains here")
    parsed = DockerRunner._parse(patched, process, manifest)
    assert parsed.status == "completed"
    assert parsed.process == process
    assert parsed.tests[0].phases[1]["stdout"] == "raw target response"


@pytest.mark.parametrize("failure", ["none", "test_create", "cleanup", "timeout"])
def test_mocked_lifecycle_always_cleans_both_containers(tmp_path, monkeypatch, failure):
    """Docker control-plane simulation only; does not claim kernel isolation testing."""
    import sandbox.runner as module

    original, suite, manifest = inputs(tmp_path)
    runner = DockerRunner(IMAGE, workspace_parent=tmp_path / "runs")
    commands = []
    process_commands = []

    def call(args, env, limits, deadline):
        commands.append(args)
        assert set(env) == {"PATH", "HOME", "DOCKER_CONFIG"}
        stdout = ""
        code = 0
        if args[0] == "info":
            stdout = json.dumps(
                dict(
                    ServerVersion="test-simulation",
                    MemoryLimit=True,
                    SwapLimit=True,
                    CpuCfsQuota=True,
                    PidsLimit=True,
                    SecurityOptions=["name=seccomp,profile=builtin"],
                )
            )
        elif args[:2] == ["image", "inspect"]:
            stdout = json.dumps([{"Id": IMAGE, "Config": {}}])
        elif args[0] == "inspect":
            stdout = "true\n"
        elif failure == "test_create" and args[0] == "create" and "10002:10002" in args:
            code = 1
        elif failure == "cleanup" and args[0] == "rm":
            code = 1
        return ProcessEvidence("completed", code, stdout, "simulated" if code else "", 0.01)

    class FakeProcess:
        def __init__(self, command, env, limit):
            process_commands.append(command)
            self.start = time.monotonic()
            self.overflow = False
            self.finished = False

        def done(self):
            return self.finished

        def finish(self, status="completed"):
            self.finished = True
            return ProcessEvidence(status, 137, "target output", "target stderr", 0.01)

        def wait(self, deadline, target=None):
            config_path = next((tmp_path / "runs").glob("*/runner/manifest.json"))
            config = json.loads(config_path.read_text())
            result = evidence(original, manifest, "patched")
            result = replace(result, execution_id=config["execution_id"])
            self.finished = True
            return ProcessEvidence(
                "timeout" if failure == "timeout" else "completed",
                0,
                json.dumps(payload(result, manifest)),
                "",
                0.01,
            )

    monkeypatch.setattr(runner, "_call", call)
    monkeypatch.setattr(module, "_Process", FakeProcess)
    result = runner.run(original, suite, manifest)
    assert len([command for command in commands if command[0] == "rm"]) == 2
    assert (
        result.status
        == {
            "none": "completed",
            "test_create": "runner_error",
            "cleanup": "infrastructure_error",
            "timeout": "timeout",
        }[failure]
    )
    assert result.target_process.stdout == "target output"
    assert not list((tmp_path / "runs").iterdir())
    creates = [command for command in commands if command[0] == "create"]
    assert "/suite" not in " ".join(creates[0])
    assert "dst=/source" not in " ".join(creates[1])


def test_docker_cli_zero_exit_with_server_error_is_infrastructure_failure(tmp_path, monkeypatch):
    original, suite, manifest = inputs(tmp_path)
    runner = DockerRunner(IMAGE, workspace_parent=tmp_path / "runs")
    calls = []

    def call(args, *unused):
        calls.append(args)
        return ProcessEvidence(
            "completed",
            0,
            json.dumps({"ServerErrors": ["Unavailable"]}),
            "Cannot connect to Docker daemon",
            0.01,
        )

    monkeypatch.setattr(runner, "_call", call)
    result = runner.run(original, suite, manifest)
    assert result.status == "infrastructure_error"
    assert "Docker unavailable" in result.reason
    assert len(calls) == 1 and result.tests == ()


@pytest.mark.parametrize(
    "corrupt",
    [
        lambda p: p.update(probe=[]),
        lambda p: p.update(results=[]),
        lambda p: p.update(collected={}),
        lambda p: p.update(pytest_exit_code=False),
        lambda p: p.update(pytest_stdout=None),
        lambda p: p["results"].update({next(iter(p["results"])): [None]}),
    ],
)
def test_malformed_machine_results_are_explicit_failures(tmp_path, corrupt):
    _, _, manifest, _, patched = good_evidence(tmp_path)
    data = payload(patched, manifest)
    corrupt(data)
    result = DockerRunner._parse(
        patched, replace(patched.process, stdout=json.dumps(data)), manifest
    )
    assert result.status == "runner_error"


def test_workspace_creation_failure_is_explicit(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    occupied = tmp_path / "file"
    occupied.write_text("not a directory")
    result = DockerRunner(IMAGE, workspace_parent=occupied).run(original, suite, manifest)
    assert result.status == "infrastructure_error"
    assert not result.tests


def test_machine_result_empty_xfail_reason_is_skipped(tmp_path):
    _, _, manifest, _, patched = good_evidence(tmp_path)
    data = payload(patched, manifest)
    data["results"][manifest.required_test_ids[0]][1]["wasxfail"] = ""
    result = DockerRunner._parse(
        patched, replace(patched.process, stdout=json.dumps(data)), manifest
    )
    assert result.tests[0].outcome == "skipped"


def test_trusted_pytest_adapter_collects_real_phases_without_importing_target(tmp_path):
    """Exercise only our trusted pytest plugin on a harmless test, never candidate code."""
    import subprocess

    test_file = tmp_path / "test_adapter.py"
    test_file.write_text(
        "def test_client_fixture(client):\n"
        "    assert callable(client.get)\n"
        '    print("trusted-test-output")\n'
    )
    script = """import contextlib, io, json, sys, pytest
from sandbox.pytest_runner import Recorder
recorder = Recorder()
with contextlib.redirect_stdout(io.StringIO()):
    code = pytest.main(['-c', '/dev/null', '--noconftest', '--rootdir=' + sys.argv[1],
                       '-p', 'no:cacheprovider', '--capture=sys', sys.argv[2]], plugins=[recorder])
print(json.dumps({'code': int(code), 'ids': recorder.collected, 'results': recorder.results}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), str(test_file)],
        env={
            "PATH": os.defpath,
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    result = json.loads(completed.stdout)
    assert result["code"] == 0
    assert result["ids"] == ["test_adapter.py::test_client_fixture"]
    phases = result["results"][result["ids"][0]]
    assert [phase["phase"] for phase in phases] == ["setup", "call", "teardown"]
    assert all(phase["outcome"] == "passed" for phase in phases)
    assert phases[1]["stdout"] == "trusted-test-output\n"
