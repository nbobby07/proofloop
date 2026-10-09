"""LedgerLite Workspace v2 composition. Reports remain compatible with Classic."""

import asyncio
import hashlib
import json
import os
import threading
from dataclasses import asdict
from uuid import uuid4

from backend.api.schemas import BaselineResult, Finding, RunStatus, VerificationSummary
from backend.engine.orchestrator import (
    BaselineReceipt,
    DiscoveryReceipt,
    ExecutionFailure,
    StageResult,
)
from backend.engine.patcher import SourceSnapshot, apply_unified_diff, disposable_workspace
from backend.providers.akash_compute import Budget, Compute
from backend.providers.akash_workspace import WorkspaceAttacker
from backend.providers.contracts import SourceSnapshot as ProviderSnapshot
from backend.providers.openai_client import OpenAIDefender
from backend.providers.semgrep_client import SemgrepScanner
from backend.storage.evidence import EvidenceStore
from sandbox.workspace.protocol import POLICY, frozen_cases, sha
from sandbox.workspace.runner import build, execute_local, make_job, runner_hash

SOURCE_PATH = "demo_target/ledgerlite_workspace/app.py"


class WorkspaceEngine:
    def __init__(self, repository, store):
        self.root, self.store = repository, store
        self.original = SourceSnapshot(((SOURCE_PATH, (repository / SOURCE_PATH).read_bytes()),))
        self.provenance = json.loads(
            (repository / "demo_target/ledgerlite_workspace/original/provenance.json").read_text()
        )
        if (
            hashlib.sha256(self.original.files[0][1]).hexdigest()
            != self.provenance["source_sha256"]
        ):
            raise ValueError("Generated original source changed")
        self.budget = Budget(store.root / "akash-budget.sqlite3")
        self.artifacts = EvidenceStore(
            store.root / "artifacts",
            tuple(
                os.getenv(k, "")
                for k in ("AKASHML_API_KEY", "AKASH_CONSOLE_API_KEY", "OPENAI_API_KEY")
            ),
        )
        self.details = store.root / "workspace-details"
        self.details.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.contexts, self.sinks = {}, {}
        self.cancellations = {}
        self.workspaces = repository / "sandbox/workspaces"
        self.workspaces.mkdir(parents=True, exist_ok=True)
        self.scanner = SemgrepScanner(
            approved_roots=[self.workspaces], executable=os.getenv("SEMGREP_EXECUTABLE", "semgrep")
        )

    def bind(self, run_id, sink):
        self.sinks[run_id] = sink
        self.cancellations[run_id] = threading.Event()

    def release(self, run_id):
        if run_id in self.cancellations:
            self.cancellations[run_id].set()
        self.contexts.pop(run_id, None)
        self.sinks.pop(run_id, None)

    def entries(self, run_id):
        # RunStore validates the identifier before any detail endpoint reaches here.
        self.store.get(run_id)
        path = self.details / (run_id + ".json")
        return json.loads(path.read_text()) if path.exists() else []

    def entry(self, run_id, kind, payload):
        reference = self.artifacts.save(payload, f"Workspace {kind} evidence.")
        payload = self.artifacts.read(reference)
        entries = self.entries(run_id)
        entries.append({"kind": kind, "reference": reference.model_dump(), "data": payload})
        path = self.details / (run_id + ".json")
        temporary = path.with_suffix(".pending")
        temporary.write_text(json.dumps(entries))
        temporary.chmod(0o600)
        temporary.replace(path)
        if run_id in self.sinks:
            metadata = {
                "provider": payload.get("provider", "local"),
                "activity": kind,
                "target_revision": self.original.sha256,
                "suite_hash": payload.get("suite_sha256"),
                "environment": payload.get("environment"),
                "duration_ms": payload.get("latency_ms"),
                "model": payload.get("model"),
                "cost_reservation_usd": payload.get("cost_reservation_usd"),
            }
            self.sinks[run_id](f"Workspace: {kind.replace('_', ' ')}.", metadata)
        return reference

    def context(self, run_id):
        if run_id not in self.contexts:
            entries = self.entries(run_id)
            context = next((e["data"] for e in reversed(entries) if e["kind"] == "context"), None)
            if (
                not context
                or context["runner_sha256"] != runner_hash()
                or context["source_sha256"] != self.original.sha256
            ):
                raise ExecutionFailure(
                    "workspace_execution_context_changed", RunStatus.INCONCLUSIVE
                )
            self.contexts[run_id] = context
        return self.contexts[run_id]

    def propose(self, run_id, source, findings, limit=3):
        context = self.contexts[run_id]
        self.budget.reserve("ml_" + uuid4().hex, "akashml", 0.1)
        proposal = WorkspaceAttacker().generate(
            source=source.decode(),
            findings=findings,
            previous=context.get("failures", [])[:20],
            max_challenges=limit,
        )
        # Preserve earlier admitted tests and bind every new generation to a fresh namespace.
        generation = context.get("generation", 0) + 1
        for case in proposal["challenges"]:
            case["id"] = f"ml{generation}_" + case["id"][:54]
        context["generation"] = generation
        context["cases"].extend(proposal["challenges"])
        if len(context["cases"]) > 100:
            raise ExecutionFailure("workspace_challenge_capacity", RunStatus.INCONCLUSIVE)
        proposal["challenges_sha256"] = sha(proposal["challenges"])
        ref = self.entry(run_id, "akashml_challenges", proposal)
        self.entry(run_id, "context", context)
        return ref

    def local(self, run_id, source, phase):
        context = self.context(run_id)
        result = execute_local(source, context["cases"], phase)
        return result, self.entry(run_id, f"{phase}_local_tests", result)

    def remote(self, run_id, source):
        if os.getenv("PROOFLOOP_AKASH_ENABLED") != "1":
            raise ExecutionFailure("akash_compute_not_enabled", RunStatus.INCONCLUSIVE)
        context = self.context(run_id)
        cancellation = self.cancellations.setdefault(run_id, threading.Event())
        if cancellation.is_set():
            raise ExecutionFailure("workspace_cancelled")
        job = make_job(
            hashlib.sha256(self.original.files[0][1]).hexdigest(), context["cases"], "baseline"
        )
        job["targets"][0]["url"] = "http://baseline:8000"
        job["targets"].append(
            {
                "name": "patched",
                "url": "http://patched:8000",
                "source_sha256": hashlib.sha256(source).hexdigest(),
            }
        )
        registry = os.getenv("PROOFLOOP_WORKSPACE_REGISTRY") or "ttl.sh/proofloop-" + uuid4().hex
        original = build(self.original.files[0][1], job, platform="linux/amd64", registry=registry)
        patched = build(source, job, platform="linux/amd64", registry=registry)
        if cancellation.is_set():
            raise ExecutionFailure("workspace_cancelled")
        images = {
            "baseline": original["target"],
            "patched": patched["target"],
            "tester": patched["tester"],
        }
        result = Compute(self.budget).run(
            images,
            job,
            lambda status, data: self.entry(
                run_id, "akash_" + status, {"provider": "akash_compute", **data}
            ),
            cancelled=cancellation,
        )
        return result, self.entry(run_id, "akash_tests", result)

    async def discover(self, run_id, target):
        return await asyncio.to_thread(self._discover, run_id)

    def _discover(self, run_id):
        context = {
            "source_sha256": self.original.sha256,
            "runner_sha256": runner_hash(),
            "policy_id": POLICY,
            "cases": [c.model_dump() for c in frozen_cases()],
        }
        self.contexts[run_id] = context
        refs = [
            self.entry(run_id, "generation_provenance", self.provenance),
            self.entry(run_id, "context", context),
        ]
        try:
            with disposable_workspace(self.original, self.workspaces) as workspace:
                scan = self.scanner.scan_with_details(workspace)
            payload = asdict(scan)
            payload["result"] = scan.result.model_dump(mode="json")
            payload["provider"] = "semgrep"
            refs.append(self.entry(run_id, "semgrep", payload))
            if not scan.result.complete:
                raise ExecutionFailure("workspace_scan_incomplete", RunStatus.INCONCLUSIVE)
            refs.append(
                self.propose(run_id, self.original.files[0][1], payload["result"]["findings"])
            )
            baseline, ref = self.local(run_id, self.original.files[0][1], "baseline")
            refs.append(ref)
            context["baseline"] = baseline
            failed = [
                t
                for t in baseline["results"][0]["tests"]
                if not t["passed"] and t.get("security_violation") is True
            ]
            context["failures"] = [
                {"test_id": t["test_id"], "family": t["family"], "steps": t["steps"]}
                for t in failed
            ]
            if not failed and self.store.get(run_id).request.execution_mode == "local_akash":
                remote, ref = self.remote(run_id, self.original.files[0][1])
                refs.append(ref)
                # Identical revisions in a clean audit are explicitly not a repair.
                if any(not t["passed"] for r in remote["results"] for t in r["tests"]):
                    raise ExecutionFailure(
                        "local_remote_audit_disagreement", RunStatus.INCONCLUSIVE
                    )
            refs.append(self.entry(run_id, "context", context))
            if not failed:
                refs.append(
                    self.entry(
                        run_id,
                        "audit_complete",
                        {
                            "source": "execution",
                            "security_failure_reproduced": False,
                            "tests_passed": sum(
                                t["passed"] for t in baseline["results"][0]["tests"]
                            ),
                            "tests_total": len(baseline["results"][0]["tests"]),
                            "message": (
                                "No reproducible vulnerability found in this executed suite. "
                                "No patch was invented."
                            ),
                        },
                    )
                )
                return DiscoveryReceipt(evidence=refs)
            finding = Finding(
                id="runtime_" + sha(failed)[:24],
                title=f"Runtime policy failure: {failed[0]['family']} ({failed[0]['test_id']})",
                severity="high",
            )
            return DiscoveryReceipt(finding=finding, evidence=refs)
        except ExecutionFailure as exc:
            exc.evidence = refs + exc.evidence
            raise
        except Exception:
            refs.append(
                self.entry(
                    run_id,
                    "execution_incomplete",
                    {
                        "message": (
                            "A required provider or runner failed; "
                            "no security verdict was inferred."
                        )
                    },
                )
            )
            raise ExecutionFailure(
                "workspace_provider_or_runner_failed", RunStatus.INCONCLUSIVE, refs
            ) from None

    async def reproduce(self, run_id, finding):
        context = self.context(run_id)
        failed = context.get("failures", [])
        return BaselineReceipt(
            result=BaselineResult(reproduced=bool(failed)),
            evidence=[self.entry(run_id, "baseline_reproduced", {"failures": failed})],
        )

    async def generate_patch(self, run_id, finding, attempt, feedback):
        context = self.context(run_id)
        source = ProviderSnapshot(
            snapshot_id=self.original.sha256,
            files={SOURCE_PATH: self.original.files[0][1].decode()},
        )
        return await asyncio.to_thread(
            OpenAIDefender(
                allowed_files=[SOURCE_PATH], attempt=attempt, timeout=60, max_output_tokens=16384
            ).generate_patch,
            source,
            finding,
            feedback + [json.dumps(f)[:3500] for f in context.get("failures", [])[:5]],
        )

    async def apply_patch(self, run_id, patch):
        apply_unified_diff(self.original, patch.diff, allowed_files=[SOURCE_PATH])

    async def verify(self, run_id):
        return await asyncio.to_thread(self._verify, run_id, 3)

    async def challenge(self, run_id, request):
        if request.policy_ids and set(request.policy_ids) != {POLICY}:
            raise ExecutionFailure("unapproved_challenge_policy", RunStatus.INCONCLUSIVE)
        return await asyncio.to_thread(self._verify, run_id, request.max_challenges)

    def _verify(self, run_id, limit):
        context = self.context(run_id)
        record = self.store.get(run_id)
        patch = apply_unified_diff(
            self.original, record.run.patch.diff, allowed_files=[SOURCE_PATH]
        )
        source = patch.patched.files[0][1]
        refs = [self.propose(run_id, source, [], limit)]
        baseline, ref = self.local(run_id, self.original.files[0][1], "baseline")
        refs.append(ref)
        candidate, ref = self.local(run_id, source, "patched")
        refs.append(ref)
        tests = candidate["results"][0]["tests"]
        if not any(
            not t["passed"] and t.get("security_violation") is True
            for t in baseline["results"][0]["tests"]
        ):
            raise ExecutionFailure(
                "workspace_baseline_not_reproduced", RunStatus.INCONCLUSIVE, refs
            )
        if record.request.execution_mode == "local_akash":
            remote, ref = self.remote(run_id, source)
            refs.append(ref)
            for local, cloud in zip(
                [baseline["results"][0], candidate["results"][0]], remote["results"], strict=True
            ):
                if [(t["test_id"], t["passed"]) for t in local["tests"]] != [
                    (t["test_id"], t["passed"]) for t in cloud["tests"]
                ]:
                    raise ExecutionFailure(
                        "local_remote_verification_disagreement", RunStatus.INCONCLUSIVE, refs
                    )
        context["failures"] = [
            {"test_id": t["test_id"], "steps": t["steps"]} for t in tests if not t["passed"]
        ]
        refs.append(self.entry(run_id, "context", context))
        counts = {
            f"{cat}_{kind}": sum(
                t["category"] == cat and (t["passed"] if kind == "passed" else True) for t in tests
            )
            for cat in ("security", "functional", "adversarial")
            for kind in ("passed", "total")
        }
        return StageResult(
            verdict=RunStatus.VERIFIED if all(t["passed"] for t in tests) else RunStatus.REJECTED,
            summary=VerificationSummary(**counts),
            evidence=refs,
            complete=True,
            patch_sha256=hashlib.sha256(record.run.patch.diff.encode()).hexdigest(),
        )


class TargetDispatcher:
    def __init__(self, classic, workspace, store):
        self.classic, self.workspace, self.store = classic, workspace, store

    def engine(self, run_id):
        if self.store.get(run_id).run.target == "LedgerLite Workspace":
            return self.workspace
        return self.classic

    def bind(self, run_id, sink):
        engine = self.engine(run_id)
        if hasattr(engine, "bind"):
            engine.bind(run_id, sink)

    def release(self, run_id):
        engine = self.engine(run_id)
        if hasattr(engine, "release"):
            engine.release(run_id)

    def __getattr__(self, name):
        if name not in {
            "discover",
            "reproduce",
            "generate_patch",
            "apply_patch",
            "verify",
            "challenge",
        }:
            raise AttributeError(name)

        async def dispatch(run_id, *args):
            engine = self.engine(run_id)
            if engine is None:
                raise ExecutionFailure("target_execution_not_configured")
            return await getattr(engine, name)(run_id, *args)

        return dispatch
