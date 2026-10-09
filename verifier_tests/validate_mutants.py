"""Demonstrate that frozen tests reject four controlled, known flawed patches.

Only these authored synthetic mutations run locally. This is not a runner for
AI-generated code; the verifier must supply isolation before such execution.
"""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from verifier_tests.run import ROOT, execute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = (ROOT / "demo_target/ledgerlite/reference_secure.py").read_text()
    correct = 'user["role"] != "administrator" and record["owner_id"] != x_synthetic_identity'
    mutations = {
        "hardcoded_invoice_allowlist": (
            f'invoice_id not in {{"inv-1001", "inv-2047"}} or ({correct})',
            "test_owner_access",
        ),
        "block_everyone": ("user is not None", "test_owner_access"),
        "reject_administrator": (
            'record["owner_id"] != x_synthetic_identity',
            "test_administrator_access",
        ),
        "reverse_ownership": (
            'user["role"] != "administrator" and record["owner_id"] == x_synthetic_identity',
            "test_cross_account_denied",
        ),
    }
    assert source.count(correct) == 1
    results = {}
    with tempfile.TemporaryDirectory(prefix="ledgerlite-mutants-") as temp:
        for name, (condition, required_failure) in mutations.items():
            target_root = Path(temp) / name
            shutil.copytree(ROOT / "demo_target", target_root / "demo_target")
            app = target_root / "demo_target/ledgerlite/app.py"
            app.write_text(source.replace(correct, condition))
            evidence = execute("candidate", target_root)
            failed_ids = [
                result["test_id"]
                for result in evidence["results"]
                if any(phase["outcome"] == "failed" for phase in result["phases"])
            ]
            detected = (
                evidence["complete"]
                and not evidence["expectation_met"]
                and any(required_failure in test_id for test_id in failed_ids)
            )
            results[name] = {"detected": detected, "evidence": evidence}
    output = {
        "schema_version": 1,
        "source": "execution",
        "data_label": "SYNTHETIC FIXTURE",
        "all_detected": all(result["detected"] for result in results.values()),
        "mutations": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"all_detected": output["all_detected"]}))
    return 0 if output["all_detected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
