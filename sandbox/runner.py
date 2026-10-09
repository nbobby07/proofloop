"""Bounded Docker-only execution for the approved LedgerLite HTTP fixture."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from backend.engine.patcher import (
    SourceSnapshot,
    checked_root,
    digest,
    materialize,
    read_tree,
    remove_readonly,
)
from sandbox.ledgerlite import SOURCE_FILES
from sandbox.models import (
    HASH,
    ExecutionEvidence,
    ExecutionLimits,
    FrozenTestManifest,
    ProcessEvidence,
    TestEvidence,
)

HERE = Path(__file__).resolve().parent
RUNNER_FILES = ("models.py", "ledgerlite.py", "runner.py", "pytest_runner.py", "target_runner.py")


class InfrastructureError(ValueError):
    """The isolation environment is unavailable or cannot enforce the boundary."""


def runner_hash() -> str:
    files = [
        (name, hashlib.sha256((HERE / name).read_bytes()).hexdigest()) for name in RUNNER_FILES
    ]
    for name in ("patcher.py", "verifier.py"):
        path = HERE.parent / "backend" / "engine" / name
        files.append((f"engine/{name}", hashlib.sha256(path.read_bytes()).hexdigest()))
    return digest(files)


def freeze_suite(root: Path, manifest: FrozenTestManifest) -> tuple[tuple[str, bytes], ...]:
    """Only explicitly hashed trusted inputs cross into the test container."""
    root = checked_root(root)
    result = []
    for name, expected in manifest.trusted_files:
        path = root / name
        checked_root(path.parent)
        # read_tree enforces no-follow, regular single-link files, size bounds, no extra files.
        # Read only this one selected file, without copying the surrounding checkout.
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("Unsafe trusted suite input")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            data = stream.read(256 * 1024 + 1)
        if len(data) > 256 * 1024 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Frozen trusted suite changed")
        result.append((name, data))
    if sum(len(data) for _, data in result) > 2 * 1024 * 1024:
        raise ValueError("Trusted suite exceeds size limit")
    return tuple(sorted(result))


class _Process:
    """Drain both pipes concurrently, retaining exact bytes up to a strict combined cap."""

    def __init__(self, command: list[str], env: dict[str, str], limit: int):
        self.start = time.monotonic()
        self.limit = limit
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.lock = threading.Lock()
        self.overflow = False
        self.error = ""
        self.process = None
        self.threads = []
        try:
            self.process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
            for stream, output in (
                (self.process.stdout, self.stdout),
                (self.process.stderr, self.stderr),
            ):
                thread = threading.Thread(target=self._drain, args=(stream, output), daemon=True)
                thread.start()
                self.threads.append(thread)
        except OSError as exc:
            self.error = str(exc)

    def _drain(self, stream, output):
        try:
            while True:
                chunk = os.read(stream.fileno(), 8192)
                if not chunk:
                    break
                with self.lock:
                    remaining = max(0, self.limit - len(self.stdout) - len(self.stderr))
                    output.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        self.overflow = True
        finally:
            stream.close()

    def done(self) -> bool:
        return self.process is None or self.process.poll() is not None

    def wait(self, deadline: float, target: _Process | None = None) -> ProcessEvidence:
        status = "completed"
        while not self.done():
            if self.overflow or (target and target.overflow):
                status = "output_limit"
                break
            if target and target.done():
                status = "runner_error"
                break
            if time.monotonic() >= deadline:
                status = "timeout"
                break
            time.sleep(0.01)
        return self.finish(status)

    def finish(self, status: str = "completed") -> ProcessEvidence:
        if self.process and not self.done():
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        for thread in self.threads:
            thread.join(timeout=1)
        if any(thread.is_alive() for thread in self.threads):
            status = "runner_error"
        if self.overflow:
            status = "output_limit"
        if self.error:
            status = "runner_error"
        return ProcessEvidence(
            status=status,
            exit_code=self.process.returncode if self.process else None,
            stdout=bytes(self.stdout).decode("utf-8", errors="replace"),
            stderr=bytes(self.stderr).decode("utf-8", errors="replace") or self.error,
            duration_seconds=time.monotonic() - self.start,
            stdout_base64=base64.b64encode(self.stdout).decode(),
            stderr_base64=base64.b64encode(self.stderr).decode(),
            truncated=self.overflow,
        )


class DockerRunner:
    """Run only approved LedgerLite source, never arbitrary repo commands.

    image_id must be a locally installed, reviewed image ID (sha256:...), not a mutable tag.
    The daemon must be local. No pull/build or fallback host execution occurs here.
    """

    def __init__(
        self,
        image_id: str,
        *,
        workspace_parent: Path | None = None,
        docker_host: str = "unix:///var/run/docker.sock",
        docker_binary: str = "docker",
    ):
        if not image_id.startswith("sha256:") or not HASH.fullmatch(image_id[7:]):
            raise ValueError("A pinned local Docker image ID is required")
        if not docker_host.startswith("unix:///") or "\x00" in docker_host:
            raise ValueError("Only a local Unix Docker socket is supported")
        self.image_id = image_id
        self.workspace_parent = workspace_parent or HERE / "workspaces"
        self.docker_host = docker_host
        self.docker_binary = shutil.which(docker_binary) or docker_binary

    def _command(self, args: list[str]) -> list[str]:
        return [self.docker_binary, "--host", self.docker_host, *args]

    def _call(self, args, env, limits, deadline) -> ProcessEvidence:
        process = _Process(self._command(args), env, limits.output_bytes)
        return process.wait(min(deadline, time.monotonic() + 10))

    def _create_args(self, name, network, uid, mounts, limits):
        args = [
            "create",
            "--name",
            name,
            "--pull=never",
            "--network",
            network,
            "--user",
            f"{uid}:{uid}",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            "--cpus",
            str(limits.cpus),
            "--memory",
            f"{limits.memory_mb}m",
            "--memory-swap",
            f"{limits.memory_mb}m",
            "--pids-limit",
            str(limits.pids),
            "--ulimit",
            "nofile=256:256",
            "--ulimit",
            "core=0:0",
            "--ulimit",
            f"fsize={limits.scratch_mb * 1048576}",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={limits.scratch_mb}m,mode=1777",
            "--shm-size=1m",
            "--ipc=private",
            "--log-driver=none",
            "--restart=no",
            "--entrypoint=/usr/bin/env",
            "--workdir=/tmp",
        ]
        for source, destination in mounts:
            if any(c in str(source) for c in (",", "\n", "\r")):
                raise ValueError("Invalid Docker mount path")
            args += ["--mount", f"type=bind,src={source},dst={destination},readonly"]
        args += [
            self.image_id,
            "-i",
            "PATH=/usr/local/bin:/usr/bin:/bin",
            "HOME=/tmp",
            "TMPDIR=/tmp",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "PYTHONDONTWRITEBYTECODE=1",
            "/usr/local/bin/python",
            "-I",
            "-B",
        ]
        return args

    def run(
        self,
        workspace: SourceSnapshot,
        trusted_suite: Path,
        manifest: FrozenTestManifest,
        limits: ExecutionLimits | None = None,
        *,
        phase: str = "patched",
        deadline: float | None = None,
    ) -> ExecutionEvidence:
        """Freeze inputs, execute, collect per-test evidence, and always clean up containers."""
        limits = limits or ExecutionLimits()
        started = time.monotonic()
        deadline = min(
            deadline if deadline is not None else float("inf"),
            started + limits.total_attempt_seconds,
        )
        execution_id = uuid.uuid4().hex
        result = ExecutionEvidence(
            status="infrastructure_error",
            phase=phase,
            source_sha256=workspace.sha256,
            manifest_sha256=manifest.sha256,
            runner_sha256=runner_hash(),
            image_id=self.image_id,
            execution_id=execution_id,
        )
        if phase not in {"baseline", "patched"}:
            return replace(result, status="runner_error", reason="Unsupported execution phase")
        if tuple(name for name, _ in workspace.files) != tuple(sorted(SOURCE_FILES)):
            return replace(
                result, status="runner_error", reason="Unapproved LedgerLite source inventory"
            )
        diagnostics = []
        names = []
        target = None
        tester = None
        target_evidence = None
        cleanup_failed = False
        try:
            self.workspace_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            checked_root(self.workspace_parent)
        except (OSError, ValueError) as exc:
            return replace(result, status="infrastructure_error", reason=str(exc))
        try:
            temporary = tempfile.TemporaryDirectory(
                prefix="verify-", dir=self.workspace_parent, ignore_cleanup_errors=True
            )
        except OSError as exc:
            return replace(result, status="infrastructure_error", reason=str(exc))
        with temporary as directory:
            root = Path(directory).resolve()
            env = {"PATH": os.defpath, "HOME": str(root), "DOCKER_CONFIG": str(root / "docker")}
            try:
                suite = freeze_suite(trusted_suite, manifest)
                materialize(workspace.files, root / "source")
                materialize(suite, root / "suite")
                config = {
                    "execution_id": execution_id,
                    "source_sha256": workspace.sha256,
                    "manifest_sha256": manifest.sha256,
                    "required_test_ids": manifest.required_test_ids,
                    "output_bytes": limits.output_bytes,
                }
                materialize(
                    (
                        ("pytest_runner.py", (HERE / "pytest_runner.py").read_bytes()),
                        ("target_runner.py", (HERE / "target_runner.py").read_bytes()),
                        ("manifest.json", json.dumps(config).encode()),
                    ),
                    root / "runner",
                )
                info = self._call(["info", "--format", "{{json .}}"], env, limits, deadline)
                diagnostics.append(info)
                if info.status != "completed" or info.exit_code != 0:
                    result = replace(
                        result, reason="Docker unavailable; no code was executed on host"
                    )
                else:
                    daemon = json.loads(info.stdout)
                    if (
                        not isinstance(daemon, dict)
                        or not daemon.get("ServerVersion")
                        or daemon.get("ServerErrors")
                    ):
                        raise InfrastructureError(
                            "Docker unavailable; no code was executed on host"
                        )
                    if not all(
                        daemon.get(flag) is True
                        for flag in ("MemoryLimit", "SwapLimit", "CpuCfsQuota", "PidsLimit")
                    ) or not any(
                        "seccomp" in option for option in daemon.get("SecurityOptions", [])
                    ):
                        raise InfrastructureError(
                            "Docker daemon cannot enforce required resource/seccomp limits"
                        )
                    inspection = self._call(
                        ["image", "inspect", self.image_id], env, limits, deadline
                    )
                    diagnostics.append(inspection)
                    if inspection.status != "completed" or inspection.exit_code != 0:
                        raise InfrastructureError("Pinned runner image unavailable locally")
                    image = json.loads(inspection.stdout)[0]
                    if image["Id"] != self.image_id or image.get("Config", {}).get("Volumes"):
                        raise ValueError("Image identity mismatch or implicit image volumes")
                    target_name = f"proofloop-target-{execution_id}"
                    tests_name = f"proofloop-tests-{execution_id}"
                    names.extend((target_name, tests_name))
                    target_args = self._create_args(
                        target_name,
                        "none",
                        10001,
                        [(root / "source", "/source"), (root / "runner", "/runner")],
                        limits,
                    ) + ["/runner/target_runner.py"]
                    created = self._call(target_args, env, limits, deadline)
                    diagnostics.append(created)
                    if created.status != "completed" or created.exit_code != 0:
                        raise ValueError("Target container creation failed")
                    target = _Process(
                        self._command(["start", "--attach", target_name]), env, limits.output_bytes
                    )
                    execution_deadline = min(deadline, target.start + limits.timeout_seconds)
                    # The tests share only the target's network namespace (loopback, no network).
                    # PID, mount, UID, IPC, and scratch namespaces stay separate.
                    test_args = self._create_args(
                        tests_name,
                        f"container:{target_name}",
                        10002,
                        [(root / "suite", "/suite"), (root / "runner", "/runner")],
                        limits,
                    ) + ["/runner/pytest_runner.py"]
                    # Wait for Docker start before joining its network namespace.
                    running = False
                    for _ in range(50):
                        inspection = self._call(
                            ["inspect", "--format", "{{.State.Running}}", target_name],
                            env,
                            limits,
                            execution_deadline,
                        )
                        if inspection.status == "completed" and inspection.stdout.strip() == "true":
                            running = True
                            break
                        if (
                            target.done()
                            or target.overflow
                            or time.monotonic() >= execution_deadline
                        ):
                            break
                        time.sleep(0.02)
                    if not running:
                        diagnostics.append(inspection)
                        raise ValueError("Target container failed to start")
                    created = self._call(test_args, env, limits, execution_deadline)
                    diagnostics.append(created)
                    if created.status != "completed" or created.exit_code != 0:
                        raise ValueError("Trusted test container creation failed")
                    tester = _Process(
                        self._command(["start", "--attach", tests_name]), env, limits.output_bytes
                    )
                    process = tester.wait(execution_deadline, target)
                    if process.status == "completed":
                        result = self._parse(result, process, manifest)
                    else:
                        result = replace(
                            result,
                            status=process.status,
                            process=process,
                            reason="Execution did not complete",
                        )
                    if target.done() or target.overflow:
                        result = replace(
                            result,
                            status="runner_error",
                            reason="Target terminated or exceeded output cap",
                        )
                    if read_tree(root / "source", tuple(sorted(SOURCE_FILES))) != workspace.files:
                        raise ValueError("Source mount changed during execution")
                    if freeze_suite(root / "suite", manifest) != suite:
                        raise ValueError("Trusted suite mount changed during execution")
                    if result.runner_sha256 != runner_hash():
                        raise ValueError("Runner changed during execution")
            except InfrastructureError as exc:
                result = replace(result, status="infrastructure_error", reason=str(exc))
            except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
                result = replace(result, status="runner_error", reason=str(exc))
            finally:
                # Removing the container kills all descendants, not just the Docker CLI process.
                target_exited = target is not None and target.done()
                for name in reversed(names):
                    cleanup = self._call(
                        ["rm", "--force", name], env, limits, time.monotonic() + 10
                    )
                    diagnostics.append(cleanup)
                    if cleanup.status != "completed" or (
                        cleanup.exit_code != 0 and "No such container" not in cleanup.stderr
                    ):
                        cleanup_failed = True
                if tester is not None and not tester.done():
                    tester.finish("runner_error")
                if target is not None:
                    target_evidence = target.finish(
                        "completed" if target_exited else "stopped_by_runner"
                    )
                try:
                    remove_readonly(root)
                except OSError:
                    cleanup_failed = True
        if root.exists():
            cleanup_failed = True
        if target_evidence and target_evidence.status in {"output_limit", "runner_error"}:
            result = replace(result, status=target_evidence.status, reason="Target capture failed")
        if cleanup_failed:
            result = replace(
                result,
                status="infrastructure_error",
                reason="Container or workspace cleanup failed",
            )
        if time.monotonic() > deadline and result.status == "completed":
            result = replace(result, status="timeout", reason="Total attempt budget exceeded")
        return replace(result, target_process=target_evidence, diagnostics=tuple(diagnostics))

    @staticmethod
    def _parse(result, process, manifest):
        try:
            payload = json.loads(process.stdout)
            if not isinstance(payload, dict) or not isinstance(payload.get("probe"), dict):
                raise ValueError("Malformed result envelope")
            if (
                type(payload.get("pytest_exit_code")) is not int
                or not isinstance(payload.get("pytest_stdout"), str)
                or not isinstance(payload.get("pytest_stderr"), str)
                or not isinstance(payload.get("results"), dict)
                or not isinstance(payload.get("collected"), list)
            ):
                raise ValueError("Missing process output or test inventory")
            if (
                payload["schema_version"] != 1
                or payload["execution_id"] != result.execution_id
                or payload["source_sha256"] != result.source_sha256
                or payload["manifest_sha256"] != result.manifest_sha256
                or payload["pytest_exit_code"] != process.exit_code
                or sorted(payload["collected"]) != sorted(manifest.required_test_ids)
                or set(payload["results"]) != set(manifest.required_test_ids)
                or process.exit_code not in (0, 1)
            ):
                raise ValueError("Missing, duplicate, stale, or mismatched test evidence")
            tests = []
            for check in manifest.checks:
                phases = payload["results"][check.test_id]
                if not isinstance(phases, list) or any(not isinstance(p, dict) for p in phases):
                    raise ValueError("Malformed test phase evidence")
                outcome = "incomplete"
                if any(p["outcome"] == "skipped" or p.get("wasxfail") is not None for p in phases):
                    outcome = "skipped"
                elif [p["phase"] for p in phases] == ["setup", "call", "teardown"]:
                    if phases[0]["outcome"] == phases[2]["outcome"] == "passed":
                        outcome = phases[1]["outcome"]
                    else:
                        outcome = "error"
                tests.append(TestEvidence(check.test_id, check.category, outcome, tuple(phases)))
            probe = payload["probe"]
            if type(probe.get("unauthorized_access_reproduced")) is not bool:
                raise ValueError("Missing baseline probe")
            return replace(
                result, status="completed", tests=tuple(tests), probe=probe, process=process
            )
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            return replace(result, status="runner_error", process=process, reason=str(exc))


def evidence_json(result: ExecutionEvidence) -> str:
    return json.dumps(asdict(result), sort_keys=True, indent=2)
