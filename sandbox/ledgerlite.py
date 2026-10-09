"""Admission adapter for A1's frozen LedgerLite fixture manifest."""

from __future__ import annotations

from sandbox.models import FrozenTestManifest, TestCheck

SOURCE_FILES = (
    "demo_target/__init__.py",
    "demo_target/ledgerlite/__init__.py",
    "demo_target/ledgerlite/app.py",
    "demo_target/ledgerlite/data.py",
)
PATCH_ALLOWLIST = ("demo_target/ledgerlite/app.py",)


def manifest_from_ledgerlite(document: dict, *, policy_sha256: str) -> FrozenTestManifest:
    """Call only on a trusted frozen manifest, never on provider output."""
    if document.get("target") != "LedgerLite" or document.get("schema_version") != 1:
        raise ValueError("Unsupported LedgerLite manifest")
    if tuple(document.get("patch_allowlist", ())) != PATCH_ALLOWLIST:
        raise ValueError("Unexpected LedgerLite patch allowlist")
    checks = []
    failures = []
    for test_id in document["required_test_ids"]:
        if "::test_cross_account_denied[" in test_id:
            category = "security"
            failures.append(test_id)
        elif "::test_invalid_identity[" in test_id:
            category = "adversarial"
        elif test_id.endswith("::test_access_sequence_preserves_functionality"):
            category = "adversarial"
            failures.append(test_id)
        elif any(
            f"::{name}" in test_id
            for name in (
                "test_owner_access[",
                "test_administrator_access[",
                "test_nonexistent_invoice[",
            )
        ) or test_id.endswith("::test_health"):
            category = "functional"
        else:
            raise ValueError("Unrecognized test: explicitly review its category before admission")
        checks.append(TestCheck(test_id, category))
    return FrozenTestManifest(
        target="LedgerLite",
        suite_version=document["suite_version"],
        checks=tuple(checks),
        trusted_files=tuple(sorted(document["trusted_file_sha256"].items())),
        baseline_expected_failures=tuple(failures),
        policy_sha256=policy_sha256,
    )
