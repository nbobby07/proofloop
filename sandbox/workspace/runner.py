"""Versioned local/cloud builds and receipt validation; no candidate host execution."""

import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from backend.providers.process import run_bounded
from sandbox.workspace.protocol import Case, category, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "python@sha256:e88e9763f943ec1834f992a4b51e0f24500486803e8bc534e5767af9ea65f6ce"


def command(args, timeout=60):
    output = run_bounded(
        ["docker", *args],
        cwd=ROOT,
        env={
            "PATH": os.environ.get("PATH", os.defpath),
            "HOME": str(Path.home()),
            "DOCKER_HOST": os.getenv("PROOFLOOP_DOCKER_HOST", "unix:///var/run/docker.sock"),
        },
        timeout=timeout,
    )
    if output.returncode:
        raise RuntimeError("docker_operation_failed")
    return output.stdout.decode()


def runner_hash():
    return sha(
        {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("runner.py", "launcher.py", "tester.py", "protocol.py", "Dockerfile")
        }
    )


def make_job(source_sha, cases, phase):
    validated = [Case.model_validate(c).model_dump() for c in cases]
    if len(validated) > 100 or len({c["id"] for c in validated}) != len(validated):
        raise ValueError("Invalid test inventory")
    return {
        "job_id": "job_" + uuid4().hex,
        "nonce": uuid4().hex + uuid4().hex,
        "cases": validated,
        "targets": [{"name": phase, "url": "http://127.0.0.1:8000", "source_sha256": source_sha}],
    }


def validate_receipt(receipt, job):
    if not isinstance(receipt, dict) or set(receipt) != {
        "job_id",
        "nonce",
        "suite_sha256",
        "results",
    }:
        raise ValueError("Invalid receipt fields")
    if any(receipt.get(k) != job[k] for k in ("job_id", "nonce")) or receipt["suite_sha256"] != sha(
        job["cases"]
    ):
        raise ValueError("Receipt identity mismatch")
    if len(receipt["results"]) != len(job["targets"]):
        raise ValueError("Incomplete targets")
    for expected, actual in zip(job["targets"], receipt["results"], strict=True):
        if any(actual.get(k) != v for k, v in expected.items()):
            raise ValueError("Target identity mismatch")
        tests = actual["tests"]
        if [t["test_id"] for t in tests] != [c["id"] for c in job["cases"]]:
            raise ValueError("Test inventory mismatch")
        for case, test in zip(job["cases"], tests, strict=True):
            if (
                test.get("category") != category(Case.model_validate(case))
                or test.get("family") != case["family"]
            ):
                raise ValueError("Test policy mismatch")
            if len(test["steps"]) != len(case["actions"]) or type(test["passed"]) is not bool:
                raise ValueError("Incomplete test steps")
            if [s["step"] for s in test["steps"]] != list(range(len(case["actions"]))):
                raise ValueError("Duplicate or missing steps")
            if any(type(s.get("observed_status")) is not int for s in test["steps"]):
                raise ValueError("Missing HTTP execution evidence")
            if any(type(s["passed"]) is not bool for s in test["steps"]) or test["passed"] != all(
                s["passed"] for s in test["steps"]
            ):
                raise ValueError("Invalid outcomes")
    return receipt


def parse_receipt(logs, job):
    framed = [line for line in logs.splitlines() if line.startswith("PROOFLOOP_RECEIPT_")]
    if framed:
        if "PROOFLOOP_RECEIPT=" in logs or len(logs) > 512_000:
            raise ValueError("Ambiguous or oversized receipt")
        if not framed[0].startswith("PROOFLOOP_RECEIPT_BEGIN=") or framed[-1] != (
            "PROOFLOOP_RECEIPT_END=complete"
        ):
            raise ValueError("Incomplete receipt framing")
        header = json.loads(framed[0].split("=", 1)[1])
        count = header.get("chunks")
        if type(count) is not int or not 1 <= count <= 100 or len(framed) != count + 2:
            raise ValueError("Invalid receipt chunk inventory")
        pieces = []
        for index, line in enumerate(framed[1:-1]):
            prefix = f"PROOFLOOP_RECEIPT_CHUNK={index}:"
            if not line.startswith(prefix) or len(line) > 6100:
                raise ValueError("Missing, repeated or reordered receipt chunk")
            pieces.append(line[len(prefix) :])
        payload = base64.b64decode("".join(pieces), validate=True)
        if hashlib.sha256(payload).hexdigest() != header.get("sha256"):
            raise ValueError("Receipt transport hash mismatch")
        return validate_receipt(json.loads(payload), job)
    lines = [
        line.removeprefix("PROOFLOOP_RECEIPT=")
        for line in logs.splitlines()
        if line.startswith("PROOFLOOP_RECEIPT=")
    ]
    if len(lines) != 1:
        raise ValueError("Missing or repeated receipt")
    return validate_receipt(json.loads(lines[0]), job)


