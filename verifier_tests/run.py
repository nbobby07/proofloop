"""Bounded local fixture runner. NOT an isolation boundary for untrusted patches."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(variant, target_root):
    manifest = json.loads((ROOT / "verifier_tests/manifest.json").read_text())
    for name, expected in manifest["trusted_file_sha256"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"Frozen trusted input changed: {name}")
    app_name = "reference_secure.py" if variant == "reference" else "app.py"
    app_file = target_root / "demo_target/ledgerlite" / app_name
    target_files = [app_file, target_root / "demo_target/ledgerlite/data.py"]
    before = {str(path.relative_to(target_root)): digest(path) for path in target_files}
    if variant != "candidate":
        for name, expected in manifest["original_file_sha256"].items():
            if digest(target_root / name) != expected:
                raise RuntimeError(f"Original fixture changed: {name}")
    env = {
        "PATH": os.defpath,
        "PYTHONPATH": os.pathsep.join((str(target_root), str(ROOT))),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LEDGERLITE_APP_FILE": str(app_file),
    }
    with tempfile.TemporaryDirectory(prefix="ledgerlite-results-") as temp:
        result_file = Path(temp) / "results.json"
        env["LEDGERLITE_RESULTS_FILE"] = str(result_file)
        suite = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-o",
                "addopts=",
                "-p",
                "no:cacheprovider",
                "-p",
                "verifier_tests.record_results",
                "--import-mode=importlib",
                str(ROOT / "verifier_tests/test_ledgerlite.py"),
                "--rootdir",
                str(ROOT),
                "-q",
            ],
            cwd=target_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        results = json.loads(result_file.read_text())
        probe = subprocess.run(
            [
                sys.executable,
                str(ROOT / "verifier_tests/probe.py"),
                str(app_file),
            ],
            cwd=target_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode != 0:
            raise RuntimeError("Reproduction probe did not complete")
        reproduction = json.loads(probe.stdout)
    after = {str(path.relative_to(target_root)): digest(path) for path in target_files}
    # Bind evidence to unchanged inputs, and require every frozen test and phase.
    trusted_unchanged = all(
        digest(ROOT / name) == expected
        for name, expected in manifest["trusted_file_sha256"].items()
    )
    outcomes = {}
    complete = (
        sorted(results["collected"]) == sorted(manifest["required_test_ids"])
        and len(results["collected"]) == len(manifest["required_test_ids"])
        and results["pytest_exit_code"] == suite.returncode
        and before == after
        and trusted_unchanged
    )
    for result in results["results"]:
        phases = result["phases"]
        if [phase["phase"] for phase in phases] != ["setup", "call", "teardown"]:
            complete = False
        if any(phase["outcome"] == "skipped" for phase in phases):
            complete = False
        if any(phase["outcome"] != "passed" for phase in phases if phase["phase"] != "call"):
            complete = False
        outcomes[result["test_id"]] = next(
            (phase["outcome"] for phase in phases if phase["phase"] == "call"), "incomplete"
        )
    complete = complete and sorted(outcomes) == sorted(manifest["required_test_ids"])
    failed = sorted(test_id for test_id, outcome in outcomes.items() if outcome == "failed")
    expected_failures = sorted(
        test_id
        for test_id in manifest["required_test_ids"]
        if "::test_cross_account_denied[" in test_id
        or test_id.endswith("::test_access_sequence_preserves_functionality")
    )
    suite_passed = (
        complete
        and suite.returncode == 0
        and all(outcome == "passed" for outcome in outcomes.values())
    )
    baseline_reproduced = (
        complete
        and suite.returncode == 1
        and failed == expected_failures
        and all(outcome in ("passed", "failed") for outcome in outcomes.values())
        and reproduction["unauthorized_access_reproduced"]
    )
    expectation_met = (
        baseline_reproduced
        if variant == "baseline"
        else (suite_passed and not reproduction["unauthorized_access_reproduced"])
    )
    return {
        "runtime": {
            "python": sys.version,
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("fastapi", "starlette", "pydantic", "pytest", "httpx2")
            },
        },
        "schema_version": 1,
        "target": "LedgerLite",
        "variant": variant,
        "source": "execution",
        "data_label": "SYNTHETIC FIXTURE",
        "isolation": "local subprocess and in-process TestClient; not a sandbox",
        "scope": "frozen LedgerLite suite only; no platform security verdict",
        "suite_manifest_sha256": digest(ROOT / "verifier_tests/manifest.json"),
        "target_file_sha256": before,
        "inputs_unchanged": before == after and trusted_unchanged,
        "complete": complete,
        "suite_passed": suite_passed,
        "expectation_met": expectation_met,
        "baseline_reproduced": baseline_reproduced,
        "counts": {
            "required": len(manifest["required_test_ids"]),
            "passed": sum(outcome == "passed" for outcome in outcomes.values()),
            "failed": len(failed),
        },
        "probe": reproduction,
        "probe_exit_code": probe.returncode,
        **results,
        "pytest_stdout": suite.stdout,
        "pytest_stderr": suite.stderr,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("baseline", "reference", "candidate"), required=True)
    parser.add_argument("--target-root", type=Path, help="Authorized disposable repo-layout copy")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.variant == "candidate") != (args.target_root is not None):
        parser.error("--target-root is required only for candidate")
    target_root = (args.target_root or ROOT).resolve()
    try:
        evidence = execute(args.variant, target_root)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        evidence = {
            "schema_version": 1,
            "source": "execution",
            "target": "LedgerLite",
            "variant": args.variant,
            "complete": False,
            "expectation_met": False,
            "error": f"{type(exc).__name__}: execution incomplete",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: evidence[key] for key in ("variant", "complete", "expectation_met")}))
    return 0 if evidence["expectation_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
