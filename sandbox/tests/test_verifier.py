from dataclasses import replace

import pytest

from backend.engine.verifier import Verifier, evaluate_patch
from sandbox.models import ExecutionLimits, FrozenTestManifest
from sandbox.tests.helpers import GOOD_APP, good_evidence, incomplete_test, inputs


def test_valid_and_invalid_patch_acceptance(tmp_path):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    result = evaluate_patch(patch, manifest, baseline, patched)
    assert result.verdict == "verified"
    assert result.to_dict()["original_sha256"] == patch.original.sha256
    assert len(result.evidence_sha256) == 64
    failed = replace(
        patched,
        tests=(incomplete_test(patched.tests[0], "failed"), *patched.tests[1:]),
        process=replace(patched.process, exit_code=1),
    )
    assert evaluate_patch(patch, manifest, baseline, failed).verdict == "rejected"


@pytest.mark.parametrize("outcome", ["skipped", "incomplete", "error", "timeout", "unknown"])
def test_missing_or_skipped_evidence_never_passes(tmp_path, outcome):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    patched = replace(
        patched, tests=(incomplete_test(patched.tests[0], outcome), *patched.tests[1:])
    )
    assert evaluate_patch(patch, manifest, baseline, patched).verdict == "inconclusive"


@pytest.mark.parametrize(
    "change",
    [
        {"tests": ()},
        {"source_sha256": "f" * 64},
        {"manifest_sha256": "f" * 64},
        {"runner_sha256": "f" * 64},
        {"image_id": "other"},
        {"execution_id": "baseline"},
        {"phase": "baseline"},
        {"source": "fixture"},
        {"probe": None},
        {"status": "timeout"},
        {"process": None},
    ],
)
def test_stale_missing_or_unbound_evidence_never_passes(tmp_path, change):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    assert (
        evaluate_patch(patch, manifest, baseline, replace(patched, **change)).verdict != "verified"
    )


def test_duplicate_and_missing_phases_or_exit_codes(tmp_path):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    for candidate in (
        replace(patched, tests=(*patched.tests, patched.tests[0])),
        replace(patched, process=replace(patched.process, exit_code=1)),
        replace(patched, process=replace(patched.process, truncated=True)),
        replace(patched, tests=(replace(patched.tests[0], phases=()), *patched.tests[1:])),
        replace(
            patched, tests=(replace(patched.tests[0], category="functional"), *patched.tests[1:])
        ),
    ):
        assert evaluate_patch(patch, manifest, baseline, candidate).verdict != "verified"


def test_missing_or_fabricated_baseline_probe_does_not_pass(tmp_path):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    for probe in (None, {}, {"unauthorized_access_reproduced": True}):
        assert (
            evaluate_patch(patch, manifest, replace(baseline, probe=probe), patched).verdict
            != "verified"
        )


def test_manifest_requires_each_category_and_unique_tests(tmp_path):
    _, _, manifest = inputs(tmp_path)
    for changes in (
        {"checks": manifest.checks[:2]},
        {"checks": manifest.checks + manifest.checks[:1]},
        {"baseline_expected_failures": ()},
        {"trusted_files": ()},
        {"policy_sha256": ""},
        {"checks": list(manifest.checks)},
    ):
        with pytest.raises(ValueError):
            replace(manifest, **changes)
    assert isinstance(manifest, FrozenTestManifest)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cpus": 0},
        {"cpus": float("nan")},
        {"memory_mb": -1},
        {"pids": True},
        {"timeout_seconds": float("inf")},
        {"scratch_mb": 1.1},
        {"output_bytes": 999999999},
    ],
)
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        ExecutionLimits(**kwargs)


def test_verifier_stops_on_missing_docker_and_protected_patch(tmp_path):
    original, suite, manifest = inputs(tmp_path)
    calls = []

    class UnavailableRunner:
        def run(self, *args, **kwargs):
            calls.append(args)
            from sandbox.tests.helpers import evidence

            return replace(
                evidence(original, manifest, "baseline"),
                status="infrastructure_error",
                reason="Docker unavailable",
            )

    verifier = Verifier(UnavailableRunner())
    result = verifier.verify_patch(
        original, {"demo_target/ledgerlite/app.py": GOOD_APP}, suite, manifest
    )
    assert result.verdict == "error"
    assert result.patched is None and len(calls) == 1
    result = verifier.verify_patch(
        original, {"demo_target/ledgerlite/data.py": "x=1"}, suite, manifest
    )
    assert result.verdict == "rejected" and len(calls) == 1


def test_empty_xfail_reason_is_not_a_pass(tmp_path):
    patch, _, manifest, baseline, patched = good_evidence(tmp_path)
    test = patched.tests[0]
    phases = tuple({**phase, "wasxfail": ""} for phase in test.phases)
    patched = replace(patched, tests=(replace(test, phases=phases), *patched.tests[1:]))
    assert evaluate_patch(patch, manifest, baseline, patched).verdict == "inconclusive"