def build(source, job, *, platform=None, registry=None):
    """Build a fixed recipe from a curated context; never RUN supplied source."""
    if len(source) > 200_000:
        raise ValueError("Source exceeds budget")
    images = {}
    with tempfile.TemporaryDirectory(prefix="proofloop-build-") as directory:
        context = Path(directory)
        for name in ("Dockerfile", "launcher.py", "tester.py", "protocol.py"):
            shutil.copyfile(HERE / name, context / name)
        shutil.copyfile(ROOT / "sandbox/requirements.lock", context / "requirements.lock")
        shutil.copyfile(
            ROOT / "demo_target/ledgerlite_workspace/index.html", context / "index.html"
        )
        (context / "app.py").write_bytes(source)
        (context / "job.json").write_text(json.dumps(job))
        for target in ("target", "tester"):
            identity = sha(
                {
                    "platform": platform or "native",
                    "source": hashlib.sha256(source).hexdigest() if target == "target" else job,
                    "runner": runner_hash(),
                }
            )[:24]
            tag = f"proofloop-workspace-{target}:{identity}"
            args = [
                "build",
                "--quiet",
                "--provenance=false",
                "--sbom=false",
                "--build-arg",
                f"PYTHON_BASE={BASE}",
                "--target",
                target,
                "-t",
                tag,
            ]
            if platform:
                args += ["--platform", platform]
            command([*args, directory], timeout=300)
            local = command(["image", "inspect", tag, "--format", "{{.Id}}"], 20).strip()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", local):
                raise ValueError("Invalid image identity")
            if registry:
                repository = (
                    f"{registry}-{target}-{identity}"
                    if registry.startswith("ttl.sh/")
                    else f"{registry}/{target}"
                )
                remote = repository + (":24h" if registry.startswith("ttl.sh/") else f":{identity}")
                command(["tag", local, remote])
                command(["push", remote], 300)
                digests = json.loads(
                    command(["image", "inspect", remote, "--format", "{{json .RepoDigests}}"], 20)
                )
                matches = [d for d in digests if d.startswith(f"{repository}@sha256:")]
                if len(matches) != 1:
                    raise ValueError("Registry digest missing")
                images[target] = matches[0]
            else:
                images[target] = local
    return images


def execute_local(source, cases, phase="baseline"):
    job = make_job(hashlib.sha256(source).hexdigest(), cases, phase)
    images = build(source, job)
    name = "proofloop-v2-" + uuid4().hex
    tester = name + "-tester"
    flags = [
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=64",
        "--log-opt=max-size=1m",
        "--log-opt=max-file=1",
    ]
    result = None
    try:
        command(
            [
                "run",
                "-d",
                "--pull=never",
                "--name",
                name,
                "--network=none",
                *flags,
                "--cap-add=SYS_CHROOT",
                "--cap-add=SETUID",
                "--cap-add=SETGID",
                "--tmpfs",
                "/jail/tmp:rw,noexec,nosuid,size=64m,mode=1777",
                images["target"],
            ]
        )
        command(
            [
                "create",
                "--pull=never",
                "--name",
                tester,
                "--network=container:" + name,
                *flags,
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m",
                images["tester"],
            ]
        )
        logs = command(["start", "-a", tester], 150)
        result = parse_receipt(logs, job)
        result.update({"environment": "local", "runner_sha256": runner_hash(), "images": images})
    finally:
        for container in (tester, name):
            command(["rm", "-f", container], 30)
    return result
